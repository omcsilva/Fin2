"""Import one official B3 COTAHIST annual ZIP into the Fin2 warehouse."""
import argparse
from datetime import datetime,timezone
from pathlib import Path

from fin2.portfolio.b3_history import capture
from warehouse.database import connect,migrate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',required=True)
    parser.add_argument('archive')
    args=parser.parse_args()
    database=Path(args.database).resolve(strict=True)
    archive=Path(args.archive).resolve(strict=True)
    body=archive.read_bytes()
    with connect(database) as connection:
        migrate(connection)
        result=capture(connection,archive.name,body,datetime.now(timezone.utc))
    print(f"{result['points']} fechamentos B3 importados; captura {result['capture_id']}")
    if result['ambiguous_symbols']:
        print('Tickers ambíguos ignorados: '+', '.join(result['ambiguous_symbols']))


if __name__=='__main__': main()
