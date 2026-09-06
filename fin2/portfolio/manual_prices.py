"""Append-only manual quotes and unit valuations, with source attribution."""
from datetime import date
from decimal import Decimal,InvalidOperation
import json,re
from uuid import uuid4
from warehouse.database import connect,migrate


def currency_code(value):
    value=str(value or '').strip().upper()
    return {'REAL':'BRL','DOL':'USD','DOLAR':'USD'}.get(value,value)


def create(database,*,asset_record,price,currency,reference_date,source,note='',document_id=None,request_key):
    if not re.fullmatch('[a-f0-9]{32}',str(request_key or '')):
        raise ValueError('Chave de envio inválida')
    try:
        day=date.fromisoformat(str(reference_date))
        amount=Decimal(str(price))
        if not amount.is_finite() or amount<=0: raise ValueError()
        amount=amount.quantize(Decimal('.0000000001'))
        if amount<=0 or amount>=Decimal('1e18'): raise ValueError()
    except (ValueError,InvalidOperation):
        raise ValueError('Informe uma data válida e um preço positivo, com até 18 dígitos inteiros') from None
    if day>date.today(): raise ValueError('A data da cotação não pode ser futura')
    source=' '.join(str(source).split());note=str(note).strip()
    if not source or len(source)>300: raise ValueError('Informe a fonte da avaliação (até 300 caracteres)')
    if len(note)>1000: raise ValueError('Observação deve ter até 1000 caracteres')
    currency=currency_code(currency)
    with connect(database) as db:
        migrate(db)
        prior=db.execute('SELECT price_id FROM market.manual_price WHERE request_key=?',[request_key]).fetchone()
        if prior:return prior[0]
        asset=db.execute('SELECT batch_id,currency FROM market.asset_catalog_effective WHERE source_record_id=?',[asset_record]).fetchone()
        if not asset: raise ValueError('Ativo desconhecido')
        if not currency or currency!=currency_code(asset[1]):
            raise ValueError('A moeda deve corresponder à moeda cadastrada do ativo')
        if document_id and not db.execute('SELECT 1 FROM source_document WHERE document_id=? AND batch_id=?',[document_id,asset[0]]).fetchone():
            raise ValueError('Documento desconhecido neste lote')
        identifier=uuid4().hex
        payload=dict(price_id=identifier,source_record_id=asset_record,price=str(amount),currency=currency,
            reference_date=str(day),source=source,note=note,document_id=document_id)
        db.execute('BEGIN')
        try:
            db.execute('''INSERT INTO market.manual_price
                (price_id,source_record_id,price,currency,reference_date,source,note,document_id,request_key)
                VALUES (?,?,?,?,?,?,?,?,?)''',[identifier,asset_record,amount,currency,day,source,note,document_id,request_key])
            db.execute("INSERT INTO ledger.audit_log(audit_id,entity_type,entity_id,action,payload) VALUES (?,'manual_price',?,'create',?)",
                [uuid4().hex,identifier,json.dumps(payload,ensure_ascii=False)])
            db.execute('COMMIT')
        except Exception:
            db.execute('ROLLBACK');raise
    return identifier
