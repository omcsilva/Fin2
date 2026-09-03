"""Validated, serialized writes to Fin2's canonical manual ledger."""

from datetime import date
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from uuid import uuid4

from warehouse.database import connect, migrate

TYPES = {'deposit','withdrawal','buy','sell','income','fee','tax','adjustment'}
REVERSE_TYPE = {'deposit':'withdrawal','withdrawal':'deposit','buy':'sell','sell':'buy',
                'income':'adjustment','fee':'adjustment','tax':'adjustment','adjustment':'adjustment'}


def decimal(value, scale, name, optional=False):
    if optional and (value is None or value == ''):
        return None
    try:
        result=Decimal(str(value))
    except (InvalidOperation,ValueError):
        raise ValueError(f'{name} inválido')
    if not result.is_finite(): raise ValueError(f'{name} inválido')
    return result.quantize(Decimal(1).scaleb(-scale))


def create(database, *, account_record, event_type, settlement_date, currency,
           amount, description, application_record=None, trade_date=None, quantity=None):
    if event_type not in TYPES: raise ValueError('Tipo de evento inválido')
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
    event_id=uuid4().hex; audit_id=uuid4().hex
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        account=db.execute('select batch_id from portfolio.account where source_record_id=?',[account_record]).fetchone()
        if not account: raise ValueError('Conta desconhecida')
        if application_record:
            application=db.execute('select batch_id,account_id from portfolio.application where source_record_id=?',[application_record]).fetchone()
            account_id=db.execute('select legacy_id from portfolio.account where source_record_id=?',[account_record]).fetchone()[0]
            if not application or application[0]!=account[0] or application[1]!=account_id:
                raise ValueError('Aplicação não pertence à conta')
        payload={'event_id':event_id,'account_source_record_id':account_record,
                 'application_source_record_id':application_record,'event_type':event_type,
                 'trade_date':str(trade) if trade else None,'settlement_date':str(settlement),
                 'currency':currency,'quantity':str(qty) if qty is not None else None,
                 'amount':str(money),'description':description}
        db.execute('BEGIN')
        try:
            db.execute('insert into ledger.manual_event values (?,?,?,?,?,?,?,?,?,?,?,now())',
              [event_id,account_record,application_record,event_type,trade,settlement,currency,qty,money,description,None])
            db.execute("insert into ledger.audit_log(audit_id,entity_type,entity_id,action,payload) values (?,'manual_event',?,'create',?)",
              [audit_id,event_id,json.dumps(payload,ensure_ascii=False)])
            db.execute('COMMIT')
        except Exception:
            db.execute('ROLLBACK'); raise
    return event_id


def reverse(database, event_id, description='Reversão'):
    reversal_id=uuid4().hex; audit_id=uuid4().hex
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        original=db.execute("""select account_source_record_id,application_source_record_id,event_type,
          trade_date,settlement_date,currency,quantity,amount from ledger.manual_event where event_id=?""",[event_id]).fetchone()
        if not original: raise ValueError('Evento desconhecido')
        if db.execute('select 1 from ledger.manual_event where reverses_event_id=?',[event_id]).fetchone():
            raise ValueError('Evento já revertido')
        description=' '.join(str(description).split()) or 'Reversão'
        payload={'event_id':reversal_id,'reverses_event_id':event_id,'amount':str(-original[7])}
        db.execute('BEGIN')
        try:
            db.execute('insert into ledger.manual_event values (?,?,?,?,?,?,?,?,?,?,?,now())',
              [reversal_id,original[0],original[1],REVERSE_TYPE[original[2]],original[3],
               original[4],original[5],original[6],-original[7],description,event_id])
            db.execute("insert into ledger.audit_log(audit_id,entity_type,entity_id,action,payload) values (?,'manual_event',?,'reverse',?)",
              [audit_id,reversal_id,json.dumps(payload,ensure_ascii=False)])
            db.execute('COMMIT')
        except Exception:
            db.execute('ROLLBACK'); raise
    return reversal_id
