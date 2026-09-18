"""Mutable document rows kept between extraction and ledger commit."""
import json
from pathlib import Path

from warehouse.database import connect, migrate


def seed(connection, import_id, rows):
    """Materialize normalized preview rows without changing raw evidence."""
    for row in rows:
        row_number = int(row['row_number'])
        payload = json.dumps(row, ensure_ascii=False)
        locator = json.dumps(row.get('source_locator') or {}, ensure_ascii=False)
        connection.execute(
            """insert into ledger.import_staging_line
                    (import_id,row_number,source_locator,raw,normalized,state)
                    values (?,?,?,?,?,?) on conflict do nothing""",
                [import_id, row_number, locator, payload, payload,
                 'pending' if row.get('errors') else 'ready'])


def rows(connection, import_id):
    """Return the editable normalized rows for an import."""
    result = connection.execute(
        """select row_number, normalized, state
           from ledger.import_staging_line where import_id=? order by row_number""",
        [import_id]).fetchall()
    return [(number, json.loads(normalized), state) for number, normalized, state in result]


def update(database, import_id, row_number, normalized, state='pending'):
    """Replace one normalized row in the pre-ledger, preserving its raw copy."""
    if state not in {'pending', 'ready', 'rejected'}:
        raise ValueError('Estado de staging inválido')
    if not isinstance(normalized, dict):
        raise ValueError('Linha normalizada inválida')
    with connect(Path(database).resolve(strict=True)) as connection:
        migrate(connection)
        item = connection.execute(
            'select status from ledger.file_import where import_id=?', [import_id]).fetchone()
        if not item or item[0] != 'preview':
            raise ValueError('Pré-visualização indisponível')
        connection.execute('BEGIN')
        try:
            exists = connection.execute(
                """select 1 from ledger.import_staging_line
                   where import_id=? and row_number=?""",
                [import_id, row_number]).fetchone()
            if not exists:
                raise ValueError('Linha de staging desconhecida')
            connection.execute(
                """update ledger.import_staging_line
                   set normalized=?, state=?, updated_at=now()
                   where import_id=? and row_number=?""",
                [json.dumps(normalized, ensure_ascii=False), state, import_id, row_number]).rowcount
            connection.execute('COMMIT')
        except Exception:
            connection.execute('ROLLBACK')
            raise


def load_for_commit(connection, import_id, fallback):
    """Use edited staging rows, falling back for imports created before 0059."""
    staged = rows(connection, import_id)
    return [normalized for _number, normalized, state in staged if state != 'rejected'] or fallback
