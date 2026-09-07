"""Audited import of official B3 COTAHIST annual ZIP files."""
from datetime import date,datetime
from decimal import Decimal,InvalidOperation
import hashlib
from io import BytesIO,TextIOWrapper
from zipfile import BadZipFile,ZipFile

MAX_ARCHIVE=256*1024*1024
MAX_TEXT=2*1024*1024*1024


def parse(body, symbols):
    if not body or len(body)>MAX_ARCHIVE:
        raise ValueError('Arquivo B3 vazio ou maior que 64 MiB')
    try:
        with ZipFile(BytesIO(body)) as archive:
            members=[item for item in archive.infolist() if not item.is_dir()]
            if len(members)!=1 or members[0].file_size>MAX_TEXT or members[0].filename.split('/')[-1]!=members[0].filename:
                raise ValueError
            source=TextIOWrapper(archive.open(members[0]),encoding='cp1252',newline=None)
            lines=(line.rstrip('\r\n') for line in source)
            header=next(lines)
            if len(header)!=245 or not header.startswith('00COTAHIST.'):
                raise ValueError
            rows=[]
            for line in lines:
                if len(line)!=245: raise ValueError
                if line.startswith('99'): continue
                if not line.startswith('01'): raise ValueError
                symbol=line[12:24].strip()
                if symbol not in symbols: continue
                market=line[24:27]
                if market!='010': continue
                day=date.fromisoformat(line[2:10][:4]+'-'+line[2:10][4:6]+'-'+line[2:10][6:])
                close=Decimal(line[108:121])/100
                if close<=0: raise ValueError
                rows.append((symbol,day,close))
    except (BadZipFile,KeyError,ValueError):
        raise ValueError('ZIP COTAHIST inválido; nada importado') from None
    except (UnicodeDecodeError,InvalidOperation,StopIteration):
        raise ValueError('Layout COTAHIST incompatível; nada importado') from None
    return rows


def capture(connection, filename, body, captured_at):
    if captured_at.tzinfo is None: raise ValueError('Captura B3 sem fuso horário')
    catalog=connection.execute("""SELECT source_record_id,symbol FROM market.asset_catalog_effective
      WHERE currency='BRL' AND symbol IS NOT NULL""").fetchall()
    by_symbol={}
    for record,symbol in catalog: by_symbol.setdefault(symbol,[]).append((record,None,None))
    for provider,canonical,valid_from,valid_to in connection.execute(
          'SELECT provider_symbol,canonical_symbol,valid_from,valid_to FROM market.asset_symbol_alias').fetchall():
        for record,_,_ in by_symbol.get(canonical,[]):
            by_symbol.setdefault(provider,[]).append((record,valid_from,valid_to))
    rows=parse(body,set(by_symbol))
    ambiguous={symbol for symbol,records in by_symbol.items() if len(records)!=1}
    rows=[row for row in rows if row[0] not in ambiguous and
          (by_symbol[row[0]][0][1] is None or by_symbol[row[0]][0][1]<=row[1]<=by_symbol[row[0]][0][2])]
    digest=hashlib.sha256(body).hexdigest()
    capture_id=hashlib.sha256(('b3_cotahist:'+digest).encode()).hexdigest()
    staged=[(by_symbol[symbol][0][0],day,close) for symbol,day,close in rows]
    connection.execute('DROP TABLE IF EXISTS b3_history_stage')
    connection.execute('CREATE TEMP TABLE b3_history_stage(source_record_id VARCHAR,trading_date DATE,close DECIMAL(28,10))')
    connection.executemany('INSERT INTO b3_history_stage VALUES (?,?,?)',staged)
    connection.execute('BEGIN')
    try:
        connection.execute("""INSERT INTO market.b3_history_capture VALUES
          (?,'b3_cotahist',?,?,?,?) ON CONFLICT DO NOTHING""",
          [capture_id,filename,captured_at,digest,body])
        connection.execute("""INSERT INTO market.b3_daily_close
              SELECT source_record_id,trading_date,'b3_cotahist','BRL',close,NULL,?,?
              FROM b3_history_stage ON CONFLICT DO UPDATE SET
              close=excluded.close,capture_id=excluded.capture_id,captured_at=excluded.captured_at
              WHERE excluded.captured_at>market.b3_daily_close.captured_at""",
              [capture_id,captured_at])
        connection.execute('COMMIT')
        return {'capture_id':capture_id,'points':len(staged),'ambiguous_symbols':sorted(ambiguous)}
    except Exception:
        connection.execute('ROLLBACK');raise
    finally:
        connection.execute('DROP TABLE IF EXISTS b3_history_stage')
