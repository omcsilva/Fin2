from decimal import Decimal
import unittest

from fin2.dashboard.templatetags.fin2_format import money,number


class FormattingTests(unittest.TestCase):
    def test_money_has_currency_brazilian_grouping_and_two_decimals(self):
        self.assertEqual(money(Decimal('1234.56'),'BRL'),'R$ 1.234,56')
        self.assertEqual(money(Decimal('123456.78'),'DOL'),'US$ 123.456,78')
        self.assertEqual(money(Decimal('123456.78'),'DOLAR'),'US$ 123.456,78')
        self.assertEqual(money(Decimal('-10.5'),'EUR'),'-€ 10,50')
        self.assertEqual(money(None,'BRL'),'—')

    def test_number_has_grouping_and_at_most_four_decimals(self):
        self.assertEqual(number(Decimal('1234567')),'1.234.567')
        self.assertEqual(number(Decimal('1234.56789')),'1.234,5679')
        self.assertEqual(number(Decimal('-10.5')),'-10,5')
        self.assertEqual(number(None),'—')
