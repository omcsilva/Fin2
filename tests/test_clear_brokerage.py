from datetime import date
from decimal import Decimal
import unittest

from fin2.imports.clear_brokerage import _rows_from_text


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


if __name__=='__main__':unittest.main()
