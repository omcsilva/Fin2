"""Single-process background quote jobs with durable progress."""
from datetime import datetime, timezone
import hashlib
import json
import re
import threading
from urllib.parse import urlencode

from fin2.portfolio.brapi import ENDPOINT, LIMIT, NoRedirect, capture
from warehouse.database import connect
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

JOB_LOCK = threading.Lock()
START_LOCK = threading.Lock()
ACTIVE_JOB_IDS = set()
CHUNK_SIZE = 20


def _fetch_many(symbols):
    headers={'Accept':'application/json','User-Agent':'Fin2/0.1'}
    import os
    token=os.environ.get('BRAPI_TOKEN')
    if token: headers['Authorization']='Bearer '+token
    url=ENDPOINT+'?'+urlencode({'symbols':','.join(symbols)})
    try:
        with build_opener(NoRedirect()).open(Request(url,headers=headers),timeout=30) as response:
            body=response.read(LIMIT+1)
            if len(body)>LIMIT: raise ValueError('Resposta excede 1 MiB')
            return body,datetime.now(timezone.utc)
    except HTTPError as error:
        code=error.code;error.close();raise ValueError(f'brapi HTTP {code}') from None
    except (URLError,TimeoutError): raise ValueError('Falha de conexão com brapi') from None


def _single_response(body,symbol):
    payload=json.loads(body)
    matches=[r for r in payload.get('results',[]) if r.get('requestedSymbol')==symbol]
    if len(matches)!=1: return body
    return json.dumps({'results':matches},ensure_ascii=False,separators=(',',':')).encode()


def _set(database,job_id,**values):
    columns=','.join(f'{key}=?' for key in values)
    with connect(database) as db:
        db.execute(f'UPDATE price_update_job SET {columns} WHERE job_id=?',[*values.values(),job_id])


def run(database,job_id,batch_id,collection_id=None,fetcher=_fetch_many):
    ACTIVE_JOB_IDS.add(job_id)
    with JOB_LOCK:
        try:
            _set(database,job_id,status='running',started_at=datetime.now(timezone.utc),message='Selecionando ativos compatíveis')
            with connect(database) as db:
                rows=db.execute("""SELECT a.source_record_id,a.symbol FROM market.asset_catalog a
                  WHERE a.batch_id=? AND a.configured_provider='atuBrAPI' AND a.currency IN ('REAL','BRL')
                    AND try_cast(a.configured_multiplier AS DECIMAL(28,10))=1
                    AND regexp_full_match(a.symbol,'[A-Z]{4}[0-9]{1,2}')
                    AND (? IS NULL OR EXISTS(SELECT 1 FROM portfolio.application ap JOIN portfolio.membership pm
                      ON pm.batch_id=ap.batch_id AND pm.application_id=ap.legacy_id
                      WHERE ap.batch_id=a.batch_id AND ap.asset_id=a.legacy_id AND pm.collection_id=?))
                    AND 1=(SELECT count(*) FROM market.asset_catalog x WHERE x.batch_id=a.batch_id AND upper(trim(x.symbol))=a.symbol)
                  ORDER BY a.symbol""",[batch_id,collection_id,collection_id]).fetchall()
                total=db.execute("""SELECT count(*) FROM market.asset_catalog a WHERE a.batch_id=? AND (? IS NULL OR EXISTS(
                  SELECT 1 FROM portfolio.application ap JOIN portfolio.membership pm ON pm.batch_id=ap.batch_id AND pm.application_id=ap.legacy_id
                  WHERE ap.batch_id=a.batch_id AND ap.asset_id=a.legacy_id AND pm.collection_id=?))""",[batch_id,collection_id,collection_id]).fetchone()[0]
            _set(database,job_id,target_count=len(rows),skipped_count=max(total-len(rows),0),message=f'Atualizando {len(rows)} ativos compatíveis')
            accepted=rejected=failed=0
            for offset in range(0,len(rows),CHUNK_SIZE):
                chunk=rows[offset:offset+CHUNK_SIZE]; symbols=[r[1] for r in chunk]
                try: body,captured_at=fetcher(symbols)
                except ValueError:
                    failed+=len(chunk);_set(database,job_id,failed_count=failed,message=f'Falha no lote iniciado em {symbols[0]}');continue
                with connect(database) as db:
                    for record_id,symbol in chunk:
                        try:
                            result=capture(db,record_id,symbol,_single_response(body,symbol),captured_at)
                            if result['status']=='accepted': accepted+=1
                            else: rejected+=1
                        except (ValueError,json.JSONDecodeError): failed+=1
                _set(database,job_id,accepted_count=accepted,rejected_count=rejected,failed_count=failed,
                     message=f'{min(offset+len(chunk),len(rows))} de {len(rows)} processados')
            status='completed' if accepted or not rows else 'failed'
            _set(database,job_id,status=status,finished_at=datetime.now(timezone.utc),accepted_count=accepted,
                 rejected_count=rejected,failed_count=failed,message=f'Concluído: {accepted} aceitos, {rejected} rejeitados, {failed} falhas')
        except Exception:
            _set(database,job_id,status='failed',finished_at=datetime.now(timezone.utc),message='Falha interna; consulte os logs do serviço')
        finally:
            ACTIVE_JOB_IDS.discard(job_id)


def create(database,batch_id,collection_id=None,runner=run):
    with START_LOCK:
        with connect(database) as db:
            active=db.execute("SELECT job_id FROM price_update_job WHERE status IN ('queued','running') ORDER BY created_at DESC LIMIT 1").fetchone()
            if active and active[0] in ACTIVE_JOB_IDS:return active[0],False
            if active:
                db.execute("UPDATE price_update_job SET status='failed',finished_at=?,message='Interrompido pela reinicialização do serviço' WHERE job_id=?",[datetime.now(timezone.utc),active[0]])
            now=datetime.now(timezone.utc);job_id=hashlib.sha256(f'{batch_id}:{collection_id}:{now.isoformat()}'.encode()).hexdigest()
            db.execute("INSERT INTO price_update_job(job_id,batch_id,collection_id,status,created_at,message) VALUES(?,?,?,'queued',?,'Aguardando início')",[job_id,batch_id,collection_id,now])
        ACTIVE_JOB_IDS.add(job_id)
        threading.Thread(target=runner,args=(database,job_id,batch_id,collection_id),daemon=True,name='fin2-price-update').start()
        return job_id,True
