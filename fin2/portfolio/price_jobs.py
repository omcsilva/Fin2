"""Single-process background quote jobs with durable progress."""
from datetime import datetime, timezone
import hashlib
import threading
import time
from zoneinfo import ZoneInfo

from fin2.portfolio.brapi import fetch_latest_close, capture_latest_close, validate_mapping
from warehouse.database import connect

JOB_LOCK = threading.Lock()
START_LOCK = threading.Lock()
ACTIVE_JOB_IDS = set()
CANCELLED_JOB_IDS = set()
LOCAL_ZONE=ZoneInfo('America/Sao_Paulo')
QUERY_INTERVAL_SECONDS=1


def _money(value):
    rendered=f'{value:,.2f}'.replace(',','X').replace('.',',').replace('X','.')
    return 'R$ '+rendered


def _set(database,job_id,**values):
    columns=','.join(f'{key}=?' for key in values)
    with connect(database) as db:
        db.execute(f'UPDATE price_update_job SET {columns} WHERE job_id=?',[*values.values(),job_id])


def _asset_set(database,job_id,record_id,**values):
    columns=','.join(f'{key}=?' for key in values)
    with connect(database) as db:
        db.execute(f'UPDATE market.price_update_job_asset SET {columns} WHERE job_id=? AND source_record_id=?',
                   [*values.values(),job_id,record_id])


def run(database,job_id,batch_id,collection_id=None,fetcher=fetch_latest_close,sleeper=time.sleep,today=None):
    ACTIVE_JOB_IDS.add(job_id)
    with JOB_LOCK:
        try:
            if job_id in CANCELLED_JOB_IDS:return
            today=today or datetime.now(LOCAL_ZONE).date()
            _set(database,job_id,status='running',started_at=datetime.now(timezone.utc),message='Selecionando ativos compatíveis')
            with connect(database) as db:
                rows=db.execute("""SELECT a.source_record_id,a.symbol,a.name,
                    EXISTS(SELECT 1 FROM market.asset_price_query_success c WHERE c.source_record_id=a.source_record_id
                      AND CAST(c.queried_at AT TIME ZONE 'America/Sao_Paulo' AS DATE)=?) current_today
                  FROM market.asset_catalog_effective a
                  JOIN market.asset_price_update_method u USING(source_record_id)
                  WHERE a.batch_id=? AND u.method='BRAPI'
                    AND (? IS NULL OR EXISTS(SELECT 1 FROM portfolio.application ap JOIN portfolio.membership pm
                      ON pm.batch_id=ap.batch_id AND pm.application_id=ap.legacy_id
                      WHERE ap.batch_id=a.batch_id AND ap.asset_id=a.legacy_id AND pm.collection_id=?))
                  ORDER BY coalesce(a.symbol,a.name),a.legacy_id""",[today,batch_id,collection_id,collection_id]).fetchall()
                total=db.execute("""SELECT count(*) FROM market.asset_catalog_effective a WHERE a.batch_id=? AND (? IS NULL OR EXISTS(
                  SELECT 1 FROM portfolio.application ap JOIN portfolio.membership pm ON pm.batch_id=ap.batch_id AND pm.application_id=ap.legacy_id
                  WHERE ap.batch_id=a.batch_id AND ap.asset_id=a.legacy_id AND pm.collection_id=?))""",[batch_id,collection_id,collection_id]).fetchone()[0]
                if rows:
                    db.executemany("""INSERT INTO market.price_update_job_asset
                      (job_id,source_record_id,asset_name,symbol,method,status) VALUES (?,?,?,?, 'BRAPI','pending')""",
                      [(job_id,record,symbol,name) for record,symbol,name,current in rows])
            pending_count=sum(not current_today for _,_,_,current_today in rows)
            selection_message=(f'Atualizando {pending_count} ativos configurados para BRAPI' if pending_count
                               else 'Todos ativos possuem cotações atualizadas na data de hoje')
            _set(database,job_id,target_count=len(rows),skipped_count=max(total-len(rows),0),message=selection_message)
            accepted=rejected=failed=disabled=0;last_success=None;failures=[];queries=0
            for record_id,symbol,name,current_today in rows:
                label=f'{name} ({symbol})' if name and symbol and name!=symbol else (symbol or name or record_id[:8])
                if current_today:
                    accepted+=1
                    _asset_set(database,job_id,record_id,status='already_current',message='Consulta bem-sucedida já realizada hoje')
                    _set(database,job_id,accepted_count=accepted)
                    continue
                try:
                    with connect(database) as db: validate_mapping(db,record_id,symbol or '')
                except ValueError as error:
                    if str(error)=='Ticker fora do formato suportado':
                        disabled+=1
                        set_update_method(database,batch_id,record_id,'NENHUM')
                        _asset_set(database,job_id,record_id,method='NENHUM',status='disabled',
                                   message='Mecanismo alterado automaticamente para NENHUM')
                        _set(database,job_id,skipped_count=max(total-len(rows),0)+disabled,
                             message=f'{label}: mecanismo alterado para NENHUM')
                        continue
                    failed+=1;failures.append(label)
                    _asset_set(database,job_id,record_id,status='failed',message=str(error))
                    _set(database,job_id,failed_count=failed,message=f'{label}: {error}')
                    continue
                if queries:
                    sleeper(QUERY_INTERVAL_SECONDS)
                queries+=1
                if job_id in CANCELLED_JOB_IDS:return
                try: body,captured_at=fetcher(symbol)
                except ValueError as error:
                    if job_id in CANCELLED_JOB_IDS:return
                    failed+=1;detail=str(error)
                    message=f'{symbol}: {detail}'
                    if any(f'HTTP {code}' in detail for code in (401,403,429)):
                        failures.append(label)
                        _asset_set(database,job_id,record_id,status='failed',message=detail,queried_at=datetime.now(timezone.utc))
                        _set(database,job_id,status='failed',finished_at=datetime.now(timezone.utc),
                             failed_count=failed,message='Falharam: '+', '.join(failures)+' · atualização interrompida')
                        return
                    failures.append(label)
                    _asset_set(database,job_id,record_id,status='failed',message=detail,queried_at=datetime.now(timezone.utc))
                    _set(database,job_id,failed_count=failed,message=message);continue
                with connect(database) as db:
                    try: result=capture_latest_close(db,record_id,symbol,body,captured_at)
                    except ValueError:
                        if job_id in CANCELLED_JOB_IDS:return
                        failed+=1;failures.append(label)
                        _asset_set(database,job_id,record_id,status='failed',message='Resposta inválida',queried_at=captured_at)
                        _set(database,job_id,failed_count=failed,message=f'{symbol}: resposta inválida');continue
                if result['status']=='accepted':
                    accepted+=1
                    day=result['quoted_at'].astimezone(LOCAL_ZONE).strftime('%d/%m/%Y')
                    last_success=f"{label}: {_money(result['price'])} — fechamento de {day}"
                    if result['points_added']:
                        last_success+=f" · {result['points_added']} fechamento(s) preenchido(s)"
                    message=last_success
                else:
                    rejected+=1;failures.append(label);message=f'{symbol}: cotação rejeitada'
                _asset_set(database,job_id,record_id,status='accepted' if result['status']=='accepted' else 'rejected',
                           message=message,queried_at=captured_at)
                _set(database,job_id,accepted_count=accepted,rejected_count=rejected,failed_count=failed,message=message)
                if job_id in CANCELLED_JOB_IDS:return
            all_ok=bool(rows) and accepted+disabled==len(rows) and not rejected and not failed
            status='completed' if all_ok or not rows else 'failed'
            if all_ok:
                finished=datetime.now(timezone.utc)
                with connect(database) as db:
                    db.execute("UPDATE market.price_update_state SET last_successful_at=?,job_id=? WHERE state_key='assets'",[finished,job_id])
                if pending_count==0:
                    summary='Todos ativos possuem cotações atualizadas na data de hoje'
                else:
                    summary=(last_success+' · ' if last_success else '')+f'Concluído: {pending_count-disabled} ativos atualizados'
                    if disabled:summary+=f', {disabled} alterados para NENHUM'
            elif failures:
                summary='Falharam: '+', '.join(failures)
            else: summary='Nenhum ativo configurado para atualização BRAPI'
            _set(database,job_id,status=status,finished_at=datetime.now(timezone.utc),accepted_count=accepted,
                 rejected_count=rejected,failed_count=failed,message=summary)
        except Exception:
            if job_id not in CANCELLED_JOB_IDS:
                _set(database,job_id,status='failed',finished_at=datetime.now(timezone.utc),message='Falha interna; consulte os logs do serviço')
        finally:
            ACTIVE_JOB_IDS.discard(job_id)
            CANCELLED_JOB_IDS.discard(job_id)


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


def recover_interrupted(database,job_id):
    """Fail an active-looking job that has no worker in this server process."""
    if job_id in ACTIVE_JOB_IDS:
        return False
    with START_LOCK:
        if job_id in ACTIVE_JOB_IDS:
            return False
        with connect(database) as db:
            row=db.execute('SELECT status FROM price_update_job WHERE job_id=?',[job_id]).fetchone()
            if not row or row[0] not in ('queued','running'):
                return False
            db.execute("""UPDATE price_update_job SET status='failed',finished_at=?,
              message='Atualização interrompida pela reinicialização do serviço' WHERE job_id=?""",
              [datetime.now(timezone.utc),job_id])
            return True


def cancel(database):
    """Persist cancellation and signal the active worker without confirmation."""
    with START_LOCK:
        with connect(database) as db:
            row=db.execute("SELECT job_id FROM price_update_job WHERE status IN ('queued','running') ORDER BY created_at DESC LIMIT 1").fetchone()
            if not row:
                return None,False
            job_id=row[0]
            CANCELLED_JOB_IDS.add(job_id)
            db.execute("""UPDATE price_update_job SET status='cancelled',finished_at=?,
              message='Atualização de preços cancelada' WHERE job_id=?""",
              [datetime.now(timezone.utc),job_id])
            return job_id,True


def set_update_method(database,batch_id,record_id,method):
    if method not in ('BRAPI','NENHUM'):
        raise ValueError('Mecanismo de atualização inválido')
    with connect(database) as db:
        row=db.execute('SELECT 1 FROM market.asset_catalog_effective WHERE batch_id=? AND source_record_id=?',
                       [batch_id,record_id]).fetchone()
        if not row:raise ValueError('Ativo não encontrado')
        db.execute("""INSERT INTO market.asset_price_update_method VALUES (?,?,now())
          ON CONFLICT(source_record_id) DO UPDATE SET method=excluded.method,updated_at=excluded.updated_at""",
          [record_id,method])
