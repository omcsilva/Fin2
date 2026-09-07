import hashlib
import json
import re
from decimal import Decimal
from datetime import date
from functools import wraps
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlencode

from django.conf import settings
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_safe, require_POST

from warehouse.repositories.dashboard import Unavailable, query, reader
from fin2.portfolio.price_jobs import (create as create_price_job,cancel as cancel_price_job,
  recover_interrupted,set_update_method)
from fin2.portfolio.manual_ledger import (create as create_manual_event,reverse as reverse_event,
  create_transfer,reverse_transfer,correct as correct_event)
from fin2.portfolio.cash_flow_decisions import create as create_cash_flow_decision
from fin2.dashboard.report_scope import scoped_connection
from fin2.portfolio.current_account import investment_balances, summarize as summarize_current_account
from fin2.imports.generic import stage as stage_file_import, commit as commit_import, reject as reject_import

ISSUES = {
    "account_mismatch": "Contas divergentes", "cash_without_account": "Lançamento sem conta",
    "future_movement": "Data futura", "movement_without_cash": "Movimentação sem lançamento",
    "unclassified_document": "Documento não classificado", "unsettled_movement": "Sem liquidação",
    "missing_document": "Documento ausente",
}

VALUATION_STATUS = {
    'quantity_review':'Quantidade a revisar','negative_quantity':'Quantidade negativa',
    'closed':'Posição zerada','missing_currency':'Moeda ausente','missing_price':'Cotação ausente ou inválida',
    'missing_price_date':'Data da cotação ausente','future_price':'Cotação posterior ao corte',
    'stale_price':'Cotação antiga (>30 dias)','priced':'Cotação disponível',
}


def page_view(function):
    @require_safe
    @wraps(function)
    def wrapped(request, *args, **kwargs):
        try:
            with reader(settings.WAREHOUSE_PATH) as connection:
                return function(request, scoped_connection(connection,request.GET.get('include_zeroed') == '1'), *args, **kwargs)
        except Unavailable:
            return render(request, "dashboard/unavailable.html", status=503)
    return wrapped


def context(request, connection, batch_id=None):
    batches = query(connection, "SELECT batch_id, as_of_date, imported_at FROM import_batch ORDER BY imported_at DESC, batch_id")
    selected = batch_id or request.GET.get("batch") or (batches[0]["batch_id"] if batches else None)
    historical = getattr(request, 'fin1_history', False)
    batch = next((b for b in batches if b["batch_id"] == selected), None)
    if not batch:
        if selected:
            raise Http404("Lote não encontrado")
        raise Unavailable("No imported batches")
    collections = query(connection, "SELECT legacy_id,name FROM portfolio.collection WHERE batch_id=? ORDER BY name,legacy_id", [selected])
    portfolio = request.GET.get('portfolio','')
    if portfolio and (not portfolio.isdecimal() or not any(str(c['legacy_id']) == portfolio for c in collections)):
        raise Http404('Carteira não encontrada')
    years = [r[0] for r in connection.execute("""
        SELECT DISTINCT y FROM (
          SELECT year(settlement_date) y FROM portfolio.movement WHERE batch_id=?
          UNION ALL SELECT year(settlement_date) FROM portfolio.cash_entry WHERE batch_id=?
          UNION ALL SELECT year(as_of_date) FROM import_batch WHERE batch_id=?
        ) WHERE y IS NOT NULL ORDER BY y DESC
        """, [selected,selected,selected]).fetchall()]
    if not historical:
        years = sorted(set(years + [date.today().year] + [r[0] for r in connection.execute(
            '''SELECT DISTINCT year(m.settlement_date) FROM ledger.manual_event m
               JOIN portfolio.account a ON a.source_record_id=m.account_source_record_id
               WHERE a.batch_id=?''', [selected]).fetchall()]), reverse=True)
    year = request.GET.get('year','')
    if year and (not re.fullmatch(r'\d{4}',year) or int(year) not in years):
        raise Http404('Ano não encontrado')
    global_query = urlencode({k:v for k,v in [('batch',selected),('portfolio',portfolio),('year',year),('include_zeroed','1' if request.GET.get('include_zeroed') == '1' else '')] if v})
    selected_collection = next((c for c in collections if str(c['legacy_id'])==portfolio),None)
    latest_price_update=connection.execute("SELECT last_successful_at FROM market.price_update_state WHERE state_key='assets'").fetchone()[0]
    latest_job=query(connection,"SELECT * FROM price_update_job ORDER BY created_at DESC LIMIT 1")
    return {"include_zeroed": request.GET.get("include_zeroed") == "1", "historical": historical, "batches": batches, "batch": batch, "collections":collections,
            "portfolio_filter":portfolio,"selected_collection":selected_collection,
            "years":years,"year_filter":year,"global_query":global_query,
            "analysis_cutoff": date(int(year),12,31) if year else (batch['as_of_date'] if historical else max(batch['as_of_date'],date.today())),
            "last_price_update":latest_price_update,"latest_price_job":latest_job[0] if latest_job else None}


def one(connection, table, key, identifier):
    # Table/key arguments are developer constants, never request parameters.
    if not re.fullmatch(r"[a-f0-9]{64}", identifier):
        raise Http404
    rows = query(connection, f"SELECT * FROM {table} WHERE {key}=?", [identifier])
    if not rows:
        raise Http404
    return rows[0]


def paged(request, connection, sql, parameters):
    count = connection.execute("SELECT count(*) FROM (" + sql + ") AS matching", parameters).fetchone()[0]
    page = Paginator(range(count), 50).get_page(request.GET.get("page"))
    rows = query(connection, sql + " LIMIT ? OFFSET ?", [*parameters, 50, (page.number - 1) * 50])
    params = request.GET.copy()
    params.pop("page", None)
    return {"rows": rows, "page": page, "query_string": params.urlencode()}


def table_order(request, allowed, default):
    """Allowlisted SQL ordering and state for the shared table controls."""
    selected=request.GET.get('sort','')
    if selected not in allowed:
        selected=default
    direction=request.GET.get('dir','asc').lower()
    if direction not in ('asc','desc'):
        direction='asc'
    return allowed[selected]+' '+direction.upper(),{'table_sort':selected,'table_direction':direction}


def valuation_query(data):
    """Parameterized positions at the chosen year-end and portfolio."""
    sql = """
    WITH annual AS (
      SELECT a.batch_id,a.legacy_id AS application_id,
        count(m.legacy_id) FILTER(WHERE m.settlement_date<=?) AS movement_count,
        count(m.legacy_id) FILTER(WHERE m.settlement_date<=? AND (m.source_quantity IS NULL OR o.quantity_multiplier IS NULL)) AS incomplete_count,
        sum(abs(m.source_quantity)*o.quantity_multiplier) FILTER(WHERE m.settlement_date<=?) AS quantity
      FROM portfolio.application a
      LEFT JOIN portfolio.movement m ON m.batch_id=a.batch_id AND m.application_id=a.legacy_id
      LEFT JOIN portfolio.operation o ON o.batch_id=m.batch_id AND o.legacy_id=m.operation_id
      WHERE a.batch_id=? GROUP BY a.batch_id,a.legacy_id
    ), manual_quantity AS (
      SELECT me.application_source_record_id,
        sum(coalesce(me.quantity,0) *
          CASE coalesce(original.event_type,me.event_type)
            WHEN 'buy' THEN 1 WHEN 'sell' THEN -1 WHEN 'redemption' THEN -1
            ELSE 0 END * CASE WHEN me.reverses_event_id IS NULL THEN 1 ELSE -1 END) quantity,
        count(*) FILTER(WHERE me.event_type='adjustment' AND me.reverses_event_id IS NULL
          AND me.quantity IS NOT NULL) incomplete_count
      FROM ledger.manual_event me
      LEFT JOIN ledger.manual_event original ON original.event_id=me.reverses_event_id
      WHERE me.settlement_date<=?
      GROUP BY me.application_source_record_id
    ), scoped AS (
      SELECT p.* EXCLUDE(quantity_at_cutoff,movement_count,incomplete_count,legacy_delta,legacy_price,price_date),
        CASE WHEN d.status='resolved' AND d.quantity_override IS NOT NULL AND d.effective_date<=?
             THEN d.quantity_override + coalesce(mq.quantity,0)
             WHEN coalesce(y.incomplete_count,0)=0 THEN coalesce(y.quantity,0) + coalesce(mq.quantity,0) END AS quantity_at_cutoff,
        coalesce(y.movement_count,0) AS movement_count,
        coalesce(y.incomplete_count,0)+coalesce(mq.incomplete_count,0) AS incomplete_count,
        coalesce(d.status='resolved' AND d.quantity_override IS NOT NULL AND d.effective_date<=?,false) decision_applied,
        CASE WHEN ?='' THEN p.legacy_delta END AS legacy_delta,
        coalesce(ep.price,p.legacy_price) AS legacy_price,
        coalesce(CAST(ep.quoted_at AS DATE),p.price_date) AS price_date,
        coalesce(ep.provider,'fin1_snapshot') AS price_source,
        CASE WHEN ep.provider<>'fin1_snapshot' THEN ep.captured_at END AS price_consulted_at
      FROM portfolio.position p JOIN annual y ON y.batch_id=p.batch_id AND y.application_id=p.legacy_id
      LEFT JOIN manual_quantity mq ON mq.application_source_record_id=p.source_record_id
      LEFT JOIN ledger.reconciliation_decision d ON d.batch_id=p.batch_id
        AND d.subject_type='application' AND d.subject_id=p.legacy_id
      LEFT JOIN market.asset_catalog_effective ma ON ma.batch_id=p.batch_id AND ma.legacy_id=p.asset_id
      LEFT JOIN LATERAL (
        SELECT * FROM market.ledger_price_observation px
        WHERE px.source_record_id=ma.source_record_id AND CAST(px.quoted_at AS DATE)<=?
        ORDER BY CAST(px.quoted_at AS DATE) DESC,px.captured_at DESC,px.capture_id DESC LIMIT 1
      ) ep ON true
      WHERE p.batch_id=? AND (?='' OR EXISTS (
        SELECT 1 FROM portfolio.membership pm WHERE pm.batch_id=p.batch_id
          AND pm.application_id=p.legacy_id AND CAST(pm.collection_id AS VARCHAR)=?))
    ), classified AS (
      SELECT *,date_diff('day',price_date,?) AS price_age_days,
       CASE WHEN incomplete_count>0 OR quantity_at_cutoff IS NULL OR (?='' AND NOT decision_applied AND (legacy_delta IS NULL OR legacy_delta<>0)) THEN 'quantity_review'
        WHEN quantity_at_cutoff<0 THEN 'negative_quantity' WHEN quantity_at_cutoff=0 THEN 'closed'
        WHEN currency IS NULL OR trim(currency)='' THEN 'missing_currency'
        WHEN legacy_price IS NULL OR legacy_price<=0 THEN 'missing_price'
        WHEN price_date IS NULL THEN 'missing_price_date' WHEN price_date>? THEN 'future_price'
        WHEN date_diff('day',price_date,?)>30 THEN 'stale_price' ELSE 'priced' END AS valuation_status
      FROM scoped
    )
    SELECT *,CASE WHEN valuation_status IN ('priced','stale_price')
      THEN CAST(quantity_at_cutoff*legacy_price AS DECIMAL(38,10)) END AS reference_value
    FROM classified
    """
    if data.get('historical'):
        sql = sql.replace('WHERE me.settlement_date<=?', 'WHERE me.settlement_date<=? AND false')
        sql = sql.replace('px.source_record_id=ma.source_record_id AND', 'px.source_record_id=ma.source_record_id AND false AND')
    cutoff=data['analysis_cutoff']; batch=data['batch']['batch_id']; portfolio=data['portfolio_filter']
    year=data['year_filter']
    return sql,[cutoff,cutoff,cutoff,batch,cutoff,cutoff,cutoff,year,cutoff,batch,portfolio,portfolio,cutoff,year,cutoff,cutoff]


def add_current_account(connection, data):
    """Share the consolidated result across overview and reports."""
    if not data['portfolio_filter'] and not data.get('historical'):
        valuation_sql, valuation_parameters = valuation_query(data)
        positions = query(connection, valuation_sql, valuation_parameters)
        data['investment_balances'] = investment_balances(connection, data['batch']['batch_id'], data['analysis_cutoff'])
        data['current_account'] = summarize_current_account(connection, data['batch']['batch_id'],
            data['analysis_cutoff'], positions, data['investment_balances'])


@page_view
def overview(request, connection):
    data = context(request, connection)
    add_current_account(connection, data)
    batch = data["batch"]["batch_id"]
    data["counts"] = [(label, connection.execute(f"SELECT count(*) FROM {table} WHERE batch_id=?", [batch]).fetchone()[0])
                      for label,table in [("Registros legados","source_record"),("Documentos","source_document"),("Sinalizações","import_issue")]]
    data["tables"] = query(connection, "SELECT database_name,table_name,row_count FROM source_table WHERE batch_id=? ORDER BY database_name,table_name", [batch])
    data["issues"] = query(connection, "SELECT code,count(*) AS count FROM import_issue WHERE batch_id=? GROUP BY code ORDER BY count DESC", [batch])
    portfolio=data['portfolio_filter']; year=data['year_filter']
    applications=connection.execute("""SELECT count(*) FROM portfolio.application a WHERE a.batch_id=? AND (?='' OR EXISTS(
      SELECT 1 FROM portfolio.membership m WHERE m.batch_id=a.batch_id AND m.application_id=a.legacy_id AND CAST(m.collection_id AS VARCHAR)=?))""",[batch,portfolio,portfolio]).fetchone()[0]
    movements=connection.execute("""SELECT count(*) FROM portfolio.movement m WHERE m.batch_id=? AND (?='' OR year(coalesce(m.settlement_date,m.trade_date))=CAST(? AS INTEGER)) AND (?='' OR EXISTS(
      SELECT 1 FROM portfolio.membership pm WHERE pm.batch_id=m.batch_id AND pm.application_id=m.application_id AND CAST(pm.collection_id AS VARCHAR)=?))""",[batch,year,year or '0',portfolio,portfolio]).fetchone()[0]
    if not data.get('historical'):
        movements += connection.execute('''SELECT count(*) FROM ledger.manual_event m
          JOIN portfolio.account a ON a.source_record_id=m.account_source_record_id
          LEFT JOIN portfolio.application ap ON ap.source_record_id=m.application_source_record_id
          WHERE a.batch_id=? AND m.settlement_date<=?
          AND (?='' OR year(m.settlement_date)=CAST(? AS INTEGER))
          AND (?='' OR EXISTS(SELECT 1 FROM portfolio.membership pm WHERE pm.batch_id=a.batch_id
            AND pm.application_id=ap.legacy_id AND CAST(pm.collection_id AS VARCHAR)=?))''',
          [batch,data['analysis_cutoff'],year,year or '0',portfolio,portfolio]).fetchone()[0]
    data['analysis_counts']=[('Aplicações',applications),('Movimentações no período',movements)]
    scoped,parameters=valuation_query(data)
    position_totals=query(connection,"""SELECT currency,sum(reference_value) position_value,
      count(*) FILTER(WHERE valuation_status<>'closed') active_count,
      count(reference_value) priced_count,
      count(*) FILTER(WHERE valuation_status NOT IN ('closed','priced','stale_price')) excluded_count,
      count(*) FILTER(WHERE valuation_status='stale_price') stale_count
      FROM ("""+scoped+") v GROUP BY currency ORDER BY currency",parameters)
    cash_totals=query(connection,"""SELECT e.currency,sum(e.amount) cash_value,
      count(*) FILTER(WHERE e.amount IS NULL) incomplete_count
      FROM ledger.investment_cash_entry e JOIN portfolio.account a
        ON a.source_record_id=e.account_source_record_id
      WHERE e.batch_id=? AND e.settlement_date<=? AND (?='' OR EXISTS(
        SELECT 1 FROM portfolio.application ap JOIN portfolio.membership m
          ON m.batch_id=ap.batch_id AND m.application_id=ap.legacy_id
        WHERE ap.batch_id=a.batch_id AND ap.account_id=a.legacy_id
          AND CAST(m.collection_id AS VARCHAR)=?))
      GROUP BY e.currency ORDER BY e.currency""",[batch,data['analysis_cutoff'],portfolio,portfolio])
    if data.get('historical'):
        cash_totals = query(connection,'''SELECT c.abbreviation currency,sum(e.signed_amount) cash_value,
          count(*) FILTER(WHERE e.signed_amount IS NULL) incomplete_count
          FROM ledger.cash_entry_canonical e JOIN portfolio.account a
            ON a.batch_id=e.batch_id AND a.legacy_id=e.account_id
          LEFT JOIN portfolio.currency c ON c.batch_id=a.batch_id AND c.legacy_id=a.currency_id
          WHERE e.batch_id=? AND e.settlement_date<=?
          AND (?='' OR EXISTS(SELECT 1 FROM portfolio.application ap JOIN portfolio.membership pm
            ON pm.batch_id=ap.batch_id AND pm.application_id=ap.legacy_id
            WHERE ap.batch_id=a.batch_id AND ap.account_id=a.legacy_id AND CAST(pm.collection_id AS VARCHAR)=?))
          GROUP BY c.abbreviation''',[batch,data['analysis_cutoff'],portfolio,portfolio])
    currency_aliases = {'BRL':'REAL','USD':'DOL','DOLAR':'DOL'}
    normalized_cash = {}
    for row in cash_totals:
        currency = currency_aliases.get(row['currency'],row['currency'])
        total = normalized_cash.setdefault(currency,dict(currency=currency,cash_value=Decimal(0),incomplete_count=0))
        total['cash_value'] += row['cash_value'] or Decimal(0)
        total['incomplete_count'] += row['incomplete_count']
    cash_totals = list(normalized_cash.values())
    by_currency={}
    for row in position_totals:
        by_currency[row['currency']]=dict(row)
    for row in cash_totals:
        by_currency.setdefault(row['currency'],{'currency':row['currency'],'position_value':None,
          'active_count':0,'priced_count':0,'excluded_count':0,'stale_count':0}).update(
          cash_value=row['cash_value'],cash_incomplete=row['incomplete_count'])
    for row in by_currency.values():
        row.setdefault('cash_value',None);row.setdefault('cash_incomplete',0)
        if row['position_value'] is not None and row['cash_value'] is not None:
            row['combined_value']=row['position_value']+row['cash_value']
        elif row['position_value'] is not None:
            row['combined_value']=row['position_value']
        else:
            row['combined_value']=row['cash_value']
    data['financial_summary']=sorted(by_currency.values(),key=lambda item:item['currency'] or '')
    data['warning_count']=sum(r['excluded_count']+r['stale_count']+r['cash_incomplete'] for r in data['financial_summary'])
    for item in data["issues"]:
        item["label"] = ISSUES.get(item["code"], item["code"])
    return render(request, 'dashboard/legacy_overview.html' if data.get('historical') else 'dashboard/overview.html', data)


@page_view
def positions(request, connection):
    data = context(request, connection)
    batch = data['batch']['batch_id']
    term = request.GET.get('q','')[:200]
    account = request.GET.get('account','')
    if account and not account.isdecimal():
        raise Http404('Conta inválida')
    order,state=table_order(request,{'asset':'asset_name','account':'account_name','currency':'currency','status':'valuation_status'},'asset')
    data.update(term=term,account_filter=account,**state)
    data['accounts'] = query(connection,'SELECT legacy_id,name FROM portfolio.account WHERE batch_id=? ORDER BY name',[batch])
    data['quantity_flags'] = connection.execute("""SELECT count(*) FROM portfolio.quantity_check q WHERE q.batch_id=?
      AND (?='' OR EXISTS(SELECT 1 FROM portfolio.membership pm WHERE pm.batch_id=q.batch_id AND pm.application_id=q.application_id AND CAST(pm.collection_id AS VARCHAR)=?))
      AND (q.legacy_delta<>0 OR q.legacy_delta IS NULL)""",[batch,data['portfolio_filter'],data['portfolio_filter']]).fetchone()[0]
    scoped,parameters=valuation_query(data)
    filtered="SELECT * FROM ("+scoped+") scoped_positions WHERE (?='' OR CAST(account_id AS VARCHAR)=?) AND (?='' OR concat_ws(' ',asset_name,name,account_name,class_name,currency) ILIKE ?)"
    filter_parameters=[*parameters,account,account,term,'%'+term+'%']
    data['position_totals']=query(connection,"SELECT currency,sum(reference_value) position_value FROM ("+filtered+") filtered_positions GROUP BY currency ORDER BY currency",filter_parameters)
    data['position_count']=connection.execute("SELECT count(*) FROM ("+filtered+") filtered_positions",filter_parameters).fetchone()[0]
    data.update(paged(request,connection,filtered+" ORDER BY "+order+",legacy_id",filter_parameters))
    for row in data['rows']:
        row['status_label'] = VALUATION_STATUS.get(row['valuation_status'], row['valuation_status'])
    return render(request,'dashboard/legacy_positions.html' if data.get('historical') else 'dashboard/positions.html',data)


@page_view
def allocation(request,connection):
    data=context(request,connection)
    batch=data['batch']['batch_id']
    currency=request.GET.get('currency','')[:20]
    term=request.GET.get('q','')[:200]
    order,state=table_order(request,{'asset':'asset_name','account':'account_name','currency':'currency','value':'reference_value','status':'valuation_status'},'currency')
    data.update(currency_filter=currency,term=term,**state)
    scoped,parameters=valuation_query(data)
    data['currencies']=query(connection,"SELECT DISTINCT currency FROM ("+scoped+") v WHERE valuation_status<>'closed' ORDER BY currency",parameters)
    totals_sql="""SELECT currency,count(*) AS active_count,count(reference_value) AS priced_count,
      count(*) FILTER(WHERE valuation_status NOT IN ('priced','stale_price')) AS excluded_count,
      count(*) FILTER(WHERE valuation_status='stale_price') AS stale_count,sum(reference_value) AS reference_subtotal
      FROM ("""+scoped+") v WHERE valuation_status<>'closed' AND (?='' OR currency=?) AND (?='' OR concat_ws(' ',asset_name,name,account_name,class_name) ILIKE ?) GROUP BY currency ORDER BY currency"
    data['totals']=query(connection,totals_sql,[*parameters,currency,currency,term,'%'+term+'%'])
    allocation_sql="""WITH groups AS (SELECT currency,coalesce(class_name,'Sem classe') class_name,
      sum(reference_value) reference_value FROM ("""+scoped+") v WHERE reference_value IS NOT NULL AND (?='' OR currency=?) AND (?='' OR concat_ws(' ',asset_name,name,account_name,class_name) ILIKE ?) GROUP BY currency,coalesce(class_name,'Sem classe')) " + \
      "SELECT *,100.0*reference_value/nullif(sum(reference_value) OVER(PARTITION BY currency),0) percentage FROM groups ORDER BY currency,reference_value DESC"
    data['allocation']=query(connection,allocation_sql,[*parameters,currency,currency,term,'%'+term+'%'])
    data.update(paged(request,connection,"SELECT * FROM ("+scoped+") v WHERE valuation_status<>'closed' AND (?='' OR currency=?) AND (?='' OR concat_ws(' ',asset_name,name,account_name,class_name) ILIKE ?) ORDER BY "+order+",legacy_id",[*parameters,currency,currency,term,'%'+term+'%']))
    for row in data['rows']:
        row['status_label']=VALUATION_STATUS.get(row['valuation_status'],row['valuation_status'])
    return render(request,'dashboard/legacy_allocation.html' if data.get('historical') else 'dashboard/allocation.html',data)


def _normalized_series(rows):
    """Return monthly, base-100 points; rate series are compounded."""
    if not rows:
        return []
    rate_units={'percent_per_day','percent_per_month'}
    unit=rows[0]['unit']; accumulated=Decimal('100'); base=Decimal(str(rows[0]['value']))
    daily=[]
    for row in rows:
        value=Decimal(str(row['value']))
        if unit in rate_units:
            accumulated *= Decimal('1') + value / Decimal('100')
            normalized=accumulated
        else:
            normalized=Decimal('100') * value / base
        daily.append((row['observation_date'],float(normalized)))
    monthly={}
    for point in daily:
        monthly[(point[0].year,point[0].month)]=point
    return list(monthly.values())


def _xirr(flows):
    """Annualized money-weighted return for conventional dated cash flows."""
    flows=[(day,float(value)) for day,value in flows if value]
    if len(flows)<2 or not any(v<0 for _,v in flows) or not any(v>0 for _,v in flows):
        return None
    origin=min(day for day,_ in flows)
    def npv(rate):
        return sum(value/(1+rate)**((day-origin).days/365.0) for day,value in flows)
    low=-.9999; high=1.0; left=npv(low); right=npv(high)
    while left*right>0 and high<1_000_000:
        high*=10; right=npv(high)
    if left*right>0:
        return None
    for _ in range(160):
        middle=(low+high)/2; value=npv(middle)
        if abs(value)<1e-7: return middle
        if left*value<=0: high=middle
        else: low=middle;left=value
    return (low+high)/2


def _average_cost(events, cutoff, report_year=None):
    """Brazilian moving-average estimate for simple quantity-bearing trades."""
    quantity=Decimal('0'); cost=Decimal('0'); realized=Decimal('0'); sale_proceeds=Decimal('0')
    buy_count=sale_count=unallocated_count=0;allocated_expenses=Decimal('0');sale_details=[]
    by_day={}
    for event in events:
        day=event['event_date']
        if day and day<=cutoff: by_day.setdefault(day,[]).append(event)
    for day, daily_events in sorted(by_day.items()):
        buys=[];sales=[]
        for event in daily_events:
            operation=str(event['operation'] or '').lower()
            qty=abs(Decimal(str(event['quantity'] or 0)))
            amount=abs(Decimal(str(event['amount'] or 0)))
            gross=abs(Decimal(str(event.get('gross_amount') or amount)))
            if not event.get('allocated_cash',True): unallocated_count+=1
            if operation in ('compra','buy'):
                if qty<=0 or amount<=0: return {'status':'missing_trade_detail'}
                buys.append((qty,amount,gross));buy_count+=1
            elif operation in ('venda','sell','resgate','redemption'):
                if qty<=0: return {'status':'missing_trade_detail'}
                sales.append((qty,amount,gross));sale_count+=1
            elif qty and operation not in ('rendimento','dividendo','juros c p','imposto','taxa'):
                return {'status':'unsupported_operation'}
        buy_qty=sum((row[0] for row in buys),Decimal('0'))
        buy_amount=sum((row[1] for row in buys),Decimal('0'))
        buy_gross=sum((row[2] for row in buys),Decimal('0'))
        sell_qty=sum((row[0] for row in sales),Decimal('0'))
        sell_amount=sum((row[1] for row in sales),Decimal('0'))
        sell_gross=sum((row[2] for row in sales),Decimal('0'))
        allocated_expenses+=(buy_amount-buy_gross)+(sell_gross-sell_amount)

        # The quantity bought and sold in the same session is day trade and
        # does not consume the position held before that session.
        day_trade_qty=min(buy_qty,sell_qty)
        if day_trade_qty:
            day_buy_cost=buy_amount*day_trade_qty/buy_qty
            day_proceeds=sell_amount*day_trade_qty/sell_qty
            day_gain=day_proceeds-day_buy_cost
            if report_year is None or day.year==report_year:
                realized+=day_gain;sale_proceeds+=day_proceeds
            sale_details.append({'date':day,'proceeds':day_proceeds,'gain':day_gain,
                                 'tax_group':'day_trade','quantity':day_trade_qty})
        remaining_buy=buy_qty-day_trade_qty
        if remaining_buy:
            quantity+=remaining_buy;cost+=buy_amount*remaining_buy/buy_qty
        remaining_sale=sell_qty-day_trade_qty
        if remaining_sale:
            if quantity<remaining_sale: return {'status':'insufficient_quantity'}
            proceeds=sell_amount*remaining_sale/sell_qty
            allocated=cost*remaining_sale/quantity
            gain=proceeds-allocated
            if report_year is None or day.year==report_year:
                realized+=gain;sale_proceeds+=proceeds
            sale_details.append({'date':day,'proceeds':proceeds,'gain':gain,
                                 'tax_group':'common','quantity':remaining_sale})
            cost-=allocated;quantity-=remaining_sale
    return {'status':'calculated','quantity':quantity,'cost_balance':cost,
      'average_cost':cost/quantity if quantity else None,'realized_gain':realized,
      'sale_proceeds':sale_proceeds,'buy_count':buy_count,'sale_count':sale_count,
      'allocated_expenses':allocated_expenses,'unallocated_count':unallocated_count,
      'sale_details':sale_details}


@page_view
def history(request,connection):
    data=context(request,connection);batch=data['batch']['batch_id'];portfolio=data['portfolio_filter']
    start=date(int(data['year_filter']),1,1) if data['year_filter'] else date(2000,1,1)
    end=data['analysis_cutoff']
    catalogs=query(connection,"""SELECT v.benchmark_source_record_id series_id,c.abbreviation code,c.name,
       v.unit,v.provider FROM market.benchmark_value v JOIN market.benchmark_catalog c
       ON c.source_record_id=v.benchmark_source_record_id
       WHERE v.observation_date BETWEEN ? AND ? GROUP BY ALL ORDER BY code""",[start,end])
    catalogs+=query(connection,"""SELECT d.series_id,a.symbol code,a.name,d.unit,d.provider
       FROM market.comparison_series d JOIN market.asset_catalog_effective a ON a.source_record_id=d.series_id
       WHERE d.observation_date BETWEEN ? AND ? AND a.batch_id=? AND EXISTS(
        SELECT 1 FROM portfolio.application ap LEFT JOIN portfolio.membership m
          ON m.batch_id=ap.batch_id AND m.application_id=ap.legacy_id
        WHERE ap.batch_id=a.batch_id AND ap.asset_id=a.legacy_id
          AND (?='' OR CAST(m.collection_id AS VARCHAR)=?))
       GROUP BY ALL ORDER BY code""",[start,end,batch,portfolio,portfolio])
    requested=request.GET.getlist('series')[:8]
    available={r['series_id']:r for r in catalogs}
    if not requested:
        requested=[r['series_id'] for r in catalogs if r['provider']=='bcb_sgs'][:6]
    requested=[item for item in requested if item in available]
    colors=['#62dce8','#d7b45a','#8b9cff','#ee7a8c','#7fd18b','#dc86e8','#ef9858','#b7c4d2']
    chart=[]
    for identifier,color in zip(requested,colors):
        rows=query(connection,"""SELECT observation_date,value,unit FROM market.comparison_series
          WHERE series_id=? AND observation_date BETWEEN ? AND ? ORDER BY observation_date""",[identifier,start,end])
        points=_normalized_series(rows)
        if points:
            item=dict(available[identifier]);item.update(color=color,points=points,first=rows[0]['observation_date'],last=rows[-1]['observation_date'],last_value=points[-1][1]);chart.append(item)
    all_points=[p for series in chart for p in series['points']]
    if all_points:
        minimum=min(p[1] for p in all_points);maximum=max(p[1] for p in all_points);span=max(maximum-minimum,1)
        dates=[p[0] for p in all_points];first=min(dates);last=max(dates);days=max((last-first).days,1)
        for series in chart:
            series['polyline']=' '.join(f"{40+720*(d-first).days/days:.1f},{20+260*(maximum-v)/span:.1f}" for d,v in series['points'])
        data.update(chart_min=minimum,chart_max=maximum,chart_first=first,chart_last=last)
    data.update(series_catalog=catalogs,selected_series=requested,chart_series=chart,history_start=start,history_end=end)
    return render(request,'dashboard/history.html',data)


@page_view
def prices(request, connection):
    data = context(request, connection)
    batch = data['batch']['batch_id']
    term = request.GET.get('q', '')[:200]
    method = request.GET.get('method', '')[:10]
    if method not in ('', 'BRAPI', 'NENHUM'):
        method = ''
    order,state=table_order(request,{'asset':'a.name','symbol':'a.symbol','provider':'a.configured_provider','price':'coalesce(ep.price,a.legacy_price)','date':'coalesce(CAST(ep.quoted_at AS DATE),a.price_date)','quality':'p.quality'},'asset')
    data.update(term=term, method_filter=method,**state)
    asset_scope="""(?='' OR EXISTS(SELECT 1 FROM portfolio.application ap JOIN portfolio.membership pm ON pm.batch_id=ap.batch_id AND pm.application_id=ap.legacy_id WHERE ap.batch_id=a.batch_id AND ap.asset_id=a.legacy_id AND CAST(pm.collection_id AS VARCHAR)=?))"""
    data['quality'] = query(connection, 'SELECT quality,count(*) AS count FROM market.price_observation p JOIN market.asset_catalog a ON a.source_record_id=p.source_record_id WHERE p.batch_id=? AND '+asset_scope+' GROUP BY quality ORDER BY quality', [batch,data['portfolio_filter'],data['portfolio_filter']])
    labels = {'missing_price':'Sem preço','invalid_price':'Preço inválido','missing_currency':'Sem moeda',
              'missing_date':'Sem data','future_price':'Posterior ao corte','stale_price':'Antiga (>30 dias)', 'available':'Disponível no corte'}
    for row in data['quality']:
        row['label'] = labels[row['quality']]
    data['identifiers'] = connection.execute('SELECT count(*) FROM market.identifier_candidate i JOIN market.asset_catalog a ON a.source_record_id=i.source_record_id WHERE i.batch_id=? AND '+asset_scope, [batch,data['portfolio_filter'],data['portfolio_filter']]).fetchone()[0]
    data['duplicates'] = connection.execute('SELECT count(*) FROM market.identifier_candidate i JOIN market.asset_catalog a ON a.source_record_id=i.source_record_id WHERE i.batch_id=? AND i.occurrences>1 AND '+asset_scope, [batch,data['portfolio_filter'],data['portfolio_filter']]).fetchone()[0]
    data.update(paged(request, connection, """
        SELECT a.*,p.quality,p.age_at_cutoff_days,p.captured_at,u.method update_method,
          coalesce(ep.price,a.legacy_price) display_price,
          coalesce(CAST(ep.quoted_at AS DATE),a.price_date) display_price_date,
          coalesce(ep.provider,'fin1_snapshot') display_price_source,
          CASE WHEN ep.provider<>'fin1_snapshot' THEN ep.captured_at END last_successful_query_at,
          (SELECT count(*) FROM market.identifier_candidate i WHERE i.source_record_id=a.source_record_id AND i.occurrences>1) AS duplicate_identifiers
        FROM market.asset_catalog_effective a JOIN market.price_observation p ON p.observation_id=a.source_record_id
        JOIN market.asset_price_update_method u ON u.source_record_id=a.source_record_id
        LEFT JOIN market.latest_ledger_price ep ON ep.source_record_id=a.source_record_id AND NOT ?
        WHERE a.batch_id=? AND (?='' OR u.method=?)
          AND (?='' OR EXISTS(SELECT 1 FROM portfolio.application ap JOIN portfolio.membership pm ON pm.batch_id=ap.batch_id AND pm.application_id=ap.legacy_id WHERE ap.batch_id=a.batch_id AND ap.asset_id=a.legacy_id AND CAST(pm.collection_id AS VARCHAR)=?))
          AND (?='' OR concat_ws(' ',a.name,a.symbol,a.legacy_code,a.legacy_cnpj) ILIKE ?)
        ORDER BY """+order+""",a.legacy_id
        """, [data.get('historical',False),batch,method,method,data['portfolio_filter'],data['portfolio_filter'],term,'%'+term+'%']))
    if not data.get('historical'):
        def effective_quality(row):
            price = row['display_price']; day = row['display_price_date']
            if not row.get('currency'): return 'missing_currency'
            if price is None: return 'missing_price'
            if price <= 0: return 'invalid_price'
            if day is None: return 'missing_date'
            if day > data['analysis_cutoff']: return 'future_price'
            return 'stale_price' if (data['analysis_cutoff']-day).days > 30 else 'available'
        effective_prices = query(connection,'''SELECT a.currency,
            coalesce(ep.price,a.legacy_price) display_price,
            coalesce(CAST(ep.quoted_at AS DATE),a.price_date) display_price_date
            FROM market.asset_catalog_effective a
            LEFT JOIN market.latest_ledger_price ep ON ep.source_record_id=a.source_record_id
            WHERE a.batch_id=? AND '''+asset_scope,[batch,data['portfolio_filter'],data['portfolio_filter']])
        counts = {}
        for row in effective_prices:
            quality = effective_quality(row)
            counts[quality] = counts.get(quality,0)+1
        data['quality'] = [dict(quality=k,count=v,label=labels[k]) for k,v in sorted(counts.items())]
        for row in data['rows']:
            row['quality'] = effective_quality(row)
            row['age_at_cutoff_days'] = (data['analysis_cutoff']-row['display_price_date']).days if row['display_price_date'] else None
    for row in data['rows']:
        row['quality_label'] = labels[row['quality']]
    return render(request, 'dashboard/legacy_prices.html' if data.get('historical') else 'dashboard/prices.html', data)


@page_view
def quote_captures(request,connection):
    data=context(request,connection);batch=data['batch']['batch_id']
    portfolio=data['portfolio_filter']
    data['captures']=query(connection,"""SELECT c.capture_id,c.requested_symbol,c.captured_at,c.quoted_at,
      c.price,c.currency,c.status,c.reason,c.source_record_id,a.name
      FROM market.quote_capture c JOIN source_record r ON r.record_id=c.source_record_id
      JOIN market.asset_catalog_effective a ON a.source_record_id=r.record_id
      WHERE r.batch_id=? AND (?='' OR EXISTS(SELECT 1 FROM portfolio.application ap
        JOIN portfolio.membership pm ON pm.batch_id=ap.batch_id AND pm.application_id=ap.legacy_id
        WHERE ap.batch_id=a.batch_id AND ap.asset_id=a.legacy_id AND CAST(pm.collection_id AS VARCHAR)=?))
      ORDER BY c.captured_at DESC,c.capture_id LIMIT 50""",[batch,portfolio,portfolio])
    return render(request,'dashboard/quote_captures.html',data)


@page_view
def quote_response(request, connection, identifier):
    item = one(connection,'market.quote_capture','capture_id',identifier)
    body = bytes(item['response_body'])
    if hashlib.sha256(body).hexdigest() != item['response_sha256']:
        raise Http404('Integridade não confirmada')
    response = HttpResponse(body,content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="brapi-{identifier}.json"'
    response['Content-Security-Policy'] = "sandbox; default-src 'none'; frame-ancestors 'self'"
    return response


@require_POST
def start_price_update(request):
    try:
        with reader(settings.WAREHOUSE_PATH) as connection:
            data=context(request,connection)
            batch=data['batch']['batch_id']
        job_id,created=create_price_job(settings.WAREHOUSE_PATH,batch,None)
        return JsonResponse({'job_id':job_id,'created':created},status=202)
    except (Unavailable,OSError):
        return JsonResponse({'error':'Banco indisponível para atualização'},status=503)


@require_POST
def cancel_price_update(request):
    try:
        job_id,cancelled=cancel_price_job(settings.WAREHOUSE_PATH)
        return JsonResponse({'job_id':job_id,'cancelled':cancelled})
    except (Unavailable,OSError):
        return JsonResponse({'error':'Banco indisponível para cancelamento'},status=503)


@require_POST
def price_update_method(request,identifier):
    try:
        with reader(settings.WAREHOUSE_PATH) as connection:
            data=context(request,connection);batch=data['batch']['batch_id']
        set_update_method(settings.WAREHOUSE_PATH,batch,identifier,request.POST.get('method',''))
        return redirect('/fin2/cotacoes/?'+data['global_query'])
    except ValueError as error:
        return HttpResponse(str(error),status=400)
    except Unavailable:
        return HttpResponse('Banco indisponível',status=503)


@require_safe
def price_update_status(request):
    try:
        with reader(settings.WAREHOUSE_PATH) as connection:
            rows=query(connection,"SELECT * FROM price_update_job ORDER BY created_at DESC LIMIT 1")
            last=connection.execute("SELECT last_successful_at FROM market.price_update_state WHERE state_key='assets'").fetchone()[0]
        if not rows:return JsonResponse({'status':'idle','message':'','last_price_update':last})
        if rows[0]['status'] in ('queued','running') and recover_interrupted(settings.WAREHOUSE_PATH,rows[0]['job_id']):
            with reader(settings.WAREHOUSE_PATH) as connection:
                rows=query(connection,"SELECT * FROM price_update_job WHERE job_id=?",[rows[0]['job_id']])
        result=rows[0];result['last_price_update']=last
        return JsonResponse(result)
    except Unavailable:
        return JsonResponse({'status':'unavailable','message':'Estado indisponível'},status=503)


@page_view
def quantity_detail(request, connection, identifier):
    item=one(connection,'source_record','record_id',identifier)
    if item['table_name']!='fin1_aplicacao' or item['database_name']!='db.sqlite3':
        raise Http404
    data=context(request,connection,item['batch_id'])
    scoped,parameters=valuation_query(data)
    positions=query(connection,'SELECT * FROM ('+scoped+') v WHERE source_record_id=?',[*parameters,identifier])
    if not positions:
        raise Http404('Aplicação fora da carteira selecionada')
    data['position']=positions[0]
    if not data.get('historical'):
        activity = """WITH activity AS (
          SELECT q.source_record_id entry_id,q.settlement_date,q.operation_name operation,
            q.signed_quantity, 'Importado' origin
          FROM portfolio.quantity_detail q WHERE q.batch_id=? AND q.application_id=?
          UNION ALL
          SELECT me.event_id,me.settlement_date,me.event_type,
            coalesce(me.quantity,0) * CASE coalesce(original.event_type,me.event_type)
              WHEN 'buy' THEN 1 WHEN 'sell' THEN -1 WHEN 'redemption' THEN -1 ELSE 0 END
              * CASE WHEN me.reverses_event_id IS NULL THEN 1 ELSE -1 END,'Fin2'
          FROM ledger.manual_event me
          LEFT JOIN ledger.manual_event original ON original.event_id=me.reverses_event_id
          WHERE me.application_source_record_id=?
        ) SELECT * FROM activity WHERE settlement_date<=?
          AND (?='' OR year(settlement_date)=CAST(? AS INTEGER))
          ORDER BY settlement_date DESC,entry_id DESC"""
        data.update(paged(request,connection,activity,[item['batch_id'],item['legacy_id'],identifier,
          data['analysis_cutoff'],data['year_filter'],data['year_filter'] or '0']))
        return render(request,'dashboard/quantity_detail.html',data)
    data.update(paged(request,connection,"SELECT * FROM portfolio.quantity_detail WHERE batch_id=? AND application_id=? AND (?='' OR year(coalesce(settlement_date,trade_date))=CAST(? AS INTEGER)) ORDER BY settlement_date NULLS LAST,trade_date,legacy_id",[item['batch_id'],item['legacy_id'],data['year_filter'],data['year_filter'] or '0']))
    return render(request,'dashboard/legacy_quantity_detail.html' if data.get('historical') else 'dashboard/quantity_detail.html',data)


@page_view
def legacy_cash(request,connection):
    data=context(request,connection)
    batch=data['batch']['batch_id']
    account=request.GET.get('account','')
    if account and not account.isdecimal():
        raise Http404('Conta inválida')
    currency=request.GET.get('currency','')[:20]
    data.update(account_filter=account,currency_filter=currency)
    data['currencies']=query(connection,'SELECT DISTINCT currency FROM ledger.cash_dashboard WHERE batch_id=? ORDER BY currency',[batch])
    scope="""(?='' OR EXISTS(SELECT 1 FROM portfolio.application ap JOIN portfolio.membership pm ON pm.batch_id=ap.batch_id AND pm.application_id=ap.legacy_id WHERE ap.batch_id=c.batch_id AND ap.account_id=c.legacy_id AND CAST(pm.collection_id AS VARCHAR)=?))"""
    data['accounts']=query(connection,"SELECT c.* FROM ledger.cash_dashboard c WHERE c.batch_id=? AND (?='' OR currency=?) AND "+scope+" ORDER BY currency,name",[batch,currency,currency,data['portfolio_filter'],data['portfolio_filter']])
    data['unassigned']=connection.execute("""SELECT count(*) FROM portfolio.cash_detail d
      LEFT JOIN ledger.reconciliation_decision r ON r.batch_id=d.batch_id
        AND r.subject_type='cash_entry' AND r.subject_id=d.legacy_id
      WHERE d.batch_id=? AND d.account_id IS NULL
        AND coalesce(r.resolution,'')<>'duplicate_source_row'
        AND (?='' OR year(d.settlement_date)=CAST(? AS INTEGER))""",
      [batch,data['year_filter'],data['year_filter'] or '0']).fetchone()[0]
    data['period_summary']=query(connection,"""SELECT c.currency,count(d.legacy_id) entry_count,
      sum(d.signed_value) FILTER(WHERE d.signed_value>0) credits,
      -sum(d.signed_value) FILTER(WHERE d.signed_value<0) debits,sum(d.signed_value) net_flow
      FROM ledger.cash_dashboard c LEFT JOIN ledger.cash_entry_dashboard d ON d.batch_id=c.batch_id AND d.account_id=c.account_id
        AND (?='' OR year(d.settlement_date)=CAST(? AS INTEGER))
      WHERE c.batch_id=? AND (?='' OR c.currency=?) AND """+scope+" GROUP BY c.currency ORDER BY c.currency",
      [data['year_filter'],data['year_filter'] or '0',batch,currency,currency,data['portfolio_filter'],data['portfolio_filter']])
    if account:
        selected=query(connection,'SELECT c.*,c.account_id AS legacy_id FROM ledger.cash_dashboard c WHERE c.batch_id=? AND c.account_id=? AND '+scope.replace('c.legacy_id','c.account_id'),[batch,int(account),data['portfolio_filter'],data['portfolio_filter']])
        if not selected:
            raise Http404('Conta não encontrada')
        data['selected']=selected[0]
        data.update(paged(request,connection,"SELECT * FROM ledger.cash_entry_dashboard WHERE batch_id=? AND account_id=? AND (?='' OR year(settlement_date)=CAST(? AS INTEGER)) ORDER BY settlement_timestamp NULLS FIRST,legacy_id",[batch,int(account),data['year_filter'],data['year_filter'] or '0']))
    return render(request,'dashboard/legacy_cash.html',data)


@page_view
def reports(request,connection):
    """Income and cash-flow report from canonical imported and manual events."""
    data=context(request,connection)
    batch=data['batch']['batch_id']; year=data['year_filter']; portfolio=data['portfolio_filter']
    add_current_account(connection, data)
    sql="""
    WITH imported AS (
      SELECT c.settlement_date AS event_date,coalesce(c.currency,'') currency,c.amount,c.category
      FROM ledger.cash_flow_effective_v3 c
      WHERE c.batch_id=? AND (?='' OR year(c.settlement_date)=CAST(? AS INTEGER))
        AND (?='' OR EXISTS(SELECT 1 FROM portfolio.membership pm
          WHERE pm.batch_id=c.batch_id AND pm.application_id=c.application_id
            AND CAST(pm.collection_id AS VARCHAR)=?))
    ), manual AS (
      SELECT me.settlement_date event_date,me.currency,me.amount,
        CASE WHEN me.transfer_id IS NOT NULL THEN 'internal_transfer'
             WHEN me.event_type='income' THEN 'income'
             WHEN me.event_type='tax' THEN 'tax'
             WHEN me.event_type='fee' THEN 'fee'
             WHEN me.event_type IN ('buy','sell','redemption') THEN 'investment'
             WHEN me.event_type='deposit' THEN 'external_contribution'
             WHEN me.event_type='withdrawal' THEN 'external_withdrawal'
             ELSE 'unclassified' END category
      FROM ledger.manual_event me
      LEFT JOIN portfolio.application ap ON ap.source_record_id=me.application_source_record_id
      WHERE EXISTS (SELECT 1 FROM portfolio.account ma WHERE ma.source_record_id=me.account_source_record_id AND ma.batch_id=?)
        AND (?='' OR year(me.settlement_date)=CAST(? AS INTEGER))
        AND (?='' OR EXISTS(SELECT 1 FROM portfolio.membership pm
          WHERE pm.batch_id=ap.batch_id AND pm.application_id=ap.legacy_id
            AND CAST(pm.collection_id AS VARCHAR)=?))
    ) , funding AS (
      SELECT settlement_date event_date,currency,amount,'external_contribution' category
      FROM ledger.purchase_contribution
      WHERE batch_id=? AND (?='' OR year(settlement_date)=CAST(? AS INTEGER))
        AND ?='' AND (reversed_at IS NULL OR reversed_at>?)
    ), events AS (SELECT * FROM imported UNION ALL SELECT * FROM manual UNION ALL SELECT * FROM funding)
    """
    params=[batch,year,year or '0',portfolio,portfolio,batch,year,year or '0',portfolio,portfolio,
            batch,year,year or '0',portfolio,data['analysis_cutoff']]
    if data.get('historical'):
        sql = sql.replace('WHERE EXISTS (SELECT 1 FROM portfolio.account ma', 'WHERE false AND EXISTS (SELECT 1 FROM portfolio.account ma')
        sql = sql.replace('WHERE batch_id=? AND', 'WHERE false AND batch_id=? AND')
    # Normalize currency aliases and restrict all report flows to the selected cutoff.
    sql = sql.replace('), events AS (', '), raw_events AS (')
    sql += """, events AS (SELECT event_date,CASE upper(currency) WHEN 'REAL' THEN 'BRL'
        WHEN 'DOL' THEN 'USD' WHEN 'DOLAR' THEN 'USD' ELSE upper(currency) END currency,
        amount,category FROM raw_events WHERE event_date<=?) """
    params.append(data['analysis_cutoff'])
    data['totals']=query(connection,sql+"""SELECT currency,
      sum(amount) FILTER(WHERE category='income') income,
      sum(amount) FILTER(WHERE category='investment') investment,
      sum(amount) FILTER(WHERE category='fee') fees,
      sum(amount) FILTER(WHERE category='tax') taxes,
      sum(amount) FILTER(WHERE category='external_contribution') contributions,
      sum(amount) FILTER(WHERE category='external_withdrawal') withdrawals,
      sum(amount) FILTER(WHERE category='internal_transfer') internal_transfers,
      sum(amount) FILTER(WHERE category='unclassified') unclassified,
      count(*) FILTER(WHERE category='unclassified') unclassified_count,
      sum(amount) net_flow,count(*) event_count
      FROM events GROUP BY currency ORDER BY currency""",params)
    data['periods']=query(connection,sql+"""SELECT
      CASE WHEN ?='' THEN strftime(event_date,'%Y') ELSE strftime(event_date,'%m/%Y') END period,
      min(event_date) period_order,currency,
      sum(amount) FILTER(WHERE category='income') income,
      sum(amount) FILTER(WHERE category='investment') investment,
      sum(amount) FILTER(WHERE category='fee') fees,
      sum(amount) FILTER(WHERE category='tax') taxes,
      sum(amount) FILTER(WHERE category='external_contribution') contributions,
      sum(amount) FILTER(WHERE category='external_withdrawal') withdrawals,
      sum(amount) FILTER(WHERE category='internal_transfer') internal_transfers,
      sum(amount) FILTER(WHERE category='unclassified') unclassified,sum(amount) net_flow
      FROM events WHERE event_date IS NOT NULL GROUP BY period,currency ORDER BY period_order DESC,currency""",
      [*params,year])
    performance_start=date(int(year),1,1) if year else date(2000,1,1)
    asset_returns=query(connection,"""SELECT d.source_record_id,a.symbol,a.name,d.currency,
      min(d.trading_date) first_date,max(d.trading_date) last_date,
      arg_min(d.adjusted_close,d.trading_date) first_value,
      arg_max(d.adjusted_close,d.trading_date) last_value
      FROM market.daily_close d JOIN market.asset_catalog a ON a.source_record_id=d.source_record_id
      WHERE a.batch_id=? AND d.adjusted_close IS NOT NULL AND d.trading_date BETWEEN ? AND ?
        AND EXISTS(SELECT 1 FROM portfolio.application ap LEFT JOIN portfolio.membership pm
          ON pm.batch_id=ap.batch_id AND pm.application_id=ap.legacy_id
          WHERE ap.batch_id=a.batch_id AND ap.asset_id=a.legacy_id
            AND (?='' OR CAST(pm.collection_id AS VARCHAR)=?))
      GROUP BY d.source_record_id,a.symbol,a.name,d.currency ORDER BY a.symbol""",
      [batch,performance_start,data['analysis_cutoff'],portfolio,portfolio])
    for row in asset_returns:
        row['return_pct']=(row['last_value']/row['first_value']-1)*100
    benchmark_returns=[]
    catalogs=query(connection,"""SELECT v.benchmark_source_record_id series_id,c.abbreviation code,c.name
      FROM market.benchmark_value v JOIN market.benchmark_catalog c
        ON c.source_record_id=v.benchmark_source_record_id
      WHERE v.observation_date BETWEEN ? AND ? GROUP BY ALL ORDER BY c.abbreviation""",
      [performance_start,data['analysis_cutoff']])
    for catalog in catalogs:
        rows=query(connection,"""SELECT observation_date,value,unit FROM market.comparison_series
          WHERE series_id=? AND observation_date BETWEEN ? AND ? ORDER BY observation_date""",
          [catalog['series_id'],performance_start,data['analysis_cutoff']])
        points=_normalized_series(rows)
        if points:
            benchmark_returns.append({**catalog,'first_date':rows[0]['observation_date'],
              'last_date':rows[-1]['observation_date'],'return_pct':Decimal(str(points[-1][1]))-100})
    data.update(performance_start=performance_start,asset_returns=asset_returns,
                benchmark_returns=benchmark_returns)
    data['unclassified_flows']=query(connection,"""SELECT c.*,
      (SELECT count(*) FROM document_record_link l WHERE l.record_id=c.cash_component_id) document_count
      FROM ledger.cash_flow_effective_v3 c WHERE c.batch_id=? AND c.category='unclassified'
      ORDER BY c.settlement_date,c.legacy_cash_id""",[batch])
    data['decision_warnings']=query(connection,"""SELECT e.*,d.rationale
      FROM ledger.cash_flow_effective_v3 e JOIN ledger.cash_flow_decision d USING(decision_id)
      WHERE (e.category='external_contribution' AND e.amount<0)
         OR (e.category='external_withdrawal' AND e.amount>0)
      ORDER BY e.settlement_date""")
    data['money_weighted_returns']=[]
    if not year:
        valuation_sql,valuation_parameters=valuation_query(data)
        applications=query(connection,"""SELECT legacy_id,source_record_id,name,asset_name,symbol,currency,
          reference_value,valuation_status FROM ("""+valuation_sql+") v ORDER BY currency,asset_name",valuation_parameters)
        all_return_flows=query(connection,"""SELECT application_id,settlement_date,amount
          FROM ledger.cash_flow_effective_v3
          WHERE batch_id=? AND application_id IS NOT NULL AND settlement_date<=?
          ORDER BY application_id,settlement_date,cash_component_id""",[batch,data['analysis_cutoff']])
        if not data.get('historical'):
            all_return_flows += query(connection,'''SELECT ap.legacy_id application_id,
              me.settlement_date,me.amount FROM ledger.manual_event me
              JOIN portfolio.application ap ON ap.source_record_id=me.application_source_record_id
              WHERE ap.batch_id=? AND me.settlement_date<=? AND me.transfer_id IS NULL
              AND me.event_type NOT IN ('deposit','withdrawal')''',[batch,data['analysis_cutoff']])
        return_flows_by_application={}
        for flow in all_return_flows:
            return_flows_by_application.setdefault(flow['application_id'],[]).append(flow)
        for application in applications:
            if application['reference_value'] is None or application['valuation_status'] not in ('priced','stale_price'):
                continue
            flows=return_flows_by_application.get(application['legacy_id'],[])
            dated=[(row['settlement_date'],row['amount']) for row in flows if row['settlement_date']]
            dated.append((data['analysis_cutoff'],application['reference_value']))
            rate=_xirr(dated)
            if rate is not None:
                application['return_pct']=Decimal(str(rate*100))
                application['first_date']=min(day for day,_ in dated)
                application['flow_count']=len(dated)-1
                data['money_weighted_returns'].append(application)
    valuation_sql,valuation_parameters=valuation_query(data)
    cost_applications=query(connection,"""SELECT legacy_id,source_record_id,name,asset_name,symbol,currency,
      class_name,investor_name,quantity_at_cutoff FROM ("""+valuation_sql+") v ORDER BY currency,asset_name",valuation_parameters)
    status_labels={'missing_trade_detail':'Compra ou venda sem quantidade/valor',
      'insufficient_quantity':'Venda excede a quantidade reconstruída',
      'unsupported_operation':'Portabilidade, split ou outra operação exige decisão de custo'}
    all_cost_events=query(connection,"""SELECT e.application_id,coalesce(e.settlement_date,e.trade_date) event_date,
      e.operation,e.source_quantity quantity,coalesce(abs(c.amount),abs(e.source_value)) amount,
      abs(e.source_value) gross_amount,c.amount IS NOT NULL allocated_cash
      FROM ledger.event e LEFT JOIN ledger.cash_flow_effective_v3 c ON c.related_event_id=e.event_id
      WHERE e.batch_id=?
      UNION ALL SELECT ap.legacy_id,coalesce(me.trade_date,me.settlement_date),me.event_type,me.quantity,
        CASE WHEN me.event_type='buy' THEN abs(me.amount)+coalesce(x.expense,0)
             WHEN me.event_type IN ('sell','redemption') THEN greatest(abs(me.amount)-coalesce(x.expense,0),0)
             ELSE abs(me.amount) END,abs(me.amount),true
      FROM ledger.manual_event me JOIN portfolio.application ap
        ON ap.source_record_id=me.application_source_record_id
      LEFT JOIN (SELECT trade_event_id,sum(amount) expense FROM ledger.file_import_event_allocation GROUP BY 1) x
        ON x.trade_event_id=me.event_id
      WHERE ap.batch_id=? AND NOT ?
      ORDER BY event_date""",[batch,batch,data.get('historical',False)])
    events_by_application={}
    for event in all_cost_events:
        events_by_application.setdefault(event['application_id'],[]).append(event)
    calculated=[];excluded=[]
    for application in cost_applications:
        events=events_by_application.get(application['legacy_id'],[])
        result=_average_cost(events,data['analysis_cutoff'],int(year) if year else None)
        application.update(result)
        if result['status']=='calculated':
            expected=application['quantity_at_cutoff']
            application['quantity_matches']=expected is not None and abs(result['quantity']-expected)<Decimal('0.00000001')
            if application['quantity_matches']: calculated.append(application)
            else:
                application['status_label']='Quantidade final não confere';excluded.append(application)
        else:
            application['status_label']=status_labels[result['status']];excluded.append(application)
    data.update(cost_basis=calculated,cost_basis_excluded=excluded)
    tax_buckets={}
    for application in calculated:
        class_name=(application['class_name'] or '').lower()
        asset_text=' '.join(str(application.get(key) or '') for key in ('name','asset_name','symbol')).lower()
        if 'brasil' in class_name:
            tax_class='etf' if any(token in asset_text for token in (' etf','ishares','it now','índice','indice')) else 'stocks'
        else:
            tax_class='fii' if class_name.startswith('im') else None
        if application['currency']!='REAL' or not tax_class: continue
        for sale in application['sale_details']:
            key=(application['investor_name'] or 'Sem titular',sale['date'].replace(day=1),tax_class,sale['tax_group'])
            bucket=tax_buckets.setdefault(key,{'investor':key[0],'month':key[1],'tax_class':tax_class,
              'sales':Decimal('0'),'gain':Decimal('0'),'tax_group':sale['tax_group']})
            bucket['sales']+=sale['proceeds'];bucket['gain']+=sale['gain']
    consolidated={}
    for bucket in tax_buckets.values():
        group='day_trade' if bucket['tax_group']=='day_trade' else ('fii' if bucket['tax_class']=='fii' else 'common')
        key=(bucket['investor'],bucket['month'],group)
        row=consolidated.setdefault(key,{'investor':key[0],'month':key[1],'tax_group':group,
          'sales':Decimal('0'),'gain':Decimal('0'),'stock_sales':Decimal('0'),
          'stock_gain':Decimal('0'),'etf_gain':Decimal('0')})
        row['sales']+=bucket['sales'];row['gain']+=bucket['gain']
        if bucket['tax_class']=='stocks':
            row['stock_sales']+=bucket['sales'];row['stock_gain']+=bucket['gain']
        elif bucket['tax_class']=='etf': row['etf_gain']+=bucket['gain']
    tax_rows=[];loss_pools={}
    for row in sorted(consolidated.values(),key=lambda item:(item['investor'],item['month'],item['tax_group'])):
        pool_key=(row['investor'],row['tax_group']);opening=loss_pools.get(pool_key,Decimal('0'))
        row['label']={'common':'Operações comuns','fii':'FII','day_trade':'Day trade'}[row['tax_group']]
        row.update(opening_loss=opening,compensated_loss=Decimal('0'),taxable_gain=None,
                   estimated_tax=None,exempt_gain=Decimal('0'))
        if row['tax_group']=='day_trade':
            taxable_result=row['gain'];rate=Decimal('.20')
        else:
            if row['tax_group']=='common':
                if row['stock_sales']<=Decimal('20000') and row['stock_gain']>0:
                    row['exempt_gain']=row['stock_gain'];taxable_result=row['etf_gain']
                else: taxable_result=row['stock_gain']+row['etf_gain']
                rate=Decimal('.15')
            else:
                taxable_result=row['gain'];rate=Decimal('.20')
        if taxable_result<0:
            row['closing_loss']=opening-taxable_result
            row['taxable_gain']=Decimal('0');row['estimated_tax']=Decimal('0')
            row['tax_status']='Prejuízo transportado'
        else:
            row['compensated_loss']=min(opening,taxable_result)
            row['taxable_gain']=taxable_result-row['compensated_loss']
            row['closing_loss']=opening-row['compensated_loss']
            row['estimated_tax']=row['taxable_gain']*rate
            row['tax_status']='Isento' if row['exempt_gain'] and not row['taxable_gain'] else 'Prévia antes do IRRF'
        loss_pools[pool_key]=row['closing_loss']
        tax_rows.append(row)
    irrf_rows=query(connection,"""WITH evidence AS (
      SELECT e.cash_component_id,coalesce(i.name,'Sem titular') investor,e.settlement_date,
        e.description,-e.amount irrf,
        CASE WHEN upper(e.description) LIKE '%DAY%TRADE%' THEN 'day_trade' ELSE 'common' END tax_group,
        CAST(date_trunc('month',coalesce(max(re.trade_date),
          CASE WHEN count(DISTINCT date_trunc('month',m.trade_date))=1 THEN max(m.trade_date) END)) AS DATE) tax_month
      FROM ledger.cash_flow_effective_v3 e
      JOIN portfolio.account a ON a.batch_id=e.batch_id AND a.legacy_id=e.account_id
      LEFT JOIN portfolio.investor i ON i.batch_id=a.batch_id AND i.legacy_id=a.investor_id
      LEFT JOIN ledger.event re ON re.event_id=e.related_event_id
      LEFT JOIN portfolio.cash_entry ce ON ce.batch_id=e.batch_id AND ce.legacy_id=e.legacy_cash_id
      LEFT JOIN main.document_record_link cash_doc ON cash_doc.record_id=ce.source_record_id
      LEFT JOIN main.document_record_link movement_doc ON movement_doc.document_id=cash_doc.document_id
      LEFT JOIN portfolio.movement m ON m.batch_id=e.batch_id AND m.source_record_id=movement_doc.record_id
      WHERE e.batch_id=? AND e.currency='REAL' AND e.category='tax'
        AND upper(e.description) LIKE 'IRRF%OPERA%'
      GROUP BY e.cash_component_id,i.name,e.settlement_date,e.description,e.amount)
      SELECT investor,tax_month,tax_group,min(settlement_date) settlement_date,sum(irrf) irrf,
        string_agg(description,'; ' ORDER BY settlement_date) descriptions
      FROM evidence GROUP BY 1,2,3 ORDER BY 1,2""",[batch])
    irrf_by_month={(row['investor'],row['tax_month'],row['tax_group']):row['irrf']
                   for row in irrf_rows if row['tax_month']}
    used_irrf=set()
    for row in tax_rows:
        key=(row['investor'],row['month'],row['tax_group'])
        row['irrf_candidate']=irrf_by_month.get(key,Decimal('0'))
        if row['irrf_candidate']: used_irrf.add(key)
        row['net_tax']=max((row['estimated_tax'] or Decimal('0'))-row['irrf_candidate'],Decimal('0')) \
          if row['estimated_tax'] is not None else None
    unmatched_irrf=[row for row in irrf_rows
                    if not row['tax_month'] or (row['investor'],row['tax_month'],row['tax_group']) not in used_irrf]
    if year:
        tax_rows=[row for row in tax_rows if row['month'].year==int(year)]
        unmatched_irrf=[row for row in unmatched_irrf
                        if (row['tax_month'] or row['settlement_date']).year==int(year)]
    data['unmatched_irrf']=unmatched_irrf
    data['tax_preview']=sorted(tax_rows,key=lambda row:(row['month'],row['investor'],row['tax_group']),reverse=True)
    return render(request,'dashboard/legacy_reports.html' if data.get('historical') else 'dashboard/reports.html',data)


@page_view
def reconciliation(request,connection):
    data=context(request,connection);batch=data['batch']['batch_id']
    cutoff=data['batch']['as_of_date']
    currency_sql="""CASE upper(currency) WHEN 'REAL' THEN 'BRL' WHEN 'DOL' THEN 'USD'
      WHEN 'DOLAR' THEN 'USD' ELSE upper(currency) END"""

    # Compare both ledgers at the frozen Fin1 cutoff. The active side includes
    # later corrections whose financial date is on or before that cutoff.
    legacy_data={**data,'analysis_cutoff':cutoff,'historical':True,'portfolio_filter':'','year_filter':''}
    active_data={**data,'analysis_cutoff':cutoff,'historical':False,'portfolio_filter':'','year_filter':''}
    legacy_valuation,legacy_parameters=valuation_query(legacy_data)
    active_valuation,active_parameters=valuation_query(active_data)
    valuation_totals_sql=lambda scoped: "SELECT "+currency_sql+""" currency,
      sum(reference_value) total_value,count(reference_value) priced_count,
      count(*) FILTER(WHERE valuation_status NOT IN ('closed','priced','stale_price')) blocker_count
      FROM ("""+scoped+") v GROUP BY 1"
    legacy_values={r['currency']:r for r in query(connection,valuation_totals_sql(legacy_valuation),legacy_parameters)}
    active_values={r['currency']:r for r in query(connection,valuation_totals_sql(active_valuation),active_parameters)}
    data['final_valuation_checks']=[]
    for currency in sorted(set(legacy_values)|set(active_values)):
        legacy=legacy_values.get(currency,{});active=active_values.get(currency,{})
        legacy_value=legacy.get('total_value');active_value=active.get('total_value')
        data['final_valuation_checks'].append({'currency':currency,'legacy_value':legacy_value,
          'active_value':active_value,'difference':(active_value or Decimal(0))-(legacy_value or Decimal(0)),
          'legacy_priced':legacy.get('priced_count',0),'active_priced':active.get('priced_count',0),
          'blocker_count':active.get('blocker_count',0)})
    data['final_valuation_blockers']=query(connection,"""SELECT source_record_id,name,asset_name,
      account_name,"""+currency_sql+""" currency,valuation_status
      FROM ("""+active_valuation+""") v
      WHERE valuation_status NOT IN ('closed','priced','stale_price')
      ORDER BY currency,account_name,asset_name""",active_parameters)
    for row in data['final_valuation_blockers']:
        row['status_label']=VALUATION_STATUS.get(row['valuation_status'],row['valuation_status'])

    data['final_cash_checks']=query(connection,"""WITH legacy AS (
      SELECT a.source_record_id,a.name,"""+currency_sql.replace('currency','c.abbreviation')+""" currency,
        sum(e.signed_amount) amount
      FROM ledger.cash_entry_canonical e
      JOIN portfolio.account a ON a.batch_id=e.batch_id AND a.legacy_id=e.account_id
      LEFT JOIN portfolio.currency c ON c.batch_id=a.batch_id AND c.legacy_id=a.currency_id
      WHERE e.batch_id=? AND e.settlement_date<=? AND NOT EXISTS (
        SELECT 1 FROM ledger.reconciliation_decision d WHERE d.batch_id=e.batch_id
          AND d.subject_type='cash_entry' AND d.subject_id=e.legacy_id
          AND d.resolution='duplicate_source_row') GROUP BY ALL
    ), active AS (
      SELECT account_source_record_id,"""+currency_sql+""" currency,sum(amount) amount
      FROM ledger.investment_cash_entry WHERE batch_id=? AND settlement_date<=? GROUP BY ALL
    ) SELECT coalesce(l.source_record_id,a.account_source_record_id) account_source_record_id,
      coalesce(l.name,p.name) account_name,coalesce(l.currency,a.currency) currency,
      coalesce(l.amount,0) legacy_balance,coalesce(a.amount,0) active_balance,
      coalesce(a.amount,0)-coalesce(l.amount,0) difference
    FROM legacy l FULL JOIN active a ON a.account_source_record_id=l.source_record_id
      AND a.currency=l.currency
    LEFT JOIN portfolio.account p ON p.source_record_id=a.account_source_record_id
    ORDER BY currency,account_name""",[batch,cutoff,batch,cutoff])

    flow_sql="""WITH imported AS (
      SELECT """+currency_sql+""" currency,category,amount FROM ledger.cash_flow_effective_v3
      WHERE batch_id=? AND settlement_date<=?
    ), manual AS (
      SELECT """+currency_sql+""" currency,
        CASE WHEN transfer_id IS NOT NULL THEN 'internal_transfer'
          WHEN event_type='income' THEN 'income' WHEN event_type='tax' THEN 'tax'
          WHEN event_type='fee' THEN 'fee' WHEN event_type IN ('buy','sell','redemption') THEN 'investment'
          WHEN event_type='deposit' THEN 'external_contribution'
          WHEN event_type='withdrawal' THEN 'external_withdrawal' ELSE 'unclassified' END category,amount
      FROM ledger.manual_event me WHERE settlement_date<=? AND EXISTS (
        SELECT 1 FROM portfolio.account a WHERE a.source_record_id=me.account_source_record_id AND a.batch_id=?)
    ), funding AS (
      SELECT """+currency_sql+""" currency,'external_contribution' category,amount
      FROM ledger.purchase_contribution WHERE batch_id=? AND settlement_date<=?
        AND (reversed_at IS NULL OR reversed_at>?)
    ), legacy AS (SELECT currency,category,sum(amount) amount FROM imported GROUP BY ALL),
    active AS (SELECT currency,category,sum(amount) amount FROM (
      SELECT * FROM imported UNION ALL SELECT * FROM manual UNION ALL SELECT * FROM funding) GROUP BY ALL)
    SELECT coalesce(l.currency,a.currency) currency,coalesce(l.category,a.category) category,
      coalesce(l.amount,0) legacy_amount,coalesce(a.amount,0) active_amount,
      coalesce(a.amount,0)-coalesce(l.amount,0) difference
    FROM legacy l FULL JOIN active a USING(currency,category) ORDER BY currency,category"""
    data['final_flow_checks']=query(connection,flow_sql,[batch,cutoff,cutoff,batch,batch,cutoff,cutoff])
    data['final_income_checks']=[r for r in data['final_flow_checks'] if r['category']=='income']
    data['final_cutoff']=cutoff
    data['final_valuation_blocker_count']=len(data['final_valuation_blockers'])
    data['final_unexplained_count']=sum(1 for r in data['final_valuation_checks'] if r['difference'])
    # Every cash/flow delta is traceable to Fin2 journal entries; valuation
    # differences would indicate an unexplained change at the common cutoff.
    data['final_fin2_adjustment_count']=sum(1 for r in data['final_cash_checks'] if r['difference'])
    data['cash_blockers']=query(connection,"""SELECT c.*,
      (SELECT count(*) FROM document_record_link l WHERE l.record_id=c.source_record_id) document_count
      FROM ledger.cash_dashboard c WHERE c.batch_id=? AND c.canonical_balance IS NULL
      ORDER BY c.currency,c.name""",[batch])
    data['position_blockers']=query(connection,"""SELECT p.source_record_id,p.legacy_id,p.name,p.asset_name,
      p.account_name,p.currency,p.legacy_quantity,p.all_settled_quantity,p.legacy_delta,
      p.legacy_net_invested,r.resolution,r.rationale,
      (SELECT count(*) FROM document_record_link l WHERE l.record_id=p.source_record_id) document_count
      FROM portfolio.position p JOIN ledger.position_reconciliation r
        ON r.batch_id=p.batch_id AND r.application_id=p.legacy_id
      WHERE p.batch_id=? AND r.canonical_quantity IS NULL ORDER BY p.name""",[batch])
    data['market_blockers']=query(connection,"""SELECT valuation_status,count(*) count
      FROM ("""+valuation_query(data)[0]+""") v
      WHERE valuation_status NOT IN ('priced','stale_price','closed') GROUP BY 1 ORDER BY 2 DESC""",
      valuation_query(data)[1])
    account_ids=[row['source_record_id'] for row in data['cash_blockers']]
    data['evidence_documents']=query(connection,"""SELECT DISTINCT d.document_id,d.original_filename,d.byte_size,l.record_id
      FROM source_document d JOIN document_record_link l USING(document_id)
      WHERE l.record_id IN ("""+','.join('?' for _ in account_ids)+") ORDER BY d.original_filename",account_ids) if account_ids else []
    data['statement_observations']=query(connection,"""SELECT r.period_end,r.currency,r.opening_balance,
      r.closing_balance,r.ledger_closing_balance,r.closing_difference,r.document_id,d.original_filename
      FROM ledger.statement_balance_reconciliation r JOIN source_document d USING(document_id)
      WHERE r.batch_id=? AND r.account_record_id IN ("""+','.join('?' for _ in account_ids)+") ORDER BY r.period_end",
      [batch,*account_ids]) if account_ids else []
    data['blocker_count']=len(data['cash_blockers'])+len(data['position_blockers'])+sum(r['count'] for r in data['market_blockers'])
    return render(request,'dashboard/reconciliation.html',data)


@require_POST
def classify_cash_flow(request,identifier):
    if not settings.WRITE_ENABLED:
        return HttpResponse('Escrita desabilitada',status=403)
    try:
        create_cash_flow_decision(settings.WAREHOUSE_PATH,cash_component_id=identifier,
          category=request.POST.get('category',''),rationale=request.POST.get('rationale',''))
    except ValueError as exc:
        return HttpResponse(str(exc),status=400)
    suffix=urlencode({key:value for key,value in (
      ('batch',request.POST.get('batch','')),('portfolio',request.POST.get('portfolio','')),
      ('year',request.POST.get('year',''))) if value})
    return redirect('/fin2/relatorios/'+(('?'+suffix) if suffix else ''))


@require_http_methods(['GET','POST'])
def manual_events(request):
    if not settings.WRITE_ENABLED:
        return HttpResponse('Escrita desabilitada',status=403)
    error=request.GET.get('error')
    if request.method=='POST':
        try:
            upload=request.FILES.get('new_document')
            upload_args={'upload_filename':upload.name,'upload_body':upload.read(),
                         'storage_root':settings.DOCUMENT_ROOT} if upload else {}
            if request.POST.get('action')=='correction':
                correct_event(settings.WAREHOUSE_PATH,request.POST.get('event_id',''),
                  settlement_date=request.POST.get('settlement_date',''),amount=request.POST.get('amount',''),
                  quantity=request.POST.get('quantity') or None,description=request.POST.get('description',''),
                  request_key=request.POST.get('request_key'))
            elif request.POST.get('action')=='transfer':
                create_transfer(settings.WAREHOUSE_PATH,source_account=request.POST.get('source_account',''),
                  destination_account=request.POST.get('destination_account',''),
                  settlement_date=request.POST.get('settlement_date',''),amount=request.POST.get('amount',''),
                  description=request.POST.get('description',''),document_id=request.POST.get('document') or None,
                  request_key=request.POST.get('request_key'),**upload_args)
            else:
                create_manual_event(settings.WAREHOUSE_PATH,
                  account_record=request.POST.get('account',''),application_record=request.POST.get('application') or None,
                  funding_source=request.POST.get('funding_source') or None,
                  event_type=request.POST.get('event_type',''),trade_date=request.POST.get('trade_date') or None,
                  settlement_date=request.POST.get('settlement_date',''),currency=request.POST.get('currency',''),
                  quantity=request.POST.get('quantity') or None,amount=request.POST.get('amount',''),
                  description=request.POST.get('description',''),document_id=request.POST.get('document') or None,
                  request_key=request.POST.get('request_key'),**upload_args)
            return redirect('manual-events')
        except ValueError as exc: error=str(exc)
    try:
        with reader(settings.WAREHOUSE_PATH) as connection:
            data=context(request,connection)
            batch=data['batch']['batch_id']
            data['accounts']=query(connection,"""select a.source_record_id,a.legacy_id,a.name,c.abbreviation currency
              from portfolio.account a left join portfolio.currency c
                on c.batch_id=a.batch_id and c.legacy_id=a.currency_id
              where a.batch_id=? order by a.name""",[batch])
            data['applications']=query(connection,'select source_record_id,name,account_id from portfolio.application where batch_id=? order by name',[batch])
            data['documents']=query(connection,'select document_id,original_filename from source_document where batch_id=? order by original_filename',[batch])
            data['manual_events']=query(connection,"""select m.*,a.name account_name,
              d.document_id,d.original_filename,
              exists(select 1 from ledger.manual_event r where r.reverses_event_id=m.event_id) reversed
              from ledger.manual_event m left join portfolio.account a on a.source_record_id=m.account_source_record_id
              left join ledger.manual_event_document md on md.event_id=m.event_id
              left join source_document d on d.document_id=md.document_id
              order by m.created_at desc limit 100""")
            for event in data['manual_events']:event['correction_request_key']=uuid4().hex
            data['manual_transfers']=query(connection,"""select t.*,s.name source_name,d.name destination_name,
              exists(select 1 from ledger.manual_transfer r where r.reverses_transfer_id=t.transfer_id) reversed
              from ledger.manual_transfer t
              left join portfolio.account s on s.source_record_id=t.source_account_record_id
              left join portfolio.account d on d.source_record_id=t.destination_account_record_id
              order by t.created_at desc limit 100""")
            data['write_error']=error
            data['form_values']=request.POST if error else {}
            data['event_request_key']=request.POST.get('request_key') if error and request.POST.get('action')=='event' else uuid4().hex
            data['transfer_request_key']=request.POST.get('request_key') if error and request.POST.get('action')=='transfer' else uuid4().hex
            return render(request,'dashboard/manual_events.html',data,status=400 if error else 200)
    except Unavailable:
        return render(request,'dashboard/unavailable.html',status=503)


@require_POST
def reverse_manual_event(request,identifier):
    if not settings.WRITE_ENABLED: return HttpResponse('Escrita desabilitada',status=403)
    if not re.fullmatch(r'[a-f0-9]{32}',identifier): raise Http404
    try: reverse_event(settings.WAREHOUSE_PATH,identifier,request.POST.get('description','Reversão'))
    except ValueError as exc:return redirect('/fin2/lancamentos/?'+urlencode({'error':str(exc)}))
    return redirect('manual-events')


@require_POST
def manual_transfer(request):
    if not settings.WRITE_ENABLED:return HttpResponse('Escrita desabilitada',status=403)
    try:
        create_transfer(settings.WAREHOUSE_PATH,source_account=request.POST.get('source_account',''),
          destination_account=request.POST.get('destination_account',''),
          settlement_date=request.POST.get('settlement_date',''),amount=request.POST.get('amount',''),
          description=request.POST.get('description',''),document_id=request.POST.get('document') or None)
    except ValueError as exc:return redirect('/fin2/lancamentos/?'+urlencode({'error':str(exc)}))
    return redirect('manual-events')


@require_POST
def reverse_manual_transfer(request,identifier):
    if not settings.WRITE_ENABLED:return HttpResponse('Escrita desabilitada',status=403)
    if not re.fullmatch(r'[a-f0-9]{32}',identifier):raise Http404
    try:reverse_transfer(settings.WAREHOUSE_PATH,identifier,request.POST.get('description','Estorno de transferência'))
    except ValueError as exc:return redirect('/fin2/lancamentos/?'+urlencode({'error':str(exc)}))
    return redirect('manual-events')


@require_http_methods(['GET','POST'])
def file_imports(request):
    if not settings.WRITE_ENABLED:return HttpResponse('Escrita desabilitada',status=403)
    try:
        if request.method=='POST':
            upload=request.FILES.get('file')
            if not upload: raise ValueError('Selecione um arquivo CSV ou XLSX')
            identifier,_=stage_file_import(settings.WAREHOUSE_PATH,settings.DOCUMENT_ROOT,
              upload.name,upload.read(),upload.content_type,
              options={'account_record':request.POST.get('account') or None,
                       'adapter_id':request.POST.get('adapter') or None})
            return redirect('/fin2/importar/?preview='+identifier)
        with reader(settings.WAREHOUSE_PATH) as connection:
            data=context(request,connection)
            data['accounts']=query(connection,"""select source_record_id,name from portfolio.account
              where batch_id=? order by name""",[data['batch']['batch_id']])
            data['imports']=query(connection,'select * exclude(preview) from ledger.file_import order by created_at desc limit 50')
            identifier=request.GET.get('preview','');selected=None
            if identifier:
                if not re.fullmatch(r'[a-f0-9]{32}',identifier):raise Http404
                rows=query(connection,'select * from ledger.file_import where import_id=?',[identifier])
                if not rows:raise Http404
                selected=rows[0];selected['rows']=json.loads(selected['preview'])
                selected['document_metadata']=json.loads(selected['document_metadata']) if selected.get('document_metadata') else None
            data.update(import_error=request.GET.get('error'),selected_import=selected)
            return render(request,'dashboard/file_imports.html',data,status=400 if request.GET.get('error') else 200)
    except (ValueError,OSError) as exc:
        try:
            with reader(settings.WAREHOUSE_PATH) as connection:
                data=context(request,connection);data.update(imports=query(connection,'select * exclude(preview) from ledger.file_import order by created_at desc limit 50'),import_error=str(exc),selected_import=None)
                return render(request,'dashboard/file_imports.html',data,status=400)
        except Unavailable:return render(request,'dashboard/unavailable.html',status=503)


@require_POST
def commit_file_import(request,identifier):
    if not settings.WRITE_ENABLED:return HttpResponse('Escrita desabilitada',status=403)
    if not re.fullmatch(r'[a-f0-9]{32}',identifier):raise Http404
    try:commit_import(settings.WAREHOUSE_PATH,identifier)
    except ValueError as exc:return HttpResponse(str(exc),status=400)
    return redirect('/fin2/importar/?preview='+identifier)


@require_POST
def reject_file_import(request,identifier):
    if not settings.WRITE_ENABLED:return HttpResponse('Escrita desabilitada',status=403)
    if not re.fullmatch(r'[a-f0-9]{32}',identifier):raise Http404
    try:reject_import(settings.WAREHOUSE_PATH,identifier,request.POST.get('reason',''))
    except ValueError as exc:
        return redirect('/fin2/importar/?'+urlencode({'preview':identifier,'error':str(exc)}))
    return redirect('/fin2/importar/?preview='+identifier)


@page_view
def file_import_file(request,connection,identifier):
    if not re.fullmatch(r'[a-f0-9]{32}',identifier):raise Http404
    rows=query(connection,'select * exclude(preview) from ledger.file_import where import_id=?',[identifier])
    if not rows:raise Http404
    item=rows[0];root=settings.DOCUMENT_ROOT.resolve();path=(root/item['storage_key']).resolve()
    if not path.is_relative_to(root):raise Http404
    try:stream=path.open('rb')
    except OSError:raise Http404 from None
    if (item['byte_size'] is not None and path.stat().st_size!=item['byte_size']) or hashlib.file_digest(stream,'sha256').hexdigest()!=item['sha256']:
        stream.close();raise Http404('Integridade do arquivo não confirmada')
    stream.seek(0)
    response=FileResponse(stream,as_attachment=True,filename=item['original_filename'],content_type=item['media_type'])
    response['Content-Security-Policy']="sandbox; default-src 'none'; frame-ancestors 'self'"
    return response


@page_view
def records(request, connection):
    data = context(request, connection)
    table, term = request.GET.get("table", ""), request.GET.get("q", "")[:200]
    order,state=table_order(request,{'id':'legacy_id','source':'table_name','label':'label'},'source')
    data.update(table_filter=table, term=term,**state)
    data["tables"] = query(connection,"SELECT DISTINCT table_name FROM source_table WHERE batch_id=? ORDER BY table_name",[data["batch"]["batch_id"]])
    data.update(paged(request, connection,
        "SELECT record_id,table_name,legacy_id,coalesce(json_extract_string(payload,'$.nome'),json_extract_string(payload,'$.descricao'),json_extract_string(payload,'$.item'),'—') AS label FROM source_record WHERE batch_id=? AND (?='' OR table_name=?) AND (?='' OR CAST(payload AS VARCHAR) ILIKE ?) ORDER BY "+order+",legacy_id",
        [data["batch"]["batch_id"],table,table,term,"%"+term+"%"]))
    return render(request,"dashboard/records.html",data)


@page_view
def record(request, connection, identifier):
    item = one(connection,"source_record","record_id",identifier)
    data = context(request, connection, item["batch_id"])
    data["item"] = item
    data["fields"] = [(k, "—" if v is None else v) for k,v in json.loads(item["payload"]).items()]
    data["documents"] = query(connection,"SELECT d.document_id,d.original_filename,l.relation FROM document_record_link l JOIN source_document d USING(document_id) WHERE l.record_id=? ORDER BY d.original_filename,l.relation",[identifier])
    data["issues"] = query(connection,"SELECT code,details FROM import_issue WHERE record_id=? ORDER BY code",[identifier])
    for issue in data["issues"]:
        issue["label"] = ISSUES.get(issue["code"],issue["code"])
    return render(request,"dashboard/record.html",data)


@page_view
def documents(request, connection):
    data = context(request, connection)
    term = request.GET.get("q", "")[:200]
    order,state=table_order(request,{'file':'original_filename','size':'byte_size','links':'links'},'file')
    data.update(term=term,**state)
    data.update(paged(request,connection,"SELECT d.document_id,d.original_filename,d.source_path,d.byte_size,(SELECT count(*) FROM document_record_link l WHERE l.document_id=d.document_id) AS links FROM source_document d WHERE batch_id=? AND (?='' OR original_filename ILIKE ?) ORDER BY "+order+",document_id",[data["batch"]["batch_id"],term,"%"+term+"%"]))
    data['filtered_bytes']=connection.execute("SELECT sum(byte_size) FROM source_document WHERE batch_id=? AND (?='' OR original_filename ILIKE ?)",[data["batch"]["batch_id"],term,"%"+term+"%"]).fetchone()[0]
    return render(request,"dashboard/documents.html",data)


def open_document(item):
    root = settings.DOCUMENT_ROOT.resolve()
    key = item["storage_key"]
    if not re.fullmatch(r"[a-f0-9]{2}/[a-f0-9]{64}", key):
        raise Http404("Arquivo indisponível")
    path = (root / key).resolve()
    if not path.is_relative_to(root):
        raise Http404("Arquivo indisponível")
    try:
        stream = path.open("rb")
    except OSError:
        raise Http404("Arquivo indisponível") from None
    if path.stat().st_size != item["byte_size"] or hashlib.file_digest(stream,"sha256").hexdigest() != item["sha256"]:
        stream.close()
        raise Http404("Integridade do arquivo não confirmada")
    stream.seek(0)
    header = stream.read(16)
    stream.seek(0)
    extension = Path(item["original_filename"]).suffix.lower()
    media = "application/octet-stream"
    if extension == ".pdf" and header.startswith(b"%PDF-"):
        media = "application/pdf"
    elif extension == ".png" and header.startswith(b"\x89PNG\r\n\x1a\n"):
        media = "image/png"
    elif extension in (".jpg", ".jpeg") and header.startswith(b"\xff\xd8\xff"):
        media = "image/jpeg"
    return stream, media


@page_view
def document(request, connection, identifier):
    item = one(connection,"source_document","document_id",identifier)
    data = context(request, connection,item["batch_id"])
    data["item"] = item
    try:
        stream, media = open_document(item)
        stream.close()
        data["preview"] = media != "application/octet-stream"
        data["available"] = True
    except Http404:
        data["available"] = False
    data["records"] = query(connection,"SELECT r.record_id,r.table_name,r.legacy_id,l.relation FROM document_record_link l JOIN source_record r USING(record_id) WHERE l.document_id=? ORDER BY r.table_name,r.legacy_id",[identifier])
    return render(request,"dashboard/document.html",data)


@page_view
def document_file(request, connection, identifier):
    item = one(connection,"source_document","document_id",identifier)
    stream, media = open_document(item)
    attachment = request.GET.get("download") == "1" or media == "application/octet-stream"
    response = FileResponse(stream,as_attachment=attachment,filename=item["original_filename"],content_type=media)
    response["Content-Security-Policy"] = "sandbox; default-src 'none'; frame-ancestors 'self'"
    return response


@page_view
def issues(request, connection):
    data = context(request,connection)
    code = request.GET.get("code", "");term=request.GET.get('q','')[:200]
    order,state=table_order(request,{'issue':'i.code','source':'r.table_name','id':'r.legacy_id'},'issue')
    data.update(code_filter=code,term=term,**state)
    data["codes"] = list(ISSUES.items())
    data.update(paged(request,connection,"SELECT i.code,i.details,r.record_id,r.table_name,r.legacy_id FROM import_issue i LEFT JOIN source_record r USING(record_id) WHERE i.batch_id=? AND (?='' OR i.code=?) AND (?='' OR concat_ws(' ',i.code,i.details,r.table_name,CAST(r.legacy_id AS VARCHAR)) ILIKE ?) ORDER BY "+order+",i.issue_id",[data["batch"]["batch_id"],code,code,term,'%'+term+'%']))
    for row in data["rows"]:
        row["label"] = ISSUES.get(row["code"],row["code"])
    return render(request,"dashboard/issues.html",data)
