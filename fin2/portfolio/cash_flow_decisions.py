"""Immutable, serialized decisions for ambiguous imported cash flows."""
from pathlib import Path
import re
from uuid import uuid4

from warehouse.database import connect, migrate

CATEGORIES={'external_contribution','external_withdrawal','income','fee','tax','investment','internal_transfer'}


def create(database, *, cash_component_id, category, rationale):
    if not re.fullmatch(r'[a-f0-9]{64}',str(cash_component_id)):
        raise ValueError('Lançamento inválido')
    if category not in CATEGORIES:
        raise ValueError('Classificação inválida')
    rationale=' '.join(str(rationale).split())
    if len(rationale)<5 or len(rationale)>500:
        raise ValueError('Informe uma justificativa entre 5 e 500 caracteres')
    decision_id=uuid4().hex
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        row=db.execute('select category from ledger.cash_flow_effective_v3 where cash_component_id=?',[cash_component_id]).fetchone()
        if not row: raise ValueError('Lançamento desconhecido')
        db.execute('BEGIN')
        try:
            db.execute('insert into ledger.cash_flow_decision(decision_id,cash_component_id,category,rationale) values (?,?,?,?)',
                       [decision_id,cash_component_id,category,rationale])
            db.execute('COMMIT')
        except Exception:
            db.execute('ROLLBACK'); raise
    return decision_id
