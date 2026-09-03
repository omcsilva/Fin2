"""Apex Clearing monthly account-statement adapter."""
from datetime import datetime
from decimal import Decimal
import io,re
from pypdf import PdfReader
from fin2.imports.base import SourceRow
from fin2.imports.clear_brokerage import _plain
from fin2.imports.registry import register

MONEY=re.compile(r'\$?([0-9][0-9,]*\.[0-9]{2})')
def _usd(value):return Decimal(value.replace(',',''))

def _statement_metadata(text):
    period=re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4})\s*-\s*([A-Z][a-z]+ \d{1,2}, \d{4})',text)
    balance=re.search(r'Cash account\s+\$?([0-9,]+\.\d{2})\s+\$?([0-9,]+\.\d{2})',text,re.I)
    if not period or not balance:return None
    return {'period_start':str(datetime.strptime(period.group(1),'%B %d, %Y').date()),
            'period_end':str(datetime.strptime(period.group(2),'%B %d, %Y').date()),
            'currency':'USD','opening_balance':str(_usd(balance.group(1))),
            'closing_balance':str(_usd(balance.group(2)))}

def _rows_from_text(text,page=1):
    rows=[]
    for line_number,line in enumerate(text.splitlines(),1):
        line=' '.join(line.split())
        match=re.match(r'^(JOURNAL|INTEREST|BOUGHT|SOLD)\s+(\d{2}/\d{2}/\d{2})\s+([CD])\s+(.+)$',line,re.I)
        if not match:continue
        kind,raw_date,direction,detail=match.groups();kind=kind.upper()
        try:day=datetime.strptime(raw_date,'%m/%d/%y').date()
        except ValueError:continue
        amounts=[_usd(value) for value in MONEY.findall(detail)]
        if not amounts:continue
        values={'kind':kind,'direction':direction.upper(),'trade_date':day,'detail':detail,'amount':amounts[-1]}
        if kind in {'BOUGHT','SOLD'}:
            trade=re.match(r'^(.*?)\s+([0-9][0-9,]*(?:\.[0-9]+)?)\s+\$?([0-9,.]+)\s+\$?([0-9,.]+)$',detail)
            if not trade:continue
            asset,quantity,price,gross=trade.groups()
            values.update(asset=asset,quantity=Decimal(quantity.replace(',','')),
                          price=_usd(price),amount=_usd(gross))
        rows.append(SourceRow({'page':page,'line':line_number,'section':'transactions','item':len(rows)+1},values))
    return rows

class ApexStatementAdapter:
    adapter_id='apex-account-statement';version='1';document_type='account_statement'
    def detect(self,filename,body):
        if not body.startswith(b'%PDF-'):return 0
        try:text='\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(body)).pages)
        except Exception:return 0
        plain=_plain(text).replace('\ufffd','')
        return 97 if 'APEX CLEARING' in plain and 'ACCOUNT STATEMENT' in plain and 'TRANSACTION DATE' in plain else 0
    def parse(self,filename,body):
        rows=[]
        for page_number,page in enumerate(PdfReader(io.BytesIO(body)).pages,1):
            page_rows=_rows_from_text(page.extract_text() or '',page_number)
            rows.extend(SourceRow({**row.locator,'item':len(rows)+index},row.values)
                        for index,row in enumerate(page_rows,1))
        if not rows:raise ValueError('O extrato Apex foi reconhecido, mas nenhum movimento pôde ser extraído')
        return rows
    def metadata(self,filename,body):
        reader=PdfReader(io.BytesIO(body))
        for page_number,page in enumerate(reader.pages,1):
            metadata=_statement_metadata(page.extract_text() or '')
            if metadata:return {**metadata,'source_page':page_number}
        return None
    def normalize(self,source,db,options=None):
        values=source.values;errors=[];kind=values['kind']
        event_type={'JOURNAL':'deposit' if values['direction']=='C' else 'withdrawal',
                    'INTEREST':'income','BOUGHT':'buy','SOLD':'sell'}[kind]
        sign=-1 if event_type in {'withdrawal','buy'} else 1
        normalized={'row_number':source.locator['item'],'source_locator':source.locator,
          'event_type':event_type,'trade_date':str(values['trade_date']),'settlement_date':str(values['trade_date']),
          'currency':'USD','quantity':str(values['quantity']) if 'quantity' in values else None,
          'amount':str(sign*values['amount']),'description':f"Extrato Apex: {values['detail']}"}
        account=(options or {}).get('account_record')
        found=db.execute("""select a.source_record_id,a.name,a.legacy_id,upper(coalesce(c.abbreviation,''))
          from portfolio.account a left join portfolio.currency c on c.batch_id=a.batch_id and c.legacy_id=a.currency_id
          where a.source_record_id=?""",[account]).fetchone() if account else None
        if not found:errors.append('selecione a conta Apex correspondente')
        else:
            normalized.update(account_record=found[0],account=found[1])
            if found[3] not in {'USD','DOL','DOLAR'}:errors.append('a conta Apex deve usar USD')
        if kind in {'BOUGHT','SOLD'}:
            key=' '.join(_plain(values['asset']).split())
            apps=db.execute("""select ap.source_record_id,ap.name from portfolio.application ap
              left join portfolio.asset a on a.batch_id=ap.batch_id and a.legacy_id=ap.asset_id
              where ap.account_id=? and (upper(trim(ap.name))=? or upper(trim(coalesce(a.symbol,'')))=?
                or upper(trim(coalesce(a.name,'')))=?)""",[found[2] if found else -1,key,key,key]).fetchall()
            if len(apps)!=1:errors.append(f'aplicação não encontrada de forma única: {values["asset"]}')
            else:normalized.update(application_record=apps[0][0],application=apps[0][1])
        else:normalized.update(application_record=None,application='')
        normalized['errors']=errors
        return normalized

APEX_ADAPTER=register(ApexStatementAdapter())
