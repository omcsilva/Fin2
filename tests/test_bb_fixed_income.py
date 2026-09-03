from datetime import date
from decimal import Decimal
import unittest
from unittest.mock import patch

from fin2.imports.bb_fixed_income import BBFixedIncomeAdapter,_rows_from_text

class BBFixedIncomeAdapterTests(unittest.TestCase):
    TEXT='''Nº de protocolo - 24498467
Data da operação 02/01/2020
Instituição BB BANCO DE INVESTIMENTO S/A
Tesouro Selic 2025
Quantidade de títulos 4,73
Valor unitário R$10.462,94
Rentabilidade 0,020%
Valor líquido R$49.489,70
Taxa da instituição financeira R$0,00
Taxa da B3 R$0,00
Valor bruto R$49.489,70
'''
    def test_extracts_purchase_and_contract_terms(self):
        rows=_rows_from_text(self.TEXT)
        self.assertEqual(len(rows),1)
        values=rows[0].values
        self.assertEqual(values['trade_date'],date(2020,1,2))
        self.assertEqual(values['quantity'],Decimal('4.73'))
        self.assertEqual(values['unit_price'],Decimal('10462.94'))
        self.assertEqual(values['amount'],Decimal('49489.70'))
        self.assertEqual(values['maturity_year'],2025)
        self.assertEqual(values['protocol'],'24498467')

    @patch('fin2.imports.bb_fixed_income.ocr.extract',return_value=TEXT)
    @patch('fin2.imports.bb_fixed_income.ocr.available',return_value=True)
    def test_content_detection_uses_ocr(self,available,extract):
        self.assertEqual(BBFixedIncomeAdapter().detect('receipt.png',b'\x89PNG\r\n\x1a\nbody'),96)

    def test_unreadable_quantity_blocks_document(self):
        with self.assertRaisesRegex(ValueError,'OCR incompleto'):
            _rows_from_text(self.TEXT.replace('títulos 4,73','títulos ilegível'))

    def test_image_adapter_reaches_preview_without_csv_headers(self):
        from tests import test_fin1_import as fixtures
        from fin2.imports.generic import stage
        from warehouse.database import connect
        f=fixtures.ImportTests();f.setUp()
        try:
            f.run_import()
            with connect(f.database) as db:
                account=db.execute('select source_record_id from portfolio.account limit 1').fetchone()[0]
            with patch('fin2.imports.bb_fixed_income.ocr.extract',return_value=self.TEXT):
                identifier,status=stage(f.database,f.database.parent/'documents','receipt.png',
                  b'\x89PNG\r\n\x1a\nbody',options={'adapter_id':'bb-tesouro-receipt','account_record':account})
            self.assertEqual(status,'preview')
            with connect(f.database) as db:
                self.assertEqual(db.execute('select adapter_id from ledger.file_import where import_id=?',[identifier]).fetchone()[0],'bb-tesouro-receipt')
        finally:f.tearDown()

if __name__=='__main__':unittest.main()
