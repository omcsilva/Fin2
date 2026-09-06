"""Operational Fin2 ledger pages and explicit Fin1 archive routes."""
from django.http import Http404
from django.shortcuts import render
from fin2.dashboard.views import context, page_view, paged, query


@page_view
def cash(request, connection):
    data = context(request, connection)
    batch = data['batch']['batch_id']
    account = request.GET.get('account', '')
    currency = request.GET.get('currency', '')[:20]
    if account and not account.isdecimal():
        raise Http404('Conta inválida')
    portfolio = data['portfolio_filter']
    scope = """a.batch_id=? AND (?='' OR EXISTS (
        SELECT 1 FROM portfolio.application ap JOIN portfolio.membership pm
        ON pm.batch_id=ap.batch_id AND pm.application_id=ap.legacy_id
        WHERE ap.batch_id=a.batch_id AND ap.account_id=a.legacy_id
        AND CAST(pm.collection_id AS VARCHAR)=?))"""
    accounts = query(connection, 'SELECT a.* FROM portfolio.account a WHERE '+scope,
                     [batch, portfolio, portfolio])
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
    params = [batch,portfolio,portfolio,data['analysis_cutoff']]
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
    return render(request,'dashboard/cash.html',data)


def historical(view):
    def archived(request, *args, **kwargs):
        request.fin1_history = True
        return view(request, *args, **kwargs)
    return archived
