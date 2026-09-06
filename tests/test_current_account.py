from datetime import date
from decimal import Decimal
import unittest
from unittest.mock import patch

from fin2.portfolio.current_account import summarize


class CurrentAccountTests(unittest.TestCase):
    def test_uninvested_dividends_and_sale_proceeds_are_investment_value(self):
        flows = [dict(currency='BRL', amount=Decimal('1000'),
                      category='external_contribution', settlement_date=date(2024,1,1))]
        positions = [dict(currency='BRL', reference_value=Decimal('800'), valuation_status='priced')]
        cash = [dict(currency='REAL', cash_value=Decimal('300'), pending=0)]
        with patch('fin2.portfolio.current_account.query', return_value=flows):
            row = summarize(None, 'batch', date(2024,12,31), positions, cash)[0]
        self.assertEqual(row['investment_value'], Decimal('1100'))
        self.assertEqual(row['invested'], Decimal('1000'))
        self.assertEqual(row['withdrawn'], 0)
        self.assertEqual(row['result'], Decimal('100'))

    def test_result_normalizes_currency_and_keeps_dollars_separate(self):
        flows = [dict(currency='REAL', amount=Decimal('1000'), category='external_contribution', settlement_date=date(2024,1,1)),
                 dict(currency='BRL', amount=Decimal('-300'), category='external_withdrawal', settlement_date=date(2024,2,1))]
        positions = [dict(currency='REAL', reference_value=Decimal('900'), valuation_status='priced'),
                     dict(currency='DOL', reference_value=Decimal('50'), valuation_status='priced'),
                     dict(currency='REAL', reference_value=None, valuation_status='closed')]
        with patch('fin2.portfolio.current_account.query', return_value=flows):
            rows = summarize(None, 'batch', date(2024,12,31), positions)
        self.assertEqual(rows[0]['result'], Decimal('200'))
        self.assertEqual(rows[0]['withdrawn'], Decimal('300'))
        self.assertEqual(rows[1]['currency'], 'USD')
        self.assertEqual(rows[1]['result'], Decimal('50'))

    def test_incomplete_value_or_flow_prevents_result(self):
        with patch('fin2.portfolio.current_account.query', return_value=[]):
            rows = summarize(None, 'batch', date(2024,12,31), [
                dict(currency='REAL', reference_value=None, valuation_status='quantity_review')])
        self.assertIsNone(rows[0]['result'])
        with patch('fin2.portfolio.current_account.query', return_value=[
            dict(currency='REAL', amount=Decimal('-10'), category='external_contribution', settlement_date=date(2024,1,1))]):
            rows = summarize(None, 'batch', date(2024,12,31), [])
        self.assertIsNone(rows[0]['result'])
