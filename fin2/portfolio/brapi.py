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

from warehouse.database import connect, migrate
from config.environment import load_dotenv

ENDPOINT = 'https://brapi.dev/api/v2/stocks/quote'
LIMIT = 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a bearer token to another endpoint.


def validate_mapping(connection, record_id, symbol):
    if not re.fullmatch(r'[A-Z]{4}[0-9]{1,2}', symbol):
        raise ValueError('Ticker fora do formato suportado')
    row = connection.execute('SELECT batch_id,symbol,currency,configured_provider,configured_multiplier FROM market.asset_catalog WHERE source_record_id=?', [record_id]).fetchone()
    if not row or row[1] != symbol or row[2] not in ('REAL','BRL') or row[3] != 'atuBrAPI':
        raise ValueError('Ativo, ticker, moeda ou provedor incompatível com o cadastro legado')
    try:
        unit = Decimal(row[4])
    except (InvalidOperation, TypeError):
        raise ValueError('Multiplicador ausente ou inválido') from None
    if unit != 1:
        raise ValueError('Somente multiplicador 1 é suportado')
    count = connection.execute('SELECT count(*) FROM market.asset_catalog WHERE batch_id=? AND upper(trim(symbol))=?', [row[0],symbol]).fetchone()[0]
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
            body,captured_at = fetch(args.symbol)
            result = capture(c,args.record,args.symbol,body,captured_at)
            print(json.dumps(result))
            if result['status']=='rejected':
                raise SystemExit(2)
    except (ValueError, OSError) as error:
        parser.exit(1,str(error)+'\n')


if __name__ == '__main__':
    main()
