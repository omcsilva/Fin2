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
    trade_date=None
    for label in ('DATA PREGAO','DATA DE REFERENCIA'):
        for index,line in enumerate(plain):
            if not line.startswith(label):continue
            candidates=(lines[index],lines[index+1] if index+1<len(lines) else '')
            match=next((re.search(r'\b\d{2}/\d{2}/\d{4}\b',candidate) for candidate in candidates
                        if re.search(r'\b\d{2}/\d{2}/\d{4}\b',candidate)),None)
            if match:trade_date=datetime.strptime(match.group(),'%d/%m/%Y').date()
            break
        if trade_date:break
    rows=[]
    for index,line in enumerate(plain):
        compact = re.fullmatch(
            r'\d+-BOVESPA\s+([CV])\s+(\S+)\s+(.+?)\s+([\d.]+)\s+([\d.]+,\d+)\s+([\d.]+,\d+)\s+[CD]',
            line)
        if compact:
            side, market, asset, quantity, price, gross = compact.groups()
            asset = re.sub(r'\s+(?:@|#|[28DFBTACPHXYLI])$', '', asset).strip()
            try:
                quantity, price, gross = map(_money, (quantity, price, gross))
            except InvalidOperation:
                continue
            rows.append(SourceRow({'page': page, 'section': 'negocios_realizados', 'item': len(rows)+1},
                                  {'kind': 'trade', 'side': side, 'market': market, 'asset': asset, 'quantity': quantity, 'price': price,
                                   'amount': gross, 'trade_date': trade_date}))
            continue
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
    components=(
        (r'\bTAXA\s+DE\s+LIQUIDA\w*\b','fee','Taxa de liquidação'),
        (r'\bTAXA\s+(?:DE\s+)?REGISTRO\b','fee','Taxa de registro'),
        (r'\bEMOLUMENTOS\b','fee','Emolumentos'),
        (r'\bTAXA\s+DE\s+TERMO\s*/\s*OPCOES\b','fee','Taxa de termo/opções'),
        (r'\bTAXA\s+A\.?N\.?A\.?\b','fee','Taxa A.N.A.'),
        (r'\bTAXA\s+DE\s+TRANSF\.?\s+DE\s+ATIVOS\b','fee','Taxa de transferência de ativos'),
        (r'\bTAXA\s+OPERACIONAL\b','fee','Taxa operacional'),
        (r'\bEXECU\w*\b','fee','Execução'),
        (r'\bTAXA\s+DE\s+CUSTODIA\b','fee','Taxa de custódia'),
        (r'\bCORRETAGEM\b','fee','Corretagem'),
        (r'\bISS\b','fee','ISS'),
        (r'\bTAXA\s+(?:DE\s+)?(?:NEGOCIACAO|BOVESPA|B3)\b','fee','Taxa Bovespa'),
        (r'\bOUTRAS\s+BOVESPA\b','fee','Taxa Bovespa'),
        (r'\bI\.?\s*R\.?\s*R\.?\s*F\.?\b','tax','IRRF'),
    )
    amount_pattern=re.compile(r'(?<![\d.,])(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}(?!\d)')
    handled_components=set()
    seen=set()

    def component_at(index):
        for component in components:
            match=re.search(component[0],plain[index])
            if match:return component,match
        return None

    def append_expense(component,value,debit_credit='D'):
        if value<=0 or component[2] in seen:return
        seen.add(component[2])
        rows.append(SourceRow({'page':page,'section':'resumo_financeiro','item':len(rows)+1},
          {'kind':'expense','category':component[1],'label':component[2],'amount':value,
           'debit_credit':debit_credit,'trade_date':trade_date}))

    def map_columnar_block(value_start,value_end,label_start,label_end,skip_values=0):
        labels=[]
        for label_index in range(label_start,label_end):
            found=component_at(label_index)
            if found:labels.append((label_index,found[0]))
        values=[]
        for value_index in range(value_start,value_end):
            values.extend(_money(value) for value in amount_pattern.findall(plain[value_index]))
        values=values[skip_values:]
        if len(values)!=len(labels):return
        for (label_index,component),value in zip(labels,values):
            handled_components.add(label_index)
            append_expense(component,value)

    summary_start=next((i for i,line in enumerate(plain)
                        if 'RESUMO FINANCEIRO' in line),None)
    if summary_start is not None:
        operations_header=next((i for i in range(summary_start,len(plain))
          if 'VALOR DAS OPERACOES' in plain[i] and 'LIQUIDO' not in plain[i]),None)
        cblc_header=next((i for i in range(summary_start,len(plain))
                          if plain[i]=='CBLC'),None)
        cblc_total=next((i for i in range((cblc_header or summary_start)+1,len(plain))
                         if 'TOTAL CBLC' in plain[i]),None)
        bovespa_header=next((i for i in range((cblc_total or summary_start)+1,len(plain))
          if 'BOVESPA / SOMA' in plain[i] and 'TOTAL' not in plain[i]),None)
        bovespa_total=next((i for i in range((bovespa_header or summary_start)+1,len(plain))
          if 'TOTAL BOVESPA / SOMA' in plain[i]),None)
        brokerage_header=next((i for i in range((bovespa_total or summary_start)+1,len(plain))
          if 'CORRETAGEM / DESPESAS' in plain[i]),None)
        brokerage_total=next((i for i in range((brokerage_header or summary_start)+1,len(plain))
          if 'TOTAL CORRETAGEM / DESPESAS' in plain[i]),None)

        if operations_header is not None and cblc_header is not None and cblc_total is not None:
            map_columnar_block(operations_header+1,cblc_header,
                               cblc_header+1,cblc_total,skip_values=1)
        if cblc_total is not None and bovespa_header is not None and bovespa_total is not None:
            map_columnar_block(cblc_total+1,bovespa_header,
                               bovespa_header+1,bovespa_total)
        if bovespa_total is not None and brokerage_header is not None and brokerage_total is not None:
            map_columnar_block(bovespa_total+1,brokerage_header,
                               brokerage_header+1,brokerage_total)

    for index,line in enumerate(plain):
        if index in handled_components:continue
        found=component_at(index)
        if not found:continue
        component,label_match=found
        if component[2] in seen:continue
        debit_credit=None;value=None
        for candidate_index in range(index,min(index+5,len(plain))):
            candidate=plain[candidate_index]
            start=label_match.end() if candidate_index==index else 0
            segment=candidate[start:]
            next_component=next((re.search(item[0],segment) for item in components
                                 if re.search(item[0],segment)),None)
            if next_component:segment=segment[:next_component.start()]
            code=re.search(r'(?<![A-Z])([CD])(?![A-Z])',segment)
            if code:debit_credit=code.group(1)
            amounts=list(amount_pattern.finditer(segment))
            if 'BASE' in segment:
                base_start=segment.index('BASE')
                base_amount=next((amount for amount in amounts
                                  if amount.start()>=base_start),None)
                amounts=[amount for amount in amounts if amount.start()<base_start]
                if base_amount:
                    amounts.extend(amount for amount in amount_pattern.finditer(segment)
                                   if amount.start()>base_amount.end())
            if amounts:
                try:value=_money(amounts[-1].group())
                except InvalidOperation:value=None
                if value is not None:break
            if next_component:break
        if value is not None:append_expense(component,value,debit_credit or 'D')
    return rows


class ClearBrokerageNoteAdapter:
    adapter_id='clear-brokerage-note';version='4';document_type='brokerage_note'
    def detect(self,filename,body):
        if b'%PDF-' not in body[:1024]:
            return 0
        plain=_plain(_text(body)).replace('\ufffd','')
        broker = 'CLEAR CORRETORA' in plain or 'XP INVESTIMENTOS CORRETORA' in plain
        note = 'NOTA DE NEGOCI' in plain or 'NEGOCIOS REALIZADOS' in plain
        structure = 'DATA PREGAO' in plain and (
            'BOVESPA' in plain or 'RESUMO FINANCEIRO' in plain)
        return 98 if note and (broker or structure) else 10
    def parse(self,filename,body):
        reader=PdfReader(io.BytesIO(body));rows=[]
        for page_number,page in enumerate(reader.pages,1):
            page_rows=_rows_from_text(page.extract_text() or '',page_number)
            for row in page_rows:
                rows.append(SourceRow({**row.locator,'item':len(rows)+1},row.values))
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
                    'description':values['label'],
                    'allocation_role':{'fee':'expense','tax':'withholding'}.get(values['category'])}
        else:
            normalized={'row_number':source.locator['item'],'source_locator':source.locator,
                    'event_type':'buy' if values['side']=='C' else 'sell',
                    'trade_date':str(values['trade_date']) if values['trade_date'] else None,
                    'settlement_date':str(values['trade_date']) if values['trade_date'] else None,
                    'currency':'BRL','quantity':str(values['quantity']),
                    'amount':str(-values['amount'] if values['side']=='C' else values['amount']),
                    'description':f"{values['asset']} ({values['market']})",
                    'allocation_role':'trade','allocation_weight':str(values['amount'])}
        account=(options or {}).get('account_record')
        found=db.execute('select source_record_id,name,legacy_id from portfolio.account where source_record_id=?',[account]).fetchone() if account else None
        if not found:errors.append('selecione a conta de corretagem correspondente')
        else:normalized.update(account_record=found[0],account=found[1])
        if 'kind' in values:
                if values['kind']=='trade':
                        key=' '.join(_plain(values['asset']).split())
                        ticker_match=re.search(r'\b[A-Z]{4}\d{1,2}\b',key)
                        ticker=ticker_match.group() if ticker_match else key
                        apps=db.execute("""select ap.source_record_id,ap.name from portfolio.application ap
                            left join portfolio.asset a on a.batch_id=ap.batch_id and a.legacy_id=ap.asset_id
                            where ap.account_id=? and (upper(trim(ap.name))=? or upper(trim(coalesce(a.symbol,'')))=?
                                or upper(trim(coalesce(a.name,'')))=? or upper(trim(coalesce(a.symbol,'')))=?)""",
                            [found[2] if found else -1,key,key,key,ticker]).fetchall()
                        if len(apps)!=1:errors.append(f'aplicação não encontrada de forma única: {values["asset"]}')
                        else:normalized.update(application_record=apps[0][0],application=apps[0][1])
                else:normalized.update(application_record=None,application='')
        if not values['trade_date']:errors.append('data do pregão não identificada')
        normalized['errors']=errors
        return normalized
CLEAR_ADAPTER=register(ClearBrokerageNoteAdapter())
