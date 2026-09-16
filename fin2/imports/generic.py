"""Preview and atomically commit generic CSV/XLSX ledger files."""
from datetime import date,datetime
from decimal import Decimal,InvalidOperation
import csv,hashlib,io,json
from pathlib import Path
from uuid import uuid4

from openpyxl import load_workbook
from warehouse.database import connect,migrate
from fin2.portfolio.manual_ledger import TYPES
from fin2.imports.base import SourceRow
from fin2.imports.registry import register,detect,get

HEADERS=('account','application','type','trade_date','settlement_date','currency','quantity','amount','description')
LIMIT=5*1024*1024

def _rows(body,extension):
    if extension=='.csv':
        text=body.decode('utf-8-sig')
        return [SourceRow({'line':number},row) for number,row in enumerate(csv.DictReader(io.StringIO(text)),2)]
    if extension=='.xlsx':
        book=load_workbook(io.BytesIO(body),read_only=True,data_only=True,keep_links=False)
        try:
            values=book.active.iter_rows(values_only=True);headers=[str(v or '').strip() for v in next(values)]
            return [SourceRow({'sheet':book.active.title,'row':number},dict(zip(headers,row)))
                    for number,row in enumerate(values,2) if any(v is not None and str(v).strip() for v in row)]
        finally: book.close()
    raise ValueError('Formato permitido: CSV ou XLSX')

def _day(value,required=False):
    if value in (None,''):
        if required: raise ValueError('data obrigatória')
        return None
    if isinstance(value,(date,datetime)): return value.date() if isinstance(value,datetime) else value
    return date.fromisoformat(str(value).strip())

def _decimal(value,scale,required=False):
    if value in (None,''):
        if required: raise ValueError('valor obrigatório')
        return None
    number=Decimal(str(value).strip().replace('.','').replace(',','.')) if isinstance(value,str) and ',' in value else Decimal(str(value))
    if not number.is_finite(): raise ValueError
    return number.quantize(Decimal(1).scaleb(-scale))


class GenericLedgerAdapter:
    adapter_id='generic-ledger';version='1';document_type='transaction_file'
    def detect(self,filename,body):
        extension=Path(filename).suffix.lower()
        if extension=='.xlsx' and body.startswith(b'PK\x03\x04'):return 80
        if extension=='.csv':
            try:header=body[:4096].decode('utf-8-sig').splitlines()[0]
            except (UnicodeDecodeError,IndexError):return 0
            return 90 if all(name in next(csv.reader([header])) for name in HEADERS) else 0
        return 0
    def parse(self,filename,body):return _rows(body,Path(filename).suffix.lower())
    def normalize(self,source,db,options=None):
        row=source.values;errors=[];normalized={'row_number':source.locator.get('line') or source.locator.get('row'),'source_locator':source.locator}
        try:
            account=str(row['account'] or '').strip()
            found=db.execute("""select source_record_id,name from portfolio.account
              where source_record_id=? or lower(name)=lower(?)""",[account,account]).fetchall()
            if len(found)!=1:raise ValueError('conta desconhecida ou ambígua')
            normalized.update(account_record=found[0][0],account=found[0][1])
            application=str(row['application'] or '').strip()
            if application:
                apps=db.execute("""select source_record_id,name from portfolio.application
                  where (source_record_id=? or lower(name)=lower(?))
                    and account_id=(select legacy_id from portfolio.account where source_record_id=?)""",
                  [application,application,found[0][0]]).fetchall()
                if len(apps)!=1:raise ValueError('aplicação desconhecida ou ambígua')
                normalized.update(application_record=apps[0][0],application=apps[0][1])
            else:normalized.update(application_record=None,application='')
            event_type=str(row['type'] or '').strip().lower()
            if event_type not in TYPES:raise ValueError('tipo inválido')
            description=' '.join(str(row['description'] or '').split())
            if not description or len(description)>500:raise ValueError('descrição inválida')
            currency=str(row['currency'] or '').strip().upper()
            currency={'REAL':'BRL','DOL':'USD','DOLAR':'USD'}.get(currency,currency)
            normalized.update(event_type=event_type,trade_date=str(_day(row['trade_date'])) if row['trade_date'] else None,
              settlement_date=str(_day(row['settlement_date'],True)),currency=currency,
              quantity=str(_decimal(row['quantity'],10)) if row['quantity'] not in (None,'') else None,
              amount=str(_decimal(row['amount'],4,True)),description=description)
            if not normalized['currency'] or len(normalized['currency'])>10:raise ValueError('moeda inválida')
        except (ValueError,InvalidOperation,KeyError) as exc:errors.append(str(exc) or 'valor inválido')
        normalized['errors']=errors
        return normalized


GENERIC_ADAPTER=register(GenericLedgerAdapter())

def stage(database,storage_root,filename,body,media_type='application/octet-stream',options=None):
    if not body or len(body)>LIMIT: raise ValueError('Arquivo vazio ou maior que 5 MiB')
    from fin2.imports.clear_brokerage import CLEAR_ADAPTER  # register built-in PDF adapter
    from fin2.imports.apex_statement import APEX_ADAPTER
    from fin2.imports.bb_fixed_income import BB_FIXED_INCOME_ADAPTER
    from fin2.imports.xp_statement import XP_ADAPTER
    selected=(options or {}).get('adapter_id')
    if selected:adapter=get(selected);confidence=100
    else:adapter,confidence=detect(filename,body)
    if adapter.adapter_id=='xp-account-statement':
        from fin2.imports.xp_reconciliation import stage as stage_xp
        return stage_xp(database,storage_root,filename,body,media_type,options or {})
    raw=list(adapter.parse(filename,body))
    if not raw: raise ValueError('Arquivo sem lançamentos')
    missing=[h for h in HEADERS if h not in raw[0].values] if adapter.adapter_id=='generic-ledger' else []
    if missing: raise ValueError('Colunas ausentes: '+', '.join(missing))
    digest=hashlib.sha256(body).hexdigest();import_id=uuid4().hex;preview=[]
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        existing=db.execute('select import_id,status from ledger.file_import where sha256=?',[digest]).fetchone()
        if existing: return existing[0],existing[1]
        for source in raw:preview.append(adapter.normalize(source,db,options or {}))
        root=Path(storage_root).resolve();target=root/'imports'/digest[:2]/digest
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists(): target.write_bytes(body)
        account_records=sorted({row.get('account_record') for row in preview if row.get('account_record')})
        batches=db.execute('select distinct batch_id from portfolio.account where source_record_id in ('+
          ','.join('?' for _ in account_records)+')',account_records).fetchall() if account_records else []
        batch_id=batches[0][0] if len(batches)==1 else None
        document_id=hashlib.sha256(f'{batch_id}:file-import:{digest}'.encode()).hexdigest() if batch_id else None
        if document_id:
            db.execute("""insert into source_document
              (document_id,batch_id,source_path,original_filename,sha256,byte_size,storage_key)
              values (?,?,?,?,?,?,?) on conflict do nothing""",
              [document_id,batch_id,f'FIN2/imports/{digest}/{Path(filename).name}',Path(filename).name,
               digest,len(body),target.relative_to(root).as_posix()])
        metadata=adapter.metadata(filename,body) if hasattr(adapter,'metadata') else None
        db.execute("""insert into ledger.file_import
          (import_id,sha256,original_filename,storage_key,media_type,status,row_count,error_count,preview,
           created_at,committed_at,byte_size,adapter_id,adapter_version,document_type,detection_confidence,
           batch_id,document_id,document_metadata)
          values (?,?,?,?,?,?,?,?,?,now(),NULL,?,?,?,?,?,?,?,?)""",
          [import_id,digest,Path(filename).name,target.relative_to(root).as_posix(),media_type,'preview',len(preview),sum(bool(r['errors']) for r in preview),json.dumps(preview,ensure_ascii=False),len(body),adapter.adapter_id,adapter.version,adapter.document_type,confidence,batch_id,document_id,json.dumps(metadata) if metadata else None])
    return import_id,'preview'

def commit(database,import_id):
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        adapter=db.execute('select adapter_id from ledger.file_import where import_id=?',[import_id]).fetchone()
    if adapter and adapter[0]=='xp-account-statement':
        from fin2.imports.xp_reconciliation import commit as commit_xp
        return commit_xp(database,import_id)
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db);item=db.execute("select status,error_count,preview,document_id,document_metadata,batch_id from ledger.file_import where import_id=?",[import_id]).fetchone()
        if not item or item[0]!='preview': raise ValueError('Pré-visualização indisponível')
        if item[1]: raise ValueError('Corrija os erros antes de importar')
        rows=json.loads(item[2]);document_id=item[3];metadata=json.loads(item[4]) if item[4] else None;db.execute('BEGIN')
        try:
            created=[]
            for row in rows:
                event_id=uuid4().hex
                db.execute("""insert into ledger.manual_event
                  (event_id,account_source_record_id,application_source_record_id,event_type,
                   trade_date,settlement_date,currency,quantity,amount,description,reverses_event_id,created_at)
                  values (?,?,?,?,?,?,?,?,?,?,NULL,now())""",
                  [event_id,row['account_record'],row['application_record'],row['event_type'],row['trade_date'],row['settlement_date'],row['currency'],row['quantity'],row['amount'],row['description']])
                db.execute("insert into ledger.audit_log(audit_id,entity_type,entity_id,action,payload) values (?,'manual_event',?,'create',?)",
                  [uuid4().hex,event_id,json.dumps({'source_import_id':import_id,'row_number':row['row_number']})])
                db.execute('insert into ledger.file_import_event(import_id,row_number,event_id,source_locator) values (?,?,?,?)',
                  [import_id,row['row_number'],event_id,json.dumps(row['source_locator'],ensure_ascii=False)])
                if document_id:db.execute('insert into ledger.manual_event_document(event_id,document_id) values (?,?)',[event_id,document_id])
                if row.get('investment_terms'):
                    terms=row['investment_terms']
                    db.execute("""insert into ledger.file_import_investment_term
                      (event_id,product_name,unit_price,yield_text,maturity_year,institution,protocol)
                      values (?,?,?,?,?,?,?)""",[event_id,terms['product_name'],terms.get('unit_price'),
                      terms.get('yield_text'),terms.get('maturity_year'),terms.get('institution'),terms.get('protocol')])
                created.append((row,event_id))
            trades=[(row,event_id,Decimal(row['allocation_weight'])) for row,event_id in created if row.get('allocation_role')=='trade']
            total_weight=sum((weight for _,_,weight in trades),Decimal('0'))
            if total_weight:
                for expense,expense_id in ((row,event_id) for row,event_id in created if row.get('allocation_role')=='expense'):
                    total=abs(Decimal(expense['amount']));remaining=total
                    for index,(_,trade_id,weight) in enumerate(trades):
                        allocated=remaining if index==len(trades)-1 else (total*weight/total_weight).quantize(Decimal('.0001'))
                        remaining-=allocated
                        db.execute("""insert into ledger.file_import_event_allocation
                          (expense_event_id,trade_event_id,amount) values (?,?,?)""",
                          [expense_id,trade_id,allocated])
            if metadata and document_id:
                account=next((row.get('account_record') for row in rows if row.get('account_record')),None)
                observation_id=hashlib.sha256(f'{import_id}:statement-balance'.encode()).hexdigest()
                db.execute("""insert into ledger.statement_balance_observation
                  (observation_id,batch_id,account_record_id,document_id,period_start,period_end,currency,
                   opening_balance,closing_balance,source_page,note) values (?,?,?,?,?,?,?,?,?,?,?)""",
                  [observation_id,item[5],account,document_id,metadata['period_start'],metadata['period_end'],
                   metadata['currency'],metadata['opening_balance'],metadata['closing_balance'],
                   metadata.get('source_page'),'Importado automaticamente do extrato'])
            db.execute("update ledger.file_import set status='committed',committed_at=now() where import_id=?",[import_id]);db.execute('COMMIT')
        except Exception: db.execute('ROLLBACK');raise
    return len(rows)


def reject(database,storage_root,import_id):
    """Discard a staged import for good: rows, document and stored file.

    Rejecting at the approval step is not a decision that gets recorded; the
    import simply stops existing and the process returns to the upload step.
    """
    root=Path(storage_root).resolve();forget_file=False
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        item=db.execute('select status,document_id,storage_key from ledger.file_import where import_id=?',[import_id]).fetchone()
        if not item or item[0]!='preview':raise ValueError('Pré-visualização indisponível')
        document_id,storage_key=item[1],item[2]
        db.execute('BEGIN')
        try:
            db.execute('delete from ledger.xp_statement_decision where import_id=?',[import_id])
            db.execute('delete from ledger.xp_statement_line where import_id=?',[import_id])
            db.execute('delete from ledger.xp_statement where import_id=?',[import_id])
            db.execute('delete from ledger.file_import where import_id=?',[import_id])
            # The document and the stored file are content-addressed; drop them
            # only when no other import still points at them.
            if document_id and not db.execute('select 1 from ledger.file_import where document_id=?',[document_id]).fetchone():
                db.execute('delete from ledger.statement_balance_observation where document_id=?',[document_id])
                db.execute(
                    'delete from document_record_link where document_id=?', [document_id])
            db.execute('COMMIT')
            if document_id:
                db.execute('delete from source_document where document_id=?',[document_id])
            forget_file = bool(storage_key) and not db.execute(
                'select 1 from source_document where storage_key=?', [storage_key]).fetchone()
        except Exception:
            db.execute('ROLLBACK')
            raise
    if forget_file:
        target=(root/storage_key).resolve()
        if target.is_relative_to(root) and target.is_file():target.unlink()
    return import_id
