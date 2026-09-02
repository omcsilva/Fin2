import hashlib
import json
import re
from datetime import date
from functools import wraps
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_safe, require_POST

from warehouse.repositories.dashboard import Unavailable, query, reader
from fin2.portfolio.price_jobs import create as create_price_job

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
                return function(request, connection, *args, **kwargs)
        except Unavailable:
            return render(request, "dashboard/unavailable.html", status=503)
    return wrapped


def context(request, connection, batch_id=None):
    batches = query(connection, "SELECT batch_id, as_of_date, imported_at FROM import_batch ORDER BY imported_at DESC, batch_id")
    selected = batch_id or request.GET.get("batch") or (batches[0]["batch_id"] if batches else None)
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
    year = request.GET.get('year','')
    if year and (not re.fullmatch(r'\d{4}',year) or int(year) not in years):
        raise Http404('Ano não encontrado')
    global_query = urlencode({k:v for k,v in [('batch',selected),('portfolio',portfolio),('year',year)] if v})
    selected_collection = next((c for c in collections if str(c['legacy_id'])==portfolio),None)
    latest_price_update=connection.execute("SELECT max(captured_at) FROM market.quote_capture WHERE status='accepted'").fetchone()[0]
    latest_job=query(connection,"SELECT * FROM price_update_job ORDER BY created_at DESC LIMIT 1")
    return {"batches": batches, "batch": batch, "collections":collections,
            "portfolio_filter":portfolio,"selected_collection":selected_collection,
            "years":years,"year_filter":year,"global_query":global_query,
            "analysis_cutoff": date(int(year),12,31) if year else max(batch['as_of_date'],date.today()),
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
    ), scoped AS (
      SELECT p.* EXCLUDE(quantity_at_cutoff,movement_count,incomplete_count,legacy_delta,legacy_price,price_date),
        CASE WHEN coalesce(y.incomplete_count,0)=0 THEN coalesce(y.quantity,0) END AS quantity_at_cutoff,
        coalesce(y.movement_count,0) AS movement_count,coalesce(y.incomplete_count,0) AS incomplete_count,
        CASE WHEN ?='' THEN p.legacy_delta END AS legacy_delta,
        coalesce(ep.price,p.legacy_price) AS legacy_price,
        coalesce(CAST(ep.quoted_at AS DATE),p.price_date) AS price_date,
        CASE WHEN ep.price IS NOT NULL THEN 'brapi_v2' ELSE 'fin1_snapshot' END AS price_source
      FROM portfolio.position p JOIN annual y ON y.batch_id=p.batch_id AND y.application_id=p.legacy_id
      LEFT JOIN market.asset_catalog ma ON ma.batch_id=p.batch_id AND ma.legacy_id=p.asset_id
      LEFT JOIN market.latest_external_price ep ON ep.source_record_id=ma.source_record_id AND CAST(ep.quoted_at AS DATE)<=?
      WHERE p.batch_id=? AND (?='' OR EXISTS (
        SELECT 1 FROM portfolio.membership pm WHERE pm.batch_id=p.batch_id
          AND pm.application_id=p.legacy_id AND CAST(pm.collection_id AS VARCHAR)=?))
    ), classified AS (
      SELECT *,date_diff('day',price_date,?) AS price_age_days,
       CASE WHEN incomplete_count>0 OR quantity_at_cutoff IS NULL OR (?='' AND (legacy_delta IS NULL OR legacy_delta<>0)) THEN 'quantity_review'
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
    cutoff=data['analysis_cutoff']; batch=data['batch']['batch_id']; portfolio=data['portfolio_filter']
    year=data['year_filter']
    return sql,[cutoff,cutoff,cutoff,batch,year,cutoff,batch,portfolio,portfolio,cutoff,year,cutoff,cutoff]


@page_view
def overview(request, connection):
    data = context(request, connection)
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
    data['analysis_counts']=[('Aplicações',applications),('Movimentações no período',movements)]
    for item in data["issues"]:
        item["label"] = ISSUES.get(item["code"], item["code"])
    return render(request, "dashboard/overview.html", data)


@page_view
def positions(request, connection):
    data = context(request, connection)
    batch = data['batch']['batch_id']
    term = request.GET.get('q','')[:200]
    account = request.GET.get('account','')
    if account and not account.isdecimal():
        raise Http404('Conta inválida')
    data.update(term=term,account_filter=account)
    data['accounts'] = query(connection,'SELECT legacy_id,name FROM portfolio.account WHERE batch_id=? ORDER BY name',[batch])
    data['quantity_flags'] = connection.execute("""SELECT count(*) FROM portfolio.quantity_check q WHERE q.batch_id=?
      AND (?='' OR EXISTS(SELECT 1 FROM portfolio.membership pm WHERE pm.batch_id=q.batch_id AND pm.application_id=q.application_id AND CAST(pm.collection_id AS VARCHAR)=?))
      AND (q.legacy_delta<>0 OR q.legacy_delta IS NULL)""",[batch,data['portfolio_filter'],data['portfolio_filter']]).fetchone()[0]
    scoped,parameters=valuation_query(data)
    data.update(paged(request,connection,
        "SELECT * FROM ("+scoped+") scoped_positions WHERE (?='' OR CAST(account_id AS VARCHAR)=?) AND (?='' OR coalesce(asset_name,name,'') ILIKE ?) ORDER BY account_name,asset_name,legacy_id",
        [*parameters,account,account,term,'%'+term+'%']))
    return render(request,'dashboard/positions.html',data)


@page_view
def allocation(request,connection):
    data=context(request,connection)
    batch=data['batch']['batch_id']
    currency=request.GET.get('currency','')[:20]
    data['currency_filter']=currency
    scoped,parameters=valuation_query(data)
    data['currencies']=query(connection,"SELECT DISTINCT currency FROM ("+scoped+") v WHERE valuation_status<>'closed' ORDER BY currency",parameters)
    totals_sql="""SELECT currency,count(*) AS active_count,count(reference_value) AS priced_count,
      count(*) FILTER(WHERE valuation_status NOT IN ('priced','stale_price')) AS excluded_count,
      count(*) FILTER(WHERE valuation_status='stale_price') AS stale_count,sum(reference_value) AS reference_subtotal
      FROM ("""+scoped+") v WHERE valuation_status<>'closed' AND (?='' OR currency=?) GROUP BY currency ORDER BY currency"
    data['totals']=query(connection,totals_sql,[*parameters,currency,currency])
    allocation_sql="""WITH groups AS (SELECT currency,coalesce(class_name,'Sem classe') class_name,
      sum(reference_value) reference_value FROM ("""+scoped+") v WHERE reference_value IS NOT NULL AND (?='' OR currency=?) GROUP BY currency,coalesce(class_name,'Sem classe')) " + \
      "SELECT *,100.0*reference_value/nullif(sum(reference_value) OVER(PARTITION BY currency),0) percentage FROM groups ORDER BY currency,reference_value DESC"
    data['allocation']=query(connection,allocation_sql,[*parameters,currency,currency])
    data.update(paged(request,connection,"SELECT * FROM ("+scoped+") v WHERE valuation_status<>'closed' AND (?='' OR currency=?) ORDER BY currency,valuation_status,asset_name,legacy_id",[*parameters,currency,currency]))
    for row in data['rows']:
        row['status_label']=VALUATION_STATUS.get(row['valuation_status'],row['valuation_status'])
    return render(request,'dashboard/allocation.html',data)


@page_view
def prices(request, connection):
    data = context(request, connection)
    batch = data['batch']['batch_id']
    term = request.GET.get('q', '')[:200]
    provider = request.GET.get('provider', '')[:100]
    data.update(term=term, provider_filter=provider)
    asset_scope="""(?='' OR EXISTS(SELECT 1 FROM portfolio.application ap JOIN portfolio.membership pm ON pm.batch_id=ap.batch_id AND pm.application_id=ap.legacy_id WHERE ap.batch_id=a.batch_id AND ap.asset_id=a.legacy_id AND CAST(pm.collection_id AS VARCHAR)=?))"""
    data['captures'] = query(connection, '''SELECT c.capture_id,c.requested_symbol,c.captured_at,c.quoted_at,c.price,c.currency,c.status,c.reason,c.source_record_id
        FROM market.quote_capture c JOIN source_record r ON r.record_id=c.source_record_id
        JOIN market.asset_catalog a ON a.source_record_id=r.record_id
        WHERE r.batch_id=? AND '''+asset_scope+' ORDER BY c.captured_at DESC,c.capture_id LIMIT 50', [batch,data['portfolio_filter'],data['portfolio_filter']])
    data['providers'] = query(connection, "SELECT DISTINCT configured_provider FROM market.asset_catalog a WHERE batch_id=? AND nullif(trim(configured_provider),'') IS NOT NULL AND "+asset_scope+" ORDER BY configured_provider", [batch,data['portfolio_filter'],data['portfolio_filter']])
    data['quality'] = query(connection, 'SELECT quality,count(*) AS count FROM market.price_observation p JOIN market.asset_catalog a ON a.source_record_id=p.source_record_id WHERE p.batch_id=? AND '+asset_scope+' GROUP BY quality ORDER BY quality', [batch,data['portfolio_filter'],data['portfolio_filter']])
    labels = {'missing_price':'Sem preço','invalid_price':'Preço inválido','missing_currency':'Sem moeda',
              'missing_date':'Sem data','future_price':'Posterior ao corte','stale_price':'Antiga (>30 dias)', 'available':'Disponível no corte'}
    for row in data['quality']:
        row['label'] = labels[row['quality']]
    data['identifiers'] = connection.execute('SELECT count(*) FROM market.identifier_candidate i JOIN market.asset_catalog a ON a.source_record_id=i.source_record_id WHERE i.batch_id=? AND '+asset_scope, [batch,data['portfolio_filter'],data['portfolio_filter']]).fetchone()[0]
    data['duplicates'] = connection.execute('SELECT count(*) FROM market.identifier_candidate i JOIN market.asset_catalog a ON a.source_record_id=i.source_record_id WHERE i.batch_id=? AND i.occurrences>1 AND '+asset_scope, [batch,data['portfolio_filter'],data['portfolio_filter']]).fetchone()[0]
    data.update(paged(request, connection, """
        SELECT a.*,p.quality,p.age_at_cutoff_days,p.captured_at,
          (SELECT count(*) FROM market.identifier_candidate i WHERE i.source_record_id=a.source_record_id AND i.occurrences>1) AS duplicate_identifiers
        FROM market.asset_catalog a JOIN market.price_observation p ON p.observation_id=a.source_record_id
        WHERE a.batch_id=? AND (?='' OR a.configured_provider=?)
          AND (?='' OR EXISTS(SELECT 1 FROM portfolio.application ap JOIN portfolio.membership pm ON pm.batch_id=ap.batch_id AND pm.application_id=ap.legacy_id WHERE ap.batch_id=a.batch_id AND ap.asset_id=a.legacy_id AND CAST(pm.collection_id AS VARCHAR)=?))
          AND (?='' OR concat_ws(' ',a.name,a.symbol,a.legacy_code,a.legacy_cnpj) ILIKE ?)
        ORDER BY a.name,a.legacy_id
        """, [batch,provider,provider,data['portfolio_filter'],data['portfolio_filter'],term,'%'+term+'%']))
    for row in data['rows']:
        row['quality_label'] = labels[row['quality']]
    return render(request, 'dashboard/prices.html', data)


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
            collection=int(data['portfolio_filter']) if data['portfolio_filter'] else None
        job_id,created=create_price_job(settings.WAREHOUSE_PATH,batch,collection)
        return JsonResponse({'job_id':job_id,'created':created},status=202)
    except (Unavailable,OSError):
        return JsonResponse({'error':'Banco indisponível para atualização'},status=503)


@require_safe
def price_update_status(request):
    try:
        with reader(settings.WAREHOUSE_PATH) as connection:
            rows=query(connection,"SELECT * FROM price_update_job ORDER BY created_at DESC LIMIT 1")
            last=connection.execute("SELECT max(captured_at) FROM market.quote_capture WHERE status='accepted'").fetchone()[0]
        if not rows:return JsonResponse({'status':'idle','message':'Nenhuma atualização executada','last_price_update':last})
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
    data.update(paged(request,connection,"SELECT * FROM portfolio.quantity_detail WHERE batch_id=? AND application_id=? AND (?='' OR year(coalesce(settlement_date,trade_date))=CAST(? AS INTEGER)) ORDER BY settlement_date NULLS LAST,trade_date,legacy_id",[item['batch_id'],item['legacy_id'],data['year_filter'],data['year_filter'] or '0']))
    return render(request,'dashboard/quantity_detail.html',data)


@page_view
def cash(request,connection):
    data=context(request,connection)
    batch=data['batch']['batch_id']
    account=request.GET.get('account','')
    if account and not account.isdecimal():
        raise Http404('Conta inválida')
    currency=request.GET.get('currency','')[:20]
    data.update(account_filter=account,currency_filter=currency)
    data['currencies']=query(connection,'SELECT DISTINCT currency FROM portfolio.cash_check WHERE batch_id=? ORDER BY currency',[batch])
    scope="""(?='' OR EXISTS(SELECT 1 FROM portfolio.application ap JOIN portfolio.membership pm ON pm.batch_id=ap.batch_id AND pm.application_id=ap.legacy_id WHERE ap.batch_id=c.batch_id AND ap.account_id=c.legacy_id AND CAST(pm.collection_id AS VARCHAR)=?))"""
    data['accounts']=query(connection,"SELECT c.* FROM portfolio.cash_check c WHERE c.batch_id=? AND (?='' OR currency=?) AND "+scope+" ORDER BY currency,name",[batch,currency,currency,data['portfolio_filter'],data['portfolio_filter']])
    data['unassigned']=connection.execute("SELECT count(*) FROM portfolio.cash_detail WHERE batch_id=? AND account_id IS NULL AND (?='' OR year(settlement_date)=CAST(? AS INTEGER))",[batch,data['year_filter'],data['year_filter'] or '0']).fetchone()[0]
    data['period_summary']=query(connection,"""SELECT c.currency,count(d.legacy_id) entry_count,
      sum(d.signed_value) FILTER(WHERE d.signed_value>0) credits,
      -sum(d.signed_value) FILTER(WHERE d.signed_value<0) debits,sum(d.signed_value) net_flow
      FROM portfolio.cash_check c LEFT JOIN portfolio.cash_detail d ON d.batch_id=c.batch_id AND d.account_id=c.legacy_id
        AND (?='' OR year(d.settlement_date)=CAST(? AS INTEGER))
      WHERE c.batch_id=? AND (?='' OR c.currency=?) AND """+scope+" GROUP BY c.currency ORDER BY c.currency",
      [data['year_filter'],data['year_filter'] or '0',batch,currency,currency,data['portfolio_filter'],data['portfolio_filter']])
    if account:
        selected=query(connection,'SELECT c.* FROM portfolio.cash_check c WHERE c.batch_id=? AND c.legacy_id=? AND '+scope,[batch,int(account),data['portfolio_filter'],data['portfolio_filter']])
        if not selected:
            raise Http404('Conta não encontrada')
        data['selected']=selected[0]
        data.update(paged(request,connection,"SELECT * FROM portfolio.cash_detail WHERE batch_id=? AND account_id=? AND (?='' OR year(settlement_date)=CAST(? AS INTEGER)) ORDER BY settlement_timestamp NULLS FIRST,legacy_id",[batch,int(account),data['year_filter'],data['year_filter'] or '0']))
    return render(request,'dashboard/cash.html',data)


@page_view
def records(request, connection):
    data = context(request, connection)
    table, term = request.GET.get("table", ""), request.GET.get("q", "")[:200]
    data.update(table_filter=table, term=term)
    data["tables"] = query(connection,"SELECT DISTINCT table_name FROM source_table WHERE batch_id=? ORDER BY table_name",[data["batch"]["batch_id"]])
    data.update(paged(request, connection,
        "SELECT record_id,table_name,legacy_id,coalesce(json_extract_string(payload,'$.nome'),json_extract_string(payload,'$.descricao'),json_extract_string(payload,'$.item'),'—') AS label FROM source_record WHERE batch_id=? AND (?='' OR table_name=?) AND (?='' OR CAST(payload AS VARCHAR) ILIKE ?) ORDER BY table_name,legacy_id",
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
    data["term"] = term
    data.update(paged(request,connection,"SELECT d.document_id,d.original_filename,d.source_path,d.byte_size,(SELECT count(*) FROM document_record_link l WHERE l.document_id=d.document_id) AS links FROM source_document d WHERE batch_id=? AND (?='' OR original_filename ILIKE ?) ORDER BY original_filename,document_id",[data["batch"]["batch_id"],term,"%"+term+"%"]))
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
    code = request.GET.get("code", "")
    data["code_filter"] = code
    data["codes"] = list(ISSUES.items())
    data.update(paged(request,connection,"SELECT i.code,i.details,r.record_id,r.table_name,r.legacy_id FROM import_issue i LEFT JOIN source_record r USING(record_id) WHERE i.batch_id=? AND (?='' OR i.code=?) ORDER BY i.code,r.legacy_id,i.issue_id",[data["batch"]["batch_id"],code,code]))
    for row in data["rows"]:
        row["label"] = ISSUES.get(row["code"],row["code"])
    return render(request,"dashboard/issues.html",data)
