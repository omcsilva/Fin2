"""Official BCB/SGS benchmark ingestion with raw-response provenance."""
from datetime import date,datetime,timezone
from decimal import Decimal,InvalidOperation
import hashlib,json
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from fin2.portfolio.brapi import LIMIT

ROOT='https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados'
def fetch(code,start,end):
 endpoint=ROOT.format(code=code);query=urlencode({'formato':'json','dataInicial':start.strftime('%d/%m/%Y'),'dataFinal':end.strftime('%d/%m/%Y')})
 try:
  with urlopen(Request(endpoint+'?'+query,headers={'Accept':'application/json','User-Agent':'Fin2/0.1'}),timeout=30) as r:
   body=r.read(LIMIT+1)
   if len(body)>LIMIT: raise ValueError('Resposta SGS excede 1 MiB')
   return endpoint,body,datetime.now(timezone.utc)
 except HTTPError as e: code=e.code;e.close();raise ValueError(f'BCB SGS HTTP {code}') from None
 except (URLError,TimeoutError): raise ValueError('Falha de conexão com BCB SGS') from None
def parse(body,start,end):
 try:
  rows=json.loads(body);out=[]
  for row in rows:
   day=datetime.strptime(row['data'],'%d/%m/%Y').date();value=Decimal(str(row['valor']).replace(',','.'))
   if day<start or day>end or not value.is_finite(): raise ValueError
   out.append((day,value))
  return out
 except (ValueError,KeyError,TypeError,InvalidOperation): raise ValueError('Resposta BCB SGS incompatível') from None
def capture(connection,catalog,endpoint,body,captured_at,start,end):
 record,abbrev,code,unit,frequency=catalog;points=parse(body,start,end);digest=hashlib.sha256(body).hexdigest();cid=hashlib.sha256(f'bcb_sgs:{code}:{digest}'.encode()).hexdigest()
 connection.execute('BEGIN')
 try:
  connection.execute('insert into market.benchmark_capture values (?,?,?,?,?,?,?) on conflict do nothing',[cid,'bcb_sgs',endpoint,str(code),captured_at,digest,body])
  for day,value in points:
   connection.execute("""insert into market.benchmark_value values (?,?,'bcb_sgs',?,?,?,?,?,?)
    on conflict(benchmark_source_record_id,observation_date,provider) do update set value=excluded.value,capture_id=excluded.capture_id,captured_at=excluded.captured_at
    where excluded.captured_at>market.benchmark_value.captured_at""",[record,day,str(code),frequency,value,unit,cid,captured_at])
  connection.execute('COMMIT');return len(points)
 except Exception: connection.execute('ROLLBACK');raise
