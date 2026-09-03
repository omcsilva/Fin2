"""Clear/XP Brazilian brokerage-note PDF adapter."""
from datetime import datetime
from decimal import Decimal,InvalidOperation
import io,re,unicodedata

from pypdf import PdfReader

from fin2.imports.base import SourceRow
from fin2.imports.registry import register


def _plain(value):
    return ''.join(char for char in unicodedata.normalize('NFKD',str(value)) if not unicodedata.combining(char)).upper()


def _money(value):return Decimal(str(value).replace('.','').replace(',','.'))


def _text(body):
    try:return '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(body)).pages)
    except Exception:return ''


def _rows_from_text(text,page=1):
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    plain=[_plain(line).replace('\ufffd','') for line in lines]
    try:
        marker=next(i for i,line in enumerate(plain) if line.startswith('DATA PREGAO'))
        trade_date=datetime.strptime(re.sub(r'[^0-9/]','',lines[marker+1]),'%d/%m/%Y').date()
    except (StopIteration,IndexError,ValueError):trade_date=None
    rows=[]
    for index,line in enumerate(plain):
        if not re.fullmatch(r'\d+-BOVESPA',line):continue
        try:
            side=plain[index+1];market=plain[index+2];cursor=index+3
            if re.fullmatch(r'\d{2}/\d{2}',plain[cursor]):cursor+=1
            asset=lines[cursor];numbers=[]
            for candidate in lines[cursor+1:cursor+10]:
                if _plain(candidate) in {'C','D'}:break
                try:numbers.append(_money(candidate))
                except InvalidOperation:pass
            quantity,price,gross=numbers[-3:]
        except (IndexError,InvalidOperation,ValueError):continue
        if side not in {'C','V'} or quantity<=0 or gross<=0:continue
        rows.append(SourceRow({'page':page,'section':'negocios_realizados','item':len(rows)+1},
          {'kind':'trade','side':side,'market':market,'asset':asset,'quantity':quantity,'price':price,
           'amount':gross,'trade_date':trade_date}))
    components=(('TAXA DE LIQUIDA','fee','Taxa de liquidação'),
                ('TAXA DE REGISTRO','fee','Taxa de registro'),
                ('EMOLUMENTOS','fee','Emolumentos'),('TAXA OPERACIONAL','fee','Taxa operacional'),
                ('EXECU','fee','Execução'),('TAXA DE CUSTODIA','fee','Taxa de custódia'),
                ('I.R.R.F.','tax','IRRF'),('IRRF','tax','IRRF'))
    seen=set()
    for index,line in enumerate(plain):
        match=next((item for item in components if item[0] in line),None)
        if not match or match[2] in seen:continue
        debit_credit=None;value=None
        for candidate in lines[index+1:index+5]:
            code=_plain(candidate)
            if code in {'C','D'}:debit_credit=code;continue
            try:value=_money(candidate);break
            except InvalidOperation:continue
        if value is None or value<=0:continue
        seen.add(match[2])
        rows.append(SourceRow({'page':page,'section':'resumo_financeiro','item':len(rows)+1},
          {'kind':'expense','category':match[1],'label':match[2],'amount':value,
           'debit_credit':debit_credit or 'D','trade_date':trade_date}))
    return rows


class ClearBrokerageNoteAdapter:
    adapter_id='clear-brokerage-note';version='1';document_type='brokerage_note'
    def detect(self,filename,body):
        if not body.startswith(b'%PDF-'):return 0
        plain=_plain(_text(body)).replace('\ufffd','')
        return 98 if 'CLEAR CORRETORA' in plain and ('NOTA DE NEGOCI' in plain or 'NEGOCIOS REALIZADOS' in plain) else 0
    def parse(self,filename,body):
        reader=PdfReader(io.BytesIO(body));rows=[]
        for page_number,page in enumerate(reader.pages,1):
            page_rows=_rows_from_text(page.extract_text() or '',page_number)
            rows.extend(SourceRow({**row.locator,'item':len(rows)+index},row.values)
                        for index,row in enumerate(page_rows,1))
        if not rows:raise ValueError('A nota Clear foi reconhecida, mas nenhuma negociação pôde ser extraída')
        return rows
    def normalize(self,source,db,options=None):
        values=source.values;errors=[]
        if values['kind']=='expense':
            normalized={'row_number':source.locator['item'],'source_locator':source.locator,
                    'event_type':values['category'],'trade_date':str(values['trade_date']) if values['trade_date'] else None,
                    'settlement_date':str(values['trade_date']) if values['trade_date'] else None,
                    'currency':'BRL','quantity':None,
                    'amount':str(-values['amount'] if values['debit_credit']=='D' else values['amount']),
                    'description':f"Nota Clear: {values['label']}",
                    'allocation_role':'expense' if values['category']=='fee' else None}
        else:
            normalized={'row_number':source.locator['item'],'source_locator':source.locator,
                    'event_type':'buy' if values['side']=='C' else 'sell',
                    'trade_date':str(values['trade_date']) if values['trade_date'] else None,
                    'settlement_date':str(values['trade_date']) if values['trade_date'] else None,
                    'currency':'BRL','quantity':str(values['quantity']),
                    'amount':str(-values['amount'] if values['side']=='C' else values['amount']),
                    'description':f"Nota Clear: {values['asset']} ({values['market']})",
                    'allocation_role':'trade','allocation_weight':str(values['amount'])}
        account=(options or {}).get('account_record')
        found=db.execute('select source_record_id,name,legacy_id from portfolio.account where source_record_id=?',[account]).fetchone() if account else None
        if not found:errors.append('selecione a conta de corretagem correspondente')
        else:normalized.update(account_record=found[0],account=found[1])
        if values['kind']=='trade':
            key=' '.join(_plain(values['asset']).split())
            apps=db.execute("""select ap.source_record_id,ap.name from portfolio.application ap
              left join portfolio.asset a on a.batch_id=ap.batch_id and a.legacy_id=ap.asset_id
              where ap.account_id=? and (upper(trim(ap.name))=? or upper(trim(coalesce(a.symbol,'')))=?
                or upper(trim(coalesce(a.name,'')))=?)""",
              [found[2] if found else -1,key,key,key]).fetchall()
            if len(apps)!=1:errors.append(f'aplicação não encontrada de forma única: {values["asset"]}')
            else:normalized.update(application_record=apps[0][0],application=apps[0][1])
        else:normalized.update(application_record=None,application='')
        if not values['trade_date']:errors.append('data do pregão não identificada')
        normalized['errors']=errors
        return normalized


CLEAR_ADAPTER=register(ClearBrokerageNoteAdapter())
