"""Load official B3 Ibovespa daily closes for a year range."""
import argparse,json
from datetime import date
from pathlib import Path

from fin2.portfolio.b3_ibovespa import capture,fetch
from warehouse.database import connect,migrate


def run(database,batch,start_year=2000,end_year=None):
    database=Path(database).resolve(strict=True);end_year=end_year or date.today().year
    with connect(database) as db:
        migrate(db)
        catalog=db.execute("""SELECT source_record_id,abbreviation FROM market.benchmark_catalog
          WHERE batch_id=? AND abbreviation='IBO'""",[batch]).fetchone()
    if not catalog:raise ValueError('Ibovespa não encontrado no lote')
    counts={}
    for year in range(start_year,end_year+1):
        endpoint,body,captured_at=fetch(year)
        with connect(database) as db:counts[str(year)]=capture(db,catalog,endpoint,body,captured_at,year)
    return {'years':counts,'points_processed':sum(counts.values())}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,required=True);parser.add_argument('--batch',required=True)
    parser.add_argument('--start-year',type=int,default=2000);parser.add_argument('--end-year',type=int)
    args=parser.parse_args();print(json.dumps(run(args.database,args.batch,args.start_year,args.end_year)))


if __name__=='__main__':main()
