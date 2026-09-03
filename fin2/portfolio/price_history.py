"""Audited brapi daily closing-price history ingestion."""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError

from fin2.portfolio.brapi import LIMIT, NoRedirect, validate_mapping
from config.environment import load_dotenv

ENDPOINT='https://brapi.dev/api/v2/stocks/historical'


def parse(body, expected_symbols):
    try:
        payload=json.loads(body,parse_float=Decimal)
        results=payload['results']
        if not isinstance(results,list): raise ValueError
        found={}
        for item in results:
            symbol=item['requestedSymbol']
            if symbol not in expected_symbols or item['symbol']!=symbol or item['changed'] is not False: raise ValueError
            data=item['data']
            if data['usedInterval']!='1d': raise ValueError
            points=[]
            for point in data['historicalDataPrice']:
                day=datetime.fromtimestamp(int(point['date']),timezone.utc).date()
                close=Decimal(str(point['close']))
                adjusted=Decimal(str(point['adjustedClose'])) if point.get('adjustedClose') is not None else None
                if not close.is_finite() or close<=0 or (adjusted is not None and (not adjusted.is_finite() or adjusted<=0)): raise ValueError
                points.append((day,close,adjusted))
            found[symbol]=points
        if set(found)!=set(expected_symbols): raise ValueError
        return found
    except (KeyError,TypeError,ValueError,InvalidOperation,OverflowError,OSError):
        raise ValueError('Histórico diário incompatível; nada importado') from None


def fetch(symbols, range_name=None, start_date=None, end_date=None):
    load_dotenv()
    params={'symbols':','.join(symbols),'interval':'1d','sortOrder':'asc'}
    if start_date:
        params['startDate']=str(start_date)
        params['endDate']=str(end_date or date.today())
    else: params['range']=range_name or '1mo'
    query=urlencode(params)
    headers={'Accept':'application/json','User-Agent':'Fin2/0.1'}
    token=os.environ.get('BRAPI_TOKEN')
    if token: headers['Authorization']='Bearer '+token
    try:
        with build_opener(NoRedirect()).open(Request(ENDPOINT+'?'+query,headers=headers),timeout=30) as response:
            body=response.read(LIMIT+1)
            if len(body)>LIMIT: raise ValueError('Histórico excede 1 MiB; nada importado')
            return body,datetime.now(timezone.utc)
    except HTTPError as error:
        code=error.code;error.close();raise ValueError(f'brapi histórico HTTP {code}; nada importado') from None
    except (URLError,TimeoutError): raise ValueError('Falha de conexão com histórico brapi; nada importado') from None


def capture(connection, records, body, captured_at):
    if captured_at.tzinfo is None or len(body)>LIMIT: raise ValueError('Captura histórica inválida')
    symbols=[symbol for _,symbol in records]
    for record,symbol in records: validate_mapping(connection,record,symbol)
    points=parse(body,set(symbols)); digest=hashlib.sha256(body).hexdigest()
    capture_id=hashlib.sha256(f"brapi_v2:history:{digest}".encode()).hexdigest()
    connection.execute('BEGIN')
    try:
        connection.execute('insert into market.history_capture values (?,?,?,?,?,?,?) on conflict do nothing',
          [capture_id,'brapi_v2',ENDPOINT,','.join(symbols),captured_at,digest,body])
        count=0
        for record,symbol in records:
            for day,close,adjusted in points[symbol]:
                connection.execute("""insert into market.daily_close values (?,?, 'brapi_v2','BRL',?,?,?,?)
                  on conflict(source_record_id,trading_date,provider) do update set
                  close=excluded.close,adjusted_close=excluded.adjusted_close,
                  capture_id=excluded.capture_id,captured_at=excluded.captured_at
                  where excluded.captured_at>market.daily_close.captured_at""",
                  [record,day,close,adjusted,capture_id,captured_at]);count+=1
        connection.execute('COMMIT')
    except Exception:
        connection.execute('ROLLBACK');raise
    return {'capture_id':capture_id,'points':count}
