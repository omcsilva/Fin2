"""Official B3 Ibovespa daily-history download and audited ingestion."""
import base64,csv,hashlib,json
from datetime import date,datetime,timezone
from decimal import Decimal,InvalidOperation
from io import StringIO
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen

ROOT='https://sistemaswebb3-listados.b3.com.br/indexStatisticsProxy/IndexCall/GetDownloadPortfolioDay/'
LIMIT=2*1024*1024
MONTHS=('Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez')


def fetch(year):
    payload={'index':'IBOVESPA','language':'pt-br','year':str(year)}
    encoded=base64.b64encode(json.dumps(payload,separators=(',',':')).encode()).decode()
    endpoint=ROOT+encoded
    try:
        with urlopen(Request(endpoint,headers={'Accept':'text/plain','User-Agent':'Fin2/0.1'}),timeout=30) as response:
            body=response.read(LIMIT+1)
            if len(body)>LIMIT:raise ValueError('Arquivo anual do Ibovespa excede 2 MiB')
            return endpoint,body,datetime.now(timezone.utc)
    except HTTPError as error:
        code=error.code;error.close();raise ValueError(f'B3 Ibovespa HTTP {code}') from None
    except (URLError,TimeoutError):raise ValueError('Falha de conexão com a série do Ibovespa') from None


def parse(body,year):
    try:
        decoded=base64.b64decode(body,validate=True).decode('cp1252')
        rows=list(csv.reader(StringIO(decoded),delimiter=';'))
        if len(rows)<3 or rows[0]!=[f'IBOVESPA - {year}'] or rows[1][:13]!=['Dia',*MONTHS]:raise ValueError
        points=[]
        for row in rows[2:]:
            if not row or not row[0].strip():continue
            if not row[0].strip().isdigit():continue  # B3 appends annual summary rows.
            day=int(row[0])
            for month,text in enumerate(row[1:13],1):
                text=text.strip()
                if not text:continue
                value=Decimal(text.replace('.','').replace(',','.'))
                when=date(year,month,day)
                if value<=0 or not value.is_finite():raise ValueError
                points.append((when,value))
        if not points:raise ValueError
        return sorted(points)
    except (ValueError,TypeError,UnicodeDecodeError,InvalidOperation,IndexError):
        raise ValueError('Arquivo anual do Ibovespa incompatível; nada importado') from None


def capture(connection,catalog,endpoint,body,captured_at,year):
    record,abbreviation=catalog
    if abbreviation!='IBO' or captured_at.tzinfo is None:raise ValueError('Catálogo Ibovespa incompatível')
    points=parse(body,year);digest=hashlib.sha256(body).hexdigest()
    capture_id=hashlib.sha256(f'b3_index:IBOV:{year}:{digest}'.encode()).hexdigest()
    connection.execute('BEGIN')
    try:
        connection.execute("""INSERT INTO market.benchmark_capture VALUES
          (?,'b3_index',?,'IBOV',?,?,?) ON CONFLICT DO NOTHING""",
          [capture_id,endpoint,captured_at,digest,body])
        connection.executemany("""INSERT INTO market.benchmark_value VALUES
          (?,?,'b3_index','IBOV','daily',?,'index_points',?,?)
          ON CONFLICT(benchmark_source_record_id,observation_date,provider) DO UPDATE SET
          value=excluded.value,capture_id=excluded.capture_id,captured_at=excluded.captured_at
          WHERE excluded.captured_at>market.benchmark_value.captured_at""",
          [(record,day,value,capture_id,captured_at) for day,value in points])
        connection.execute('COMMIT');return len(points)
    except Exception:connection.execute('ROLLBACK');raise
