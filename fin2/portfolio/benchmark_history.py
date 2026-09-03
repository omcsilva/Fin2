"""Audited benchmark history from brapi, always starting 2000-01-01."""
from datetime import date,datetime,timezone
from decimal import Decimal,InvalidOperation
import hashlib,json,os
from urllib.parse import urlencode
from urllib.request import Request,build_opener
from urllib.error import HTTPError,URLError
from fin2.portfolio.brapi import LIMIT,NoRedirect
from config.environment import load_dotenv

ENDPOINTS={'macro':'https://brapi.dev/api/v2/macro','currency':'https://brapi.dev/api/v2/currency/historical','stocks':'https://brapi.dev/api/v2/stocks/historical'}

def fetch(family,symbols,start=date(2000,1,1)):
 load_dotenv()
 params={'startDate':str(start),'sortOrder':'asc'}
 if family=='macro': params.update(symbols=','.join(symbols),limit=10000)
 elif family=='currency': params.update(currency=','.join(symbols),limit=10000)
 else: params.update(symbols=','.join(symbols),interval='1d')
 headers={'Accept':'application/json','User-Agent':'Fin2/0.1'};token=os.environ.get('BRAPI_TOKEN')
 if token: headers['Authorization']='Bearer '+token
 try:
  with build_opener(NoRedirect()).open(Request(ENDPOINTS[family]+'?'+urlencode(params),headers=headers),timeout=30) as r:
   body=r.read(LIMIT+1)
   if len(body)>LIMIT: raise ValueError('Resposta de índice excede 1 MiB')
   return body,datetime.now(timezone.utc)
 except HTTPError as e: code=e.code;e.close();raise ValueError(f'brapi índice HTTP {code}') from None
 except (URLError,TimeoutError): raise ValueError('Falha de conexão com índices brapi') from None

def parse(body,family,expected):
 try:
  results=json.loads(body,parse_float=Decimal)['results'];out={}
  for item in results:
   if family=='macro':
    meta=item['series'];symbol=meta['slug'];freq=meta['frequency'];unit=meta['unit'];raw=item['observations']
   elif family=='currency': symbol=item['pair'];freq='daily';unit='BRL_per_unit';raw=item['observations']
   else:
    symbol=item['requestedSymbol'];freq='daily';unit='index_points';raw=item['data']['historicalDataPrice']
    if item['symbol']!=symbol or item['changed'] is not False or item['data']['usedInterval']!='1d': raise ValueError
   points=[]
   for p in raw:
    day=datetime.fromtimestamp(int(p['date']),timezone.utc).date() if family=='stocks' else date.fromisoformat(p['date'])
    value=Decimal(str(p['close'] if family=='stocks' else p['value']))
    if day<date(2000,1,1) or not value.is_finite(): raise ValueError
    points.append((day,value,freq,unit))
   out[symbol]=points
  if set(out)!=set(expected): raise ValueError
  return out
 except (KeyError,TypeError,ValueError,InvalidOperation,OverflowError,OSError): raise ValueError('Série de índice incompatível') from None

def capture(connection,catalog,body,captured_at):
 family=catalog[0][2];symbols=[r[3] for r in catalog];points=parse(body,family,set(symbols))
 digest=hashlib.sha256(body).hexdigest();cid=hashlib.sha256(f'brapi_v2:{family}:{digest}'.encode()).hexdigest()
 connection.execute('BEGIN')
 try:
  connection.execute('insert into market.benchmark_capture values (?,?,?,?,?,?,?) on conflict do nothing',[cid,'brapi_v2',ENDPOINTS[family],','.join(symbols),captured_at,digest,body])
  count=0
  for record,_,_,symbol in catalog:
   for day,value,freq,unit in points[symbol]:
    connection.execute("""insert into market.benchmark_value values (?,?,'brapi_v2',?,?,?,?,?,?)
     on conflict(benchmark_source_record_id,observation_date,provider) do update set
     value=excluded.value,unit=excluded.unit,frequency=excluded.frequency,capture_id=excluded.capture_id,captured_at=excluded.captured_at
     where excluded.captured_at>market.benchmark_value.captured_at""",[record,day,symbol,freq,value,unit,cid,captured_at]);count+=1
  connection.execute('COMMIT');return count
 except Exception: connection.execute('ROLLBACK');raise
