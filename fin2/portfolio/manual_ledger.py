"""Validated, serialized writes to Fin2's canonical manual ledger."""

from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

from warehouse.database import connect, migrate

TYPES = {'deposit','withdrawal','buy','sell','redemption','income','fee','tax','adjustment'}
POSITIVE_TYPES={'deposit','sell','redemption','income'}
NEGATIVE_TYPES={'withdrawal','buy','fee','tax'}
REVERSE_TYPE = {'deposit':'withdrawal','withdrawal':'deposit','buy':'sell','sell':'buy',
                'redemption':'adjustment','income':'adjustment','fee':'adjustment','tax':'adjustment','adjustment':'adjustment'}
DOCUMENT_LIMIT=10*1024*1024
DOCUMENT_TYPES={'.pdf':'application/pdf','.png':'image/png','.jpg':'image/jpeg',
                '.jpeg':'image/jpeg','.webp':'image/webp'}


def _prepare_document(storage_root,batch,filename,body):
    name=Path(filename or '').name
    extension=Path(name).suffix.lower()
    if extension not in DOCUMENT_TYPES:
        raise ValueError('Comprovante deve ser PDF, PNG, JPG ou WEBP')
    if not body or len(body)>DOCUMENT_LIMIT:
        raise ValueError('Comprovante vazio ou maior que 10 MiB')
    valid=(body.startswith(b'%PDF-') if extension=='.pdf' else
           body.startswith(b'\x89PNG\r\n\x1a\n') if extension=='.png' else
           body.startswith(b'\xff\xd8\xff') if extension in {'.jpg','.jpeg'} else
           len(body)>=12 and body.startswith(b'RIFF') and body[8:12]==b'WEBP')
    if not valid: raise ValueError('Conteúdo do comprovante incompatível com a extensão')
    digest=hashlib.sha256(body).hexdigest()
    document_id=hashlib.sha256(f'{batch}:fin2-manual:{digest}'.encode()).hexdigest()
    root=Path(storage_root).resolve();target=root/'manual'/digest[:2]/digest
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists(): target.write_bytes(body)
    return {'document_id':document_id,'batch_id':batch,'source_path':f'FIN2/manual/{digest}/{name}',
            'original_filename':name,'storage_key':target.relative_to(root).as_posix(),
            'sha256':digest,'byte_size':len(body),'media_type':DOCUMENT_TYPES[extension]}


def _put_document(db,item):
    db.execute("""insert into source_document
      (document_id,batch_id,source_path,original_filename,storage_key,sha256,byte_size)
      values (?,?,?,?,?,?,?) on conflict do nothing""",
      [item[key] for key in ('document_id','batch_id','source_path','original_filename','storage_key','sha256','byte_size')])
    return item['document_id']


def decimal(value, scale, name, optional=False):
    if optional and (value is None or value == ''):
        return None
    try:
        result=Decimal(str(value))
    except (InvalidOperation,ValueError):
        raise ValueError(f'{name} inválido')
    if not result.is_finite(): raise ValueError(f'{name} inválido')
    return result.quantize(Decimal(1).scaleb(-scale))


def _account(db,record):
    row=db.execute("""select a.batch_id,c.abbreviation from portfolio.account a
      left join portfolio.currency c on c.batch_id=a.batch_id and c.legacy_id=a.currency_id
      where a.source_record_id=?""",[record]).fetchone()
    if not row: raise ValueError('Conta desconhecida')
    aliases={'REAL':'BRL','DOL':'USD','DOLAR':'USD'}
    return row[0],aliases.get(str(row[1] or '').upper(),str(row[1] or '').upper())


def create(database, *, account_record, event_type, settlement_date, currency,
           amount, description, application_record=None, trade_date=None, quantity=None,
           document_id=None,request_key=None,upload_filename=None,upload_body=None,storage_root=None,
           funding_source=None):
    request_key=str(request_key or uuid4().hex)
    if not re.fullmatch(r'[a-f0-9]{32}',request_key):raise ValueError('Chave de envio inválida')
    if event_type not in TYPES: raise ValueError('Tipo de evento inválido')
    if event_type == 'buy':
        funding_source = funding_source or 'result_account'
        if funding_source not in {'result_account','investment_balance','dividends','sales','portability'}:
            raise ValueError('Origem dos recursos inválida')
    else:
        funding_source = None
    try:
        settlement=date.fromisoformat(str(settlement_date))
        trade=date.fromisoformat(str(trade_date)) if trade_date else None
    except ValueError: raise ValueError('Data inválida')
    description=' '.join(str(description).split())
    if not description or len(description)>500: raise ValueError('Descrição inválida')
    currency=str(currency).strip().upper()
    if not currency or len(currency)>10: raise ValueError('Moeda inválida')
    money=decimal(amount,4,'Valor'); qty=decimal(quantity,10,'Quantidade',True)
    if qty is not None and qty<0: raise ValueError('Quantidade não pode ser negativa')
    if event_type in POSITIVE_TYPES and money<=0: raise ValueError('O valor desta operação deve ser positivo')
    if event_type in NEGATIVE_TYPES and money>=0: raise ValueError('O valor desta operação deve ser negativo')
    if event_type in {'buy','sell','redemption'} and (not application_record or qty is None or qty<=0):
        raise ValueError('Compra, venda e resgate exigem aplicação e quantidade positiva')
    if event_type not in {'buy','sell','redemption','adjustment'} and qty is not None:
        raise ValueError('Quantidade não se aplica a este tipo de evento')
    event_id=uuid4().hex; audit_id=uuid4().hex
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        existing=db.execute('select event_id from ledger.manual_event where request_key=?',[request_key]).fetchone()
        if existing:return existing[0]
        account=_account(db,account_record)
        if document_id and upload_body: raise ValueError('Escolha um documento existente ou um novo comprovante')
        prepared=_prepare_document(storage_root,account[0],upload_filename,upload_body) if upload_body else None
        aliases={'REAL':'BRL','DOL':'USD','DOLAR':'USD'}
        account_currency=aliases.get(str(account[1] or '').upper(),str(account[1] or '').upper())
        normalized_currency=aliases.get(currency,currency)
        if account_currency and normalized_currency!=account_currency:
            raise ValueError(f'Moeda incompatível com a conta ({account_currency})')
        if application_record:
            application=db.execute('select batch_id,account_id from portfolio.application where source_record_id=?',[application_record]).fetchone()
            account_id=db.execute('select legacy_id from portfolio.account where source_record_id=?',[account_record]).fetchone()[0]
            if not application or application[0]!=account[0] or application[1]!=account_id:
                raise ValueError('Aplicação não pertence à conta')
        if document_id:
            document=db.execute('select batch_id from source_document where document_id=?',[document_id]).fetchone()
            if not document or document[0]!=account[0]: raise ValueError('Documento desconhecido neste lote')
        payload={'event_id':event_id,'account_source_record_id':account_record,
                 'application_source_record_id':application_record,'event_type':event_type,
                 'trade_date':str(trade) if trade else None,'settlement_date':str(settlement),
                 'currency':normalized_currency,'quantity':str(qty) if qty is not None else None,
                 'amount':str(money),'description':description,'document_id':document_id,
                 'funding_source':funding_source}
        db.execute('BEGIN')
        try:
            if prepared: document_id=_put_document(db,prepared)
            if document_id:
                db.execute('insert into document_record_link(document_id,record_id,relation) values (?,?,?) on conflict do nothing',
                           [document_id, account_record, 'account_document'])
            db.execute("""insert into ledger.manual_event
              (event_id,account_source_record_id,application_source_record_id,event_type,trade_date,
               settlement_date,currency,quantity,amount,description,reverses_event_id,created_at,transfer_id,request_key)
              values (?,?,?,?,?,?,?,?,?,?,?,now(),NULL,?)""",
              [event_id,account_record,application_record,event_type,trade,settlement,normalized_currency,qty,money,description,None,request_key])
            if funding_source:
                db.execute('insert into ledger.purchase_funding values (?,?)',[event_id,funding_source])
            db.execute("insert into ledger.audit_log(audit_id,entity_type,entity_id,action,payload) values (?,'manual_event',?,'create',?)",
              [audit_id,event_id,json.dumps(payload,ensure_ascii=False)])
            if document_id:
                db.execute("insert into ledger.manual_event_document(event_id,document_id) values (?,?)",
                           [event_id,document_id])
            db.execute('COMMIT')
        except Exception:
            db.execute('ROLLBACK'); raise
    return event_id


def reverse(database, event_id, description='Reversão'):
    reversal_id=uuid4().hex; audit_id=uuid4().hex
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        original=db.execute("""select account_source_record_id,application_source_record_id,event_type,
          trade_date,settlement_date,currency,quantity,amount,transfer_id from ledger.manual_event where event_id=?""",[event_id]).fetchone()
        if not original: raise ValueError('Evento desconhecido')
        if original[8]: raise ValueError('Use o estorno da transferência para reverter os dois lados')
        if db.execute('select 1 from ledger.manual_event where reverses_event_id=?',[event_id]).fetchone():
            raise ValueError('Evento já revertido')
        description=' '.join(str(description).split()) or 'Reversão'
        payload={'event_id':reversal_id,'reverses_event_id':event_id,'amount':str(-original[7])}
        db.execute('BEGIN')
        try:
            db.execute("""insert into ledger.manual_event
              (event_id,account_source_record_id,application_source_record_id,event_type,trade_date,
               settlement_date,currency,quantity,amount,description,reverses_event_id,created_at,transfer_id)
              values (?,?,?,?,?,?,?,?,?,?,?,now(),NULL)""",
              [reversal_id,original[0],original[1],REVERSE_TYPE[original[2]],original[3],
               original[4],original[5],original[6],-original[7],description,event_id])
            db.execute("insert into ledger.audit_log(audit_id,entity_type,entity_id,action,payload) values (?,'manual_event',?,'reverse',?)",
              [audit_id,reversal_id,json.dumps(payload,ensure_ascii=False)])
            db.execute('COMMIT')
        except Exception:
            db.execute('ROLLBACK'); raise
    return reversal_id


def correct(database,event_id,*,settlement_date,amount,description,quantity=None,request_key=None):
    """Atomically reverse one event and append its corrected replacement."""
    request_key=str(request_key or uuid4().hex)
    if not re.fullmatch(r'[a-f0-9]{32}',request_key): raise ValueError('Chave de envio inválida')
    try: settlement=date.fromisoformat(str(settlement_date))
    except ValueError: raise ValueError('Data inválida')
    description=' '.join(str(description).split())
    if not description or len(description)>500: raise ValueError('Descrição inválida')
    money=decimal(amount,4,'Valor');qty=decimal(quantity,10,'Quantidade',True)
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        existing=db.execute('select event_id from ledger.manual_event where request_key=?',[request_key]).fetchone()
        if existing:return existing[0]
        original=db.execute("""select account_source_record_id,application_source_record_id,event_type,
          trade_date,settlement_date,currency,quantity,amount,transfer_id from ledger.manual_event where event_id=?""",[event_id]).fetchone()
        if not original:raise ValueError('Evento desconhecido')
        if original[8]:raise ValueError('Transferências devem ser corrigidas por estorno e nova transferência')
        if db.execute('select 1 from ledger.manual_event where reverses_event_id=?',[event_id]).fetchone():
            raise ValueError('Evento já revertido')
        event_type=original[2]
        if event_type in POSITIVE_TYPES and money<=0:raise ValueError('O valor desta operação deve ser positivo')
        if event_type in NEGATIVE_TYPES and money>=0:raise ValueError('O valor desta operação deve ser negativo')
        if event_type in {'buy','sell','redemption'} and (qty is None or qty<=0):
            raise ValueError('Compra, venda e resgate exigem quantidade positiva')
        if event_type not in {'buy','sell','redemption','adjustment'} and qty is not None:
            raise ValueError('Quantidade não se aplica a este tipo de evento')
        reversal_id=uuid4().hex;replacement_id=uuid4().hex
        documents=[row[0] for row in db.execute('select document_id from ledger.manual_event_document where event_id=?',[event_id]).fetchall()]
        db.execute('BEGIN')
        try:
            db.execute("""insert into ledger.manual_event
              (event_id,account_source_record_id,application_source_record_id,event_type,trade_date,
               settlement_date,currency,quantity,amount,description,reverses_event_id,created_at,transfer_id)
              values (?,?,?,?,?,?,?,?,?,?,?,now(),NULL)""",
              [reversal_id,original[0],original[1],REVERSE_TYPE[event_type],original[3],original[4],
               original[5],original[6],-original[7],'Reversão para correção',event_id])
            db.execute("""insert into ledger.manual_event
              (event_id,account_source_record_id,application_source_record_id,event_type,trade_date,
               settlement_date,currency,quantity,amount,description,reverses_event_id,created_at,transfer_id,request_key)
              values (?,?,?,?,?,?,?,?,?,?,NULL,now(),NULL,?)""",
              [replacement_id,original[0],original[1],event_type,original[3],settlement,
               original[5],qty,money,description,request_key])
            db.execute('''insert into ledger.purchase_funding
                select ?,source from ledger.purchase_funding where event_id=?''',
                [replacement_id,event_id])
            for document_id in documents:
                db.execute('insert into ledger.manual_event_document(event_id,document_id) values (?,?)',[reversal_id,document_id])
                db.execute('insert into ledger.manual_event_document(event_id,document_id) values (?,?)',[replacement_id,document_id])
            payload={'original_event_id':event_id,'reversal_event_id':reversal_id,
                     'replacement_event_id':replacement_id,'amount':str(money),
                     'quantity':str(qty) if qty is not None else None,'settlement_date':str(settlement)}
            db.execute("insert into ledger.audit_log(audit_id,entity_type,entity_id,action,payload) values (?,'manual_event',?,'reverse',?)",
              [uuid4().hex,reversal_id,json.dumps(payload,ensure_ascii=False)])
            db.execute("insert into ledger.audit_log(audit_id,entity_type,entity_id,action,payload) values (?,'manual_event',?,'create',?)",
              [uuid4().hex,replacement_id,json.dumps(payload,ensure_ascii=False)])
            db.execute('COMMIT')
        except Exception:db.execute('ROLLBACK');raise
    return replacement_id


def create_transfer(database,*,source_account,destination_account,settlement_date,amount,
                    description,document_id=None,reverses_transfer_id=None,request_key=None,
                    upload_filename=None,upload_body=None,storage_root=None):
    request_key=str(request_key or uuid4().hex)
    if not re.fullmatch(r'[a-f0-9]{32}',request_key):raise ValueError('Chave de envio inválida')
    if source_account==destination_account: raise ValueError('Selecione contas diferentes')
    try: settlement=date.fromisoformat(str(settlement_date))
    except ValueError: raise ValueError('Data inválida')
    money=decimal(amount,4,'Valor')
    if money<=0: raise ValueError('O valor da transferência deve ser positivo')
    description=' '.join(str(description).split())
    if not description or len(description)>500: raise ValueError('Descrição inválida')
    transfer_id=uuid4().hex;out_id=uuid4().hex;in_id=uuid4().hex;audit_id=uuid4().hex
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        existing=db.execute('select transfer_id from ledger.manual_transfer where request_key=?',[request_key]).fetchone()
        if existing:return existing[0]
        source_batch,source_currency=_account(db,source_account)
        destination_batch,destination_currency=_account(db,destination_account)
        if source_batch!=destination_batch: raise ValueError('As contas pertencem a lotes diferentes')
        if not source_currency or source_currency!=destination_currency:
            raise ValueError('A transferência exige contas na mesma moeda')
        if document_id and upload_body: raise ValueError('Escolha um documento existente ou um novo comprovante')
        prepared=_prepare_document(storage_root,source_batch,upload_filename,upload_body) if upload_body else None
        if document_id:
            row=db.execute('select batch_id from source_document where document_id=?',[document_id]).fetchone()
            if not row or row[0]!=source_batch: raise ValueError('Documento desconhecido neste lote')
        db.execute('BEGIN')
        try:
            if prepared: document_id=_put_document(db,prepared)
            db.execute("""insert into ledger.manual_transfer
              (transfer_id,source_account_record_id,destination_account_record_id,settlement_date,
               currency,amount,description,reverses_transfer_id,request_key) values (?,?,?,?,?,?,?,?,?)""",
              [transfer_id,source_account,destination_account,settlement,source_currency,money,description,reverses_transfer_id,request_key])
            for event_id,account,event_type,value in ((out_id,source_account,'withdrawal',-money),(in_id,destination_account,'deposit',money)):
                db.execute("""insert into ledger.manual_event
                  (event_id,account_source_record_id,event_type,settlement_date,currency,amount,
                   description,created_at,transfer_id) values (?,?,?,?,?,?,?,now(),?)""",
                  [event_id,account,event_type,settlement,source_currency,value,description,transfer_id])
                if document_id: db.execute('insert into ledger.manual_event_document(event_id,document_id) values (?,?)',[event_id,document_id])
            payload={'transfer_id':transfer_id,'source_account':source_account,'destination_account':destination_account,
                     'settlement_date':str(settlement),'currency':source_currency,'amount':str(money),
                     'description':description,'document_id':document_id,'events':[out_id,in_id],
                     'reverses_transfer_id':reverses_transfer_id}
            db.execute("insert into ledger.audit_log(audit_id,entity_type,entity_id,action,payload) values (?,'manual_transfer',?,'create',?)",
                       [audit_id,transfer_id,json.dumps(payload,ensure_ascii=False)])
            db.execute('COMMIT')
        except Exception: db.execute('ROLLBACK');raise
    return transfer_id


def reverse_transfer(database,transfer_id,description='Estorno de transferência'):
    description=' '.join(str(description).split()) or 'Estorno de transferência'
    if len(description)>500: raise ValueError('Descrição inválida')
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        row=db.execute("""select source_account_record_id,destination_account_record_id,
          settlement_date,amount,currency from ledger.manual_transfer where transfer_id=?""",[transfer_id]).fetchone()
        if not row: raise ValueError('Transferência desconhecida')
        if db.execute('select 1 from ledger.manual_transfer where reverses_transfer_id=?',[transfer_id]).fetchone():
            raise ValueError('Transferência já revertida')
        reversal_id=uuid4().hex;out_id=uuid4().hex;in_id=uuid4().hex;audit_id=uuid4().hex
        db.execute('BEGIN')
        try:
            db.execute("""insert into ledger.manual_transfer
              (transfer_id,source_account_record_id,destination_account_record_id,settlement_date,
               currency,amount,description,reverses_transfer_id) values (?,?,?,?,?,?,?,?)""",
              [reversal_id,row[1],row[0],row[2],row[4],row[3],description,transfer_id])
            for event_id,account,event_type,value in ((out_id,row[1],'withdrawal',-row[3]),(in_id,row[0],'deposit',row[3])):
                db.execute("""insert into ledger.manual_event
                  (event_id,account_source_record_id,event_type,settlement_date,currency,amount,
                   description,created_at,transfer_id) values (?,?,?,?,?,?,?,now(),?)""",
                  [event_id,account,event_type,row[2],row[4],value,description,reversal_id])
            payload={'transfer_id':reversal_id,'reverses_transfer_id':transfer_id,
                     'source_account':row[1],'destination_account':row[0],
                     'settlement_date':str(row[2]),'currency':row[4],'amount':str(row[3]),
                     'description':description,'events':[out_id,in_id]}
            db.execute("insert into ledger.audit_log(audit_id,entity_type,entity_id,action,payload) values (?,'manual_transfer',?,'reverse',?)",
                       [audit_id,reversal_id,json.dumps(payload,ensure_ascii=False)])
            db.execute('COMMIT')
        except Exception:db.execute('ROLLBACK');raise
    return reversal_id
