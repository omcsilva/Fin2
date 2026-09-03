from datetime import date
from decimal import Decimal
import unittest
from fin2.imports.apex_statement import _rows_from_text,_statement_metadata

class ApexStatementAdapterTests(unittest.TestCase):
    def test_extracts_cash_interest_and_security_purchase(self):
        text='''TRANSACTION DATE ACCOUNT TYPE DESCRIPTION QUANTITY PRICE DEBIT CREDIT
JOURNAL 07/13/23 C Journal from $25,000.00
INTEREST 07/31/23 C UNITED STATES TREASURY NOTE $23.45
BOUGHT 07/18/23 C UNITED STATES TREASURY NOTE 1,000 $98.25 $982.50
'''
        rows=_rows_from_text(text,8)
        self.assertEqual([row.values['kind'] for row in rows],['JOURNAL','INTEREST','BOUGHT'])
        self.assertEqual(rows[0].locator['page'],8)
        self.assertEqual(rows[0].values['trade_date'],date(2023,7,13))
        self.assertEqual(rows[0].values['amount'],Decimal('25000.00'))
        self.assertEqual(rows[2].values['quantity'],Decimal('1000'))
        self.assertEqual(rows[2].values['amount'],Decimal('982.50'))

    def test_extracts_statement_period_and_cash_balances(self):
        metadata=_statement_metadata('''July 1, 2023 - July 31, 2023
OPENING BALANCE CLOSING BALANCE
Cash account $1,234.50 $25,678.90''')
        self.assertEqual(metadata,{'period_start':'2023-07-01','period_end':'2023-07-31',
          'currency':'USD','opening_balance':'1234.50','closing_balance':'25678.90'})

if __name__=='__main__':unittest.main()
