from datetime import date
from decimal import Decimal
import unittest
from unittest.mock import patch

from fin2.imports.clear_brokerage import ClearBrokerageNoteAdapter, _rows_from_text
from fin2.imports.base import SourceRow


class ClearBrokerageAdapterTests(unittest.TestCase):
    def test_extracts_trade_with_page_locator_and_financial_types(self):
        text='''Negócios realizados
Q
Negociação
C/V
Tipo mercado
Prazo
Especificação do título
Obs. (*)
Quantidade
Preço / Ajuste
Valor Operação / Ajuste
D/C
1-BOVESPA
C
VISTA
ACME PN
N1
1.000
12,34
12.340,00
D
NOTA DE NEGOCIAÇÃO
Nr. nota
123
Data pregão
08/06/2021
Taxa de liquidação
D
1,20
Emolumentos
D
0,80
I.R.R.F. s/ operações, base R$ 10.000,00
D
0,50
'''
        rows=_rows_from_text(text,3)
        self.assertEqual(len(rows),4)
        self.assertEqual(rows[0].locator,{'page':3,'section':'negocios_realizados','item':1})
        self.assertEqual(rows[0].values['trade_date'],date(2021,6,8))
        self.assertEqual(rows[0].values['quantity'],Decimal('1000'))
        self.assertEqual(rows[0].values['amount'],Decimal('12340.00'))
        self.assertEqual([(row.values['category'],row.values['amount']) for row in rows[1:]],
                         [('fee',Decimal('1.20')),('fee',Decimal('0.80')),('tax',Decimal('0.50'))])

    def test_recognizes_and_extracts_xp_note_with_trade_on_one_line(self):
        text = '''Nota de Negociação
Data de Referência: 11/08/2025
XP INVESTIMENTOS CORRETORA DE CÂMBIO, TÍTULOS E VALORES MOBILIÁRIOS S.A.
Data pregão
11/08/2025
Nº Nota
117684642
Negociações
Q Negociação C/V Tipo mercado Prazo Especificação do título Obs. (*) Quantidade Preço / Ajuste Valor Operação / Ajuste D/C
1-BOVESPA V VISTA LIGHT S/A LIGT3 ON NM @ 2000 7,00 14.000,00 C
Taxa de liquidação
3,13
D
'''
        adapter = ClearBrokerageNoteAdapter()
        with patch('fin2.imports.clear_brokerage._text', return_value=text):
            self.assertEqual(adapter.detect(
                'nota.pdf', b'\xef\xbb\xbf%PDF-fixture'), 98)
        with patch('fin2.imports.clear_brokerage._text', return_value=''):
            self.assertEqual(adapter.detect('nota.pdf', b'%PDF-fixture'), 10)
        rows = _rows_from_text(text)
        self.assertEqual(rows[0].values, {
            'kind': 'trade', 'side': 'V', 'market': 'VISTA', 'asset': 'LIGHT S/A LIGT3 ON NM',
            'quantity': Decimal('2000'), 'price': Decimal('7.00'), 'amount': Decimal('14000.00'),
            'trade_date': date(2025, 8, 11)})

    def test_uses_reference_date_on_summary_page_and_ticker_for_application(self):
        rows = _rows_from_text('''Data de Referência: 11/08/2025
Resumo Financeiro
Taxa de liquidação
3,13
D
''', 2)
        self.assertEqual(rows[0].values['trade_date'], date(2025, 8, 11))

        class Result:
            def __init__(self, rows): self.rows=rows
            def fetchone(self): return self.rows[0] if self.rows else None
            def fetchall(self): return self.rows

        class Database:
            def execute(self, sql, parameters):
                if 'from portfolio.account' in sql:
                    return Result([('account-record','Conta XP',5)])
                self.assert_ticker = parameters[-1]
                return Result([('application-record','MLu M XP LIGT3')])

        database=Database()
        normalized=ClearBrokerageNoteAdapter().normalize(SourceRow(
            {'page':1,'item':1},{'kind':'trade','side':'V','market':'VISTA',
             'asset':'LIGHT S/A LIGT3 ON NM','quantity':Decimal('2000'),
             'price':Decimal('7'),'amount':Decimal('14000'),'trade_date':date(2025,8,11)}),
            database,{'account_record':'account-record'})
        self.assertEqual(database.assert_ticker,'LIGT3')
        self.assertEqual(normalized['application_record'],'application-record')
        self.assertEqual(normalized['errors'],[])

if __name__=='__main__':unittest.main()
