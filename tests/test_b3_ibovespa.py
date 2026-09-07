import base64
from datetime import datetime,timezone
from decimal import Decimal
import unittest

from fin2.portfolio.b3_ibovespa import parse


class B3IbovespaTests(unittest.TestCase):
    def test_parse_official_year_matrix(self):
        csv='IBOVESPA - 2025\r\nDia;Jan;Fev;Mar;Abr;Mai;Jun;Jul;Ago;Set;Out;Nov;Dez\r\n\r\n2;120.125,39;;;;;;;;;;;\r\n3;;125.970,46;;;;;;;;;;\r\n'
        self.assertEqual(parse(base64.b64encode(csv.encode()),2025),[
          (datetime(2025,1,2).date(),Decimal('120125.39')),
          (datetime(2025,2,3).date(),Decimal('125970.46'))])

    def test_rejects_wrong_year_or_encoding(self):
        with self.assertRaises(ValueError):parse(b'not-base64',2025)
        body=base64.b64encode(b'IBOVESPA - 2024\nDia;Jan;Fev;Mar;Abr;Mai;Jun;Jul;Ago;Set;Out;Nov;Dez\n1;1;;;;;;;;;;;')
        with self.assertRaises(ValueError):parse(body,2025)


if __name__=='__main__':unittest.main()
