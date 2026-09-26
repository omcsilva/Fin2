"""Operational Fin2 ledger pages and explicit Fin1 archive routes."""
from decimal import Decimal
from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse

from fin2.dashboard.detail_headers import detail_header
from django.http import Http404
from django.shortcuts import render
from fin2.dashboard.views import context, page_view, paged, query, valuation_query, VALUATION_STATUS, application_cost_events, _average_cost


@page_view
def cash(request, connection, account_id=None, institution_id=None, investor_id=None):
    data = context(request, connection)
    batch = data['batch']['batch_id']
    account = str(account_id) if account_id is not None else request.GET.get('account', '')
    currency = '' if account_id is not None else request.GET.get('currency', '')[:20]
    if account and not account.isdecimal():
        raise Http404('Conta inválida')
    portfolio = data['portfolio_filter']
    scope = """a.batch_id=? AND (?='' OR EXISTS (
        SELECT 1 FROM portfolio.application ap JOIN portfolio.membership pm
        ON pm.batch_id=ap.batch_id AND pm.application_id=ap.legacy_id
        WHERE ap.batch_id=a.batch_id AND ap.account_id=a.legacy_id
        AND CAST(pm.collection_id AS VARCHAR)=?))"""
    scope_params = [batch, portfolio, portfolio]
    group_kind = 'investor' if investor_id is not None else 'institution'
    group_id = investor_id if investor_id is not None else institution_id
    if group_id is not None:
        groups = query(connection, f'SELECT * FROM portfolio.{group_kind} WHERE batch_id=? AND legacy_id=?',
                       [batch, group_id])
        if not groups:
            raise Http404('Titular não encontrado' if investor_id is not None else 'Instituição não encontrada')
        data[group_kind] = groups[0]
        data.update(detail_header(connection, groups[0]['source_record_id'], data['global_query']))
        scope += f' AND a.{group_kind}_id=?'
        scope_params.append(group_id)
        account = ''
        currency = ''
    accounts = query(connection, '''SELECT a.*,coalesce(i.name,i.abbreviation) institution_name,
                       coalesce(t.name,t.abbreviation) investor_name,
                       coalesce(c.name,c.abbreviation) currency_name,
                       c.abbreviation currency
                       FROM portfolio.account a
                       LEFT JOIN portfolio.institution i ON i.batch_id=a.batch_id AND i.legacy_id=a.institution_id
                       LEFT JOIN portfolio.investor t ON t.batch_id=a.batch_id AND t.legacy_id=a.investor_id
                       LEFT JOIN portfolio.currency c ON c.batch_id=a.batch_id AND c.legacy_id=a.currency_id
                       WHERE '''+scope,
                     scope_params)
    if account and not any(str(a['legacy_id']) == account for a in accounts):
        raise Http404('Conta não encontrada')
    sql = """WITH entries AS (
        SELECT e.*,a.legacy_id account_id,a.name account_name,
          CASE upper(e.currency) WHEN 'REAL' THEN 'BRL' WHEN 'DOL' THEN 'USD'
            WHEN 'DOLAR' THEN 'USD' ELSE upper(e.currency) END normalized_currency,
          CASE WHEN p.entry_id IS NOT NULL AND e.amount=p.amount THEN 'Aporte da Conta de Resultado'
            WHEN e.entry_id LIKE '%:reversal' THEN 'Estorno de aporte vinculado'
            ELSE coalesce(m.description,c.description,'Lançamento') END description,
          CASE WHEN c.cash_entry_id IS NOT NULL THEN 'Importado' ELSE 'Fin2' END origin
        FROM ledger.investment_cash_entry e
        JOIN portfolio.account a ON a.source_record_id=e.account_source_record_id
        LEFT JOIN ledger.manual_event m ON m.event_id=e.entry_id
        LEFT JOIN ledger.cash_entry_canonical c ON c.cash_entry_id=e.entry_id
        LEFT JOIN ledger.purchase_contribution p ON p.entry_id=e.entry_id
        WHERE """+scope+""" AND e.settlement_date<=?
    ), balances AS (
        SELECT *,sum(amount) OVER(PARTITION BY account_source_record_id,normalized_currency
          ORDER BY settlement_date,entry_id,amount ROWS UNBOUNDED PRECEDING) running_balance
        FROM entries
    ) """
    params = [*scope_params,data['analysis_cutoff']]
    data['accounts'] = query(connection, sql+"""SELECT account_id,account_name,normalized_currency currency,
        sum(amount) balance,count(*) entry_count,count(*) FILTER(WHERE amount IS NULL) pending
        FROM entries WHERE (?='' OR normalized_currency=?)
        GROUP BY account_id,account_name,normalized_currency ORDER BY normalized_currency,account_name""",
        [*params,currency,currency])
    data['currencies'] = query(connection, sql+'SELECT DISTINCT normalized_currency currency FROM entries ORDER BY 1',params)
    year = data['year_filter']
    data.update(account_filter=account,currency_filter=currency)
    data.update(paged(request, connection, sql+"""SELECT * EXCLUDE(currency),normalized_currency currency
        FROM balances WHERE (?='' OR CAST(account_id AS VARCHAR)=?)
        AND (?='' OR normalized_currency=?)
        AND (?='' OR year(settlement_date)=CAST(? AS INTEGER))
        ORDER BY settlement_date DESC,entry_id DESC,amount DESC""",
        [*params,account,account,currency,currency,year,year or '0']))
    if group_id is not None:
        tab = request.GET.get('tab', 'resultado')
        data[group_kind + '_tab'] = tab if tab in ('resultado','contas','aplicacoes','movimentacoes') else 'resultado'
        data[group_kind + '_accounts'] = accounts
        for item in accounts:
            item['balances'] = [row for row in data['accounts'] if row['account_id'] == item['legacy_id']]
        positions_sql, positions_params = valuation_query(data)
        data['applications'] = query(connection,
            'SELECT p.* FROM (' + positions_sql + f''') p
            JOIN portfolio.account a ON a.batch_id=p.batch_id AND a.legacy_id=p.account_id
            WHERE a.{group_kind}_id=? ORDER BY p.asset_name,p.legacy_id''',
            [*positions_params, group_id])
        for application in data['applications']:
            application['status_label'] = VALUATION_STATUS.get(application['valuation_status'],application['valuation_status'])
        if data[group_kind + '_tab'] == 'resultado':
            events = application_cost_events(connection,batch)
            groups = {}
            for application in data['applications']:
                code = (application['currency'] or '').strip().upper()
                code = {'REAL':'BRL','DOL':'USD','DOLAR':'USD'}.get(code,code)
                groups.setdefault(code,[]).append(application)
            data[group_kind + '_results'] = [dict(currency=code, **summarize_application_results(items,events,data['analysis_cutoff']))
                                           for code,items in sorted(groups.items())]
        return render(request,f'dashboard/{group_kind}.html',data)
    if account_id is not None:
        tab = request.GET.get('tab', 'resultado')
        data['account_tab'] = tab if tab in ('resultado', 'aplicacoes', 'movimentacoes') else 'resultado'
        data['account'] = next(a for a in accounts if str(a['legacy_id']) == account)
        data.update(detail_header(connection, data['account']['source_record_id'], data['global_query']))
        data['accounts'] = [a for a in data['accounts'] if str(a['account_id']) == account]
        account_currency = (data['account']['currency'] or '').upper()
        account_currency = {'REAL': 'BRL', 'DOL': 'USD', 'DOLAR': 'USD'}.get(account_currency, account_currency)
        if settings.WRITE_ENABLED:
            import_options = {'account': data['account']['source_record_id']}
            if account_currency == 'BRL' and 'XP' in (data['account']['institution_name'] or '').upper():
                import_options['adapter'] = 'xp-account-statement'
            data['account_import_url'] = reverse('statement-imports') + '?' + data['global_query'] + '&' + urlencode(import_options)
        data['account_balance'] = next(
            (row for row in data['accounts'] if row['currency'] == account_currency),
            {'balance': 0, 'pending': 0, 'currency': account_currency})
        positions_sql, positions_params = valuation_query(data)
        data['applications'] = query(connection,
            'SELECT * FROM (' + positions_sql + ') p WHERE account_id=? ORDER BY asset_name,legacy_id',
            [*positions_params, account_id])
        for application in data['applications']:
            application['status_label'] = VALUATION_STATUS.get(
                application['valuation_status'], application['valuation_status'])
        if data['account_tab'] == 'resultado':
            data['account_result'] = summarize_application_results(
                data['applications'], application_cost_events(connection, batch), data['analysis_cutoff'])
        return render(request, 'dashboard/account.html', data)
    return render(request,'dashboard/cash.html',data)


def historical(view):
    def archived(request, *args, **kwargs):
        request.fin1_history = True
        return view(request, *args, **kwargs)
    return archived


def summarize_application_results(applications, cost_events, cutoff):
    events = {}
    for event in cost_events:
        events.setdefault(event['application_id'], []).append(event)
    totals = dict(invested=Decimal(0), present=Decimal(0), result=Decimal(0), pending=0, stale=0)
    for application in applications:
        cost = _average_cost(events.get(application['legacy_id'], []), cutoff)
        quantity = application['quantity_at_cutoff']
        valid_cost = (cost['status'] == 'calculated' and quantity is not None
                      and abs(cost['quantity'] - quantity) < Decimal('0.00000001'))
        present = Decimal(0) if application['valuation_status'] == 'closed' else application['reference_value']
        application['invested'] = cost['cost_balance'] if valid_cost else None
        application['present'] = present
        application['result'] = present - application['invested'] if valid_cost and present is not None else None
        if application['result'] is None:
            totals['pending'] += 1
        else:
            totals['invested'] += application['invested']
            totals['present'] += present
            totals['result'] += application['result']
        totals['stale'] += application['valuation_status'] == 'stale_price'
    return totals


@page_view
def product_detail(request, connection, product_id=None, class_id=None):
    data = context(request, connection)
    batch = data['batch']['batch_id']
    group_kind = 'asset_class' if class_id is not None else 'product'
    reference_kind = 'classe' if class_id is not None else 'produto'
    asset_column = 'class_id' if class_id is not None else 'product_id'
    group_id = class_id if class_id is not None else product_id
    records = query(connection, "SELECT * FROM portfolio.reference WHERE batch_id=? AND kind=? AND legacy_id=?",
                    [batch, reference_kind, group_id])
    if not records:
        raise Http404('Classe não encontrada' if class_id is not None else 'Produto não encontrado')
    data[group_kind] = records[0]
    data.update(detail_header(connection, records[0]['source_record_id'], data['global_query']))
    tab = request.GET.get('tab', 'resultado')
    data[group_kind + '_tab'] = tab if tab in ('resultado','contas','aplicacoes','movimentacoes') else 'resultado'
    positions_sql, params = valuation_query(data)
    selected = 'SELECT p.* FROM (' + positions_sql + f''') p
        JOIN portfolio.asset a ON a.batch_id=p.batch_id AND a.legacy_id=p.asset_id
        WHERE a.{asset_column}=?'''
    params = [*params, group_id]
    data['applications'] = query(connection, selected+' ORDER BY p.asset_name,p.legacy_id', params)
    data[group_kind + '_accounts'] = query(connection, '''SELECT DISTINCT a.*,i.name institution_name,t.name investor_name,c.abbreviation currency
        FROM ('''+selected+''') p JOIN portfolio.account a ON a.batch_id=p.batch_id AND a.legacy_id=p.account_id
        LEFT JOIN portfolio.institution i ON i.batch_id=a.batch_id AND i.legacy_id=a.institution_id
        LEFT JOIN portfolio.investor t ON t.batch_id=a.batch_id AND t.legacy_id=a.investor_id
        LEFT JOIN portfolio.currency c ON c.batch_id=a.batch_id AND c.legacy_id=a.currency_id
        ORDER BY a.name,a.legacy_id''', params)
    for application in data['applications']:
        application['status_label'] = VALUATION_STATUS.get(application['valuation_status'],application['valuation_status'])
    if data[group_kind + '_tab'] == 'resultado':
        events = application_cost_events(connection,batch)
        groups = {}
        for application in data['applications']:
            currency = (application['currency'] or '').strip().upper()
            currency = {'REAL':'BRL','DOL':'USD','DOLAR':'USD'}.get(currency,currency)
            groups.setdefault(currency,[]).append(application)
        data[group_kind + '_results'] = [dict(currency=currency, **summarize_application_results(items,events,data['analysis_cutoff']))
                                   for currency,items in sorted(groups.items())]
    if data[group_kind + '_tab'] == 'movimentacoes':
        activity = '''WITH selected AS ('''+selected+'''), activity AS (
            SELECT f.cash_component_id entry_id,p.source_record_id application_record,
                coalesce(p.asset_name,p.name) application_name,p.account_id,p.account_name,
                f.settlement_date,f.description,f.amount,f.currency,'Importado' origin
            FROM ledger.cash_flow_effective_v3 f JOIN selected p
                ON p.batch_id=f.batch_id AND p.legacy_id=f.application_id
            UNION ALL
            SELECT m.event_id,p.source_record_id,coalesce(p.asset_name,p.name),p.account_id,p.account_name,
                m.settlement_date,m.description,m.amount,m.currency,'Fin2'
            FROM ledger.manual_event m JOIN selected p ON p.source_record_id=m.application_source_record_id
        ) SELECT * FROM activity WHERE settlement_date<=?
          AND (?='' OR year(settlement_date)=CAST(? AS INTEGER))
          ORDER BY settlement_date DESC,entry_id DESC'''
        year = data['year_filter']
        data.update(paged(request,connection,activity,[*params,data['analysis_cutoff'],year,year or '0']))
    return render(request,f'dashboard/{group_kind}.html',data)
