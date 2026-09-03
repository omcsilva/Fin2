"""Banco do Brasil Tesouro Direto receipt adapter."""
from datetime import datetime
from decimal import Decimal,InvalidOperation
import re
from fin2.imports.base import SourceRow
from fin2.imports import ocr
from fin2.imports.clear_brokerage import _plain
from fin2.imports.registry import register

def _number(value):return Decimal(value.replace('.','').replace(',','.'))

def _rows_from_text(text):
    date_match=re.search(r'Data da opera(?:ç|c)[aã]o\s+(\d{2}/\d{2}/\d{4})',text,re.I)
    day=datetime.strptime(date_match.group(1),'%d/%m/%Y').date() if date_match else None
    protocol=(re.search(r'(?:N[ºo°]\s*de\s*)?protocolo\s*[-:]\s*(\d+)',text,re.I) or [None,None])[1]
    starts=list(re.finditer(r'(?im)^\s*((?:Tesouro\s+(?:Selic|IPCA\+?(?:\s+com\s+Juros\s+Semestrais)?|Prefixado)|(?:NTN[ -]?B|LTN|LFT)\s+\d)[^\r\n]*)',text))
    rows=[]
    for index,start in enumerate(starts):
        block=text[start.start():(starts[index+1].start() if index+1<len(starts) else len(text))]
        def capture(pattern):
            match=re.search(pattern,block,re.I|re.S);return match.group(1).strip() if match else None
        quantity=capture(r'Quantidade de t[ií]tulos\s+([\d.,]+)')
        unit=capture(r'Valor unit[aá]rio\s+R?\$?\s*([\d.,]+)')
        gross=capture(r'Valor bruto\s+R?\$?\s*([\d.,]+)')
        yield_text=capture(r'Rentabilidade\s+([\d.,]+\s*%)')
        if not quantity or not gross:
            raise ValueError('OCR incompleto: quantidade ou valor bruto ilegível em um dos produtos')
        try:quantity_value=_number(quantity);gross_value=_number(gross);unit_value=_number(unit) if unit else None
        except InvalidOperation:raise ValueError('OCR produziu um valor numérico inválido') from None
        title=' '.join(start.group(1).split())
        maturity=re.search(r'(20\d{2})',title)
        rows.append(SourceRow({'page':1,'section':'investimentos','item':len(rows)+1},
          {'title':title,'quantity':quantity_value,'unit_price':unit_value,'amount':gross_value,
           'yield_text':yield_text,'maturity_year':int(maturity.group(1)) if maturity else None,
           'trade_date':day,'protocol':protocol}))
    return rows

class BBFixedIncomeAdapter:
    adapter_id='bb-tesouro-receipt';version='1';document_type='investment_receipt'
    def detect(self,filename,body):
        if not (body.startswith(b'\x89PNG\r\n\x1a\n') or body.startswith(b'\xff\xd8\xff')) or not ocr.available():return 0
        plain=_plain(ocr.extract(body)).replace('\ufffd','')
        return 96 if 'BB BANCO DE INVESTIMENTO' in plain and 'QUANTIDADE DE TITULOS' in plain else 0
    def parse(self,filename,body):
        rows=_rows_from_text(ocr.extract(body))
        if not rows:raise ValueError('O comprovante BB foi reconhecido, mas os investimentos não puderam ser extraídos')
        return rows
    def normalize(self,source,db,options=None):
        values=source.values;errors=[]
        normalized={'row_number':source.locator['item'],'source_locator':source.locator,'event_type':'buy',
          'trade_date':str(values['trade_date']) if values['trade_date'] else None,
          'settlement_date':str(values['trade_date']) if values['trade_date'] else None,
          'currency':'BRL','quantity':str(values['quantity']),'amount':str(-values['amount']),
          'description':f"Comprovante BB: {values['title']}",
          'investment_terms':{'product_name':values['title'],'unit_price':str(values['unit_price']) if values['unit_price'] else None,
            'yield_text':values['yield_text'],'maturity_year':values['maturity_year'],'institution':'BB Banco de Investimento S/A','protocol':values['protocol']}}
        account=(options or {}).get('account_record')
        found=db.execute('select source_record_id,name,legacy_id from portfolio.account where source_record_id=?',[account]).fetchone() if account else None
        if not found:errors.append('selecione a conta Banco do Brasil correspondente')
        else:normalized.update(account_record=found[0],account=found[1])
        key=' '.join(_plain(values['title']).split())
        apps=db.execute("""select ap.source_record_id,ap.name from portfolio.application ap
          left join portfolio.asset a on a.batch_id=ap.batch_id and a.legacy_id=ap.asset_id
          where ap.account_id=? and (upper(trim(ap.name))=? or upper(trim(coalesce(a.name,'')))=?)""",
          [found[2] if found else -1,key,key]).fetchall()
        if len(apps)!=1:errors.append(f'aplicação não encontrada de forma única: {values["title"]}')
        else:normalized.update(application_record=apps[0][0],application=apps[0][1])
        if not values['trade_date']:errors.append('data da operação não identificada')
        normalized['errors']=errors;return normalized

BB_FIXED_INCOME_ADAPTER=register(BBFixedIncomeAdapter())
