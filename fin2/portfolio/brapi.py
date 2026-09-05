"""Explicit, offline, one-asset brapi v2 capture; never updates legacy prices."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlencode

from warehouse.database import connect, migrate
from config.environment import load_dotenv

ENDPOINT = 'https://brapi.dev/api/v2/stocks/quote'
HISTORICAL_ENDPOINT = 'https://brapi.dev/api/v2/stocks/historical'
LIMIT = 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a bearer token to another endpoint.


def validate_mapping(connection, record_id, symbol):
    if not re.fullmatch(r'[A-Z]{4}[0-9]{1,2}', symbol):
        raise ValueError('Ticker fora do formato suportado')
    row = connection.execute('SELECT batch_id,symbol,currency,configured_provider,configured_multiplier FROM market.asset_catalog_effective WHERE source_record_id=?', [record_id]).fetchone()
    if not row or row[1] != symbol or row[2] not in ('REAL','BRL'):
        raise ValueError('Ativo, ticker ou moeda incompatível com a brapi')
    try:
        unit = Decimal(row[4])
    except (InvalidOperation, TypeError):
        raise ValueError('Multiplicador ausente ou inválido') from None
    if unit != 1:
        raise ValueError('Somente multiplicador 1 é suportado')
    count = connection.execute('SELECT count(*) FROM market.asset_catalog_effective WHERE batch_id=? AND upper(trim(symbol))=?', [row[0],symbol]).fetchone()[0]
    if count != 1:
        raise ValueError('Ticker ambíguo no lote')


def parse_quote(body, symbol, captured_at):
    try:
        payload = json.loads(body, parse_float=Decimal)
        results = payload['results']
        if not isinstance(results,list) or len(results) != 1:
            raise ValueError
        item = results[0]
        if item['requestedSymbol'] != symbol or item['symbol'] != symbol or item['changed'] is not False:
            raise ValueError
        data = item['data']
        if data['currency'] != 'BRL' or isinstance(data['regularMarketPrice'], bool):
            raise ValueError
        price = Decimal(str(data['regularMarketPrice']))
        if not price.is_finite() or price <= 0 or price >= Decimal('1e18'):
            raise ValueError
        if price != price.quantize(Decimal('0.0000000001')):
            raise ValueError
        quoted_at = datetime.fromisoformat(data['regularMarketTime'].replace('Z','+00:00'))
        if quoted_at.tzinfo is None or quoted_at > captured_at:
            raise ValueError
        return price, 'BRL', quoted_at
    except (ValueError, KeyError, TypeError, AttributeError, InvalidOperation, OverflowError):
        raise ValueError('Resposta incompatível: confira ticker, renome, moeda, preço e data na evidência original') from None


def fetch(symbol):
    load_dotenv()
    headers = {'Accept':'application/json','User-Agent':'Fin2/0.1'}
    token = os.environ.get('BRAPI_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer '+token
    try:
        with build_opener(NoRedirect()).open(Request(ENDPOINT+'?symbols='+symbol,headers=headers),timeout=20) as response:
            body = response.read(LIMIT+1)
            if len(body)>LIMIT:
                raise ValueError('Resposta excede 1 MiB; nada importado')
            return body, datetime.now(timezone.utc)
    except HTTPError as error:
        error.close()
        raise ValueError(f'brapi HTTP {error.code}; nada importado') from None
    except (URLError, TimeoutError):
        raise ValueError('Falha de conexão com brapi; nada importado') from None


def fetch_latest_close(symbol):
    """Fetch one ticker's recent daily history from the free-plan endpoint."""
    load_dotenv()
    headers = {'Accept':'application/json','User-Agent':'Fin2/0.1'}
    token = os.environ.get('BRAPI_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer '+token
    query = urlencode({'symbols':symbol,'interval':'1d','range':'3mo','sortOrder':'desc'})
    try:
        with build_opener(NoRedirect()).open(Request(HISTORICAL_ENDPOINT+'?'+query,headers=headers),timeout=5) as response:
            body = response.read(LIMIT+1)
            if len(body)>LIMIT:
                raise ValueError('Resposta excede 1 MiB; nada importado')
            return body, datetime.now(timezone.utc)
    except HTTPError as error:
        code=error.code;error.close()
        raise ValueError(f'brapi histórico HTTP {code}; nada importado') from None
    except (URLError, TimeoutError):
        raise ValueError('Falha de conexão com histórico brapi; nada importado') from None


def parse_recent_closes(body,symbol,captured_at):
    try:
        payload=json.loads(body,parse_float=Decimal)
        results=payload['results']
        if not isinstance(results,list) or len(results)!=1:
            raise ValueError
        item=results[0]
        if item['requestedSymbol']!=symbol or item['symbol']!=symbol or item['changed'] is not False:
            raise ValueError
        data=item['data']
        if data['usedInterval']!='1d':
            raise ValueError
        points=data['historicalDataPrice']
        if not isinstance(points,list) or not points:
            raise ValueError
        parsed=[]
        for point in points:
            quoted_at=datetime.fromtimestamp(int(point['date']),timezone.utc)
            close=Decimal(str(point['close']))
            adjusted=Decimal(str(point['adjustedClose'])) if point.get('adjustedClose') is not None else None
            values=(close,) if adjusted is None else (close,adjusted)
            if quoted_at>captured_at or any(not value.is_finite() or value<=0 or value>=Decimal('1e18') for value in values):
                raise ValueError
            if any(value!=value.quantize(Decimal('0.0000000001')) for value in values):
                raise ValueError
            parsed.append((quoted_at,close,adjusted))
        return parsed
    except (ValueError,KeyError,TypeError,InvalidOperation,OverflowError,OSError):
        raise ValueError('Histórico incompatível: confira ticker, fechamento e data na evidência original') from None


def parse_latest_close(body,symbol,captured_at):
    quoted_at,price,_=max(parse_recent_closes(body,symbol,captured_at),key=lambda point:point[0])
    return price,'BRL',quoted_at


def capture(connection, record_id, symbol, body, captured_at):
    validate_mapping(connection, record_id, symbol)
    if len(body)>LIMIT or captured_at.tzinfo is None:
        raise ValueError('Captura inválida')
    digest = hashlib.sha256(body).hexdigest()
    capture_id = hashlib.sha256(f'{record_id}:brapi_v2:{symbol}:{digest}'.encode()).hexdigest()
    existing = connection.execute('SELECT status FROM market.quote_capture WHERE capture_id=?',[capture_id]).fetchone()
    if existing:
        return {'capture_id':capture_id,'status':existing[0],'reused':True}
    reason = None
    try:
        price,currency,quoted_at = parse_quote(body,symbol,captured_at)
        status = 'accepted'
    except ValueError as error:
        reason = str(error)
        price = currency = quoted_at = None
        status = 'rejected'
    # One INSERT atomically preserves the exact bytes and interpretation.
    connection.execute('INSERT INTO external_quote_capture VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
        [capture_id,record_id,'brapi_v2',symbol,ENDPOINT,captured_at,digest,body,status,reason,price,currency,quoted_at])
    return {'capture_id':capture_id,'status':status,'reused':False}


def capture_latest_close(connection,record_id,symbol,body,captured_at):
    validate_mapping(connection,record_id,symbol)
    if len(body)>LIMIT or captured_at.tzinfo is None:
        raise ValueError('Captura inválida')
    digest=hashlib.sha256(body).hexdigest()
    capture_id=hashlib.sha256(f'{record_id}:brapi_v2:latest_close:{symbol}:{digest}'.encode()).hexdigest()
    existing=connection.execute('SELECT status,price,quoted_at,captured_at FROM market.quote_capture WHERE capture_id=?',[capture_id]).fetchone()
    reason=None
    if existing:
        status,price,quoted_at,_=existing;currency='BRL' if status=='accepted' else None
        points=parse_recent_closes(body,symbol,captured_at) if status=='accepted' else []
    else:
        try:
            points=parse_recent_closes(body,symbol,captured_at)
            quoted_at,price,_=max(points,key=lambda point:point[0]);currency='BRL';status='accepted'
        except ValueError as error:
            reason=str(error);points=[];price=currency=quoted_at=None;status='rejected'
        connection.execute('INSERT INTO external_quote_capture VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
            [capture_id,record_id,'brapi_v2',symbol,HISTORICAL_ENDPOINT,captured_at,digest,body,status,reason,price,currency,quoted_at])
    points_added=0
    if status=='accepted':
        connection.execute('INSERT INTO market.asset_price_query_success VALUES (?,?,?,?,?,?,?)',
            [record_id,'brapi_v2',captured_at,quoted_at,price,currency,capture_id])
        history_id=hashlib.sha256(f'brapi_v2:history:{digest}'.encode()).hexdigest()
        connection.execute('INSERT INTO market.history_capture VALUES (?,?,?,?,?,?,?) ON CONFLICT DO NOTHING',
            [history_id,'brapi_v2',HISTORICAL_ENDPOINT,symbol,captured_at,digest,body])
        for point_at,close,adjusted in points:
            inserted=connection.execute("""INSERT INTO market.daily_close VALUES (?,?, 'brapi_v2','BRL',?,?,?,?)
              ON CONFLICT DO NOTHING RETURNING trading_date""",
              [record_id,point_at.date(),close,adjusted,history_id,captured_at]).fetchone()
            points_added+=int(inserted is not None)
    return {'capture_id':capture_id,'status':status,'price':price,'quoted_at':quoted_at,
            'captured_at':captured_at,'reused':existing is not None,'points_added':points_added}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--record',required=True)
    parser.add_argument('--symbol',required=True)
    parser.add_argument('--fetch',action='store_true',help='Explicitly request and save one quote; stop the web server first')
    args = parser.parse_args()
    try:
        database = args.database.resolve(strict=True)
        if not args.fetch:
            import duckdb
            with duckdb.connect(str(database),read_only=True) as c:
                validate_mapping(c,args.record,args.symbol)
            print('Mapeamento legado compatível. Nenhuma consulta ou escrita executada.')
            return
        with connect(database) as c:
            migrate(c)
            validate_mapping(c,args.record,args.symbol)
            body,captured_at = fetch_latest_close(args.symbol)
            result = capture_latest_close(c,args.record,args.symbol,body,captured_at)
            print(json.dumps(result))
            if result['status']=='rejected':
                raise SystemExit(2)
    except (ValueError, OSError) as error:
        parser.exit(1,str(error)+'\n')


if __name__ == '__main__':
    main()
