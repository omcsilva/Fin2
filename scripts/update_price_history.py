"""Fetch and persist audited daily closes for all compatible assets."""
import argparse,json
from pathlib import Path
from fin2.portfolio.price_history import capture,fetch
from warehouse.database import connect,migrate

def run(database,batch,range_name):
 with connect(Path(database).resolve(strict=True)) as db:
  migrate(db)
  rows=db.execute("""select a.source_record_id,a.symbol,
   min(coalesce(m.trade_date,m.settlement_date)) filter(where o.quantity_multiplier>0 and abs(m.source_quantity)>0) first_investment
   from market.asset_catalog a
   join portfolio.application ap on ap.batch_id=a.batch_id and ap.asset_id=a.legacy_id
   join portfolio.movement m on m.batch_id=ap.batch_id and m.application_id=ap.legacy_id and m.settlement_date is not null
   left join portfolio.operation o on o.batch_id=m.batch_id and o.legacy_id=m.operation_id
   where a.batch_id=?
   and configured_provider='atuBrAPI' and currency in ('REAL','BRL')
   and try_cast(configured_multiplier as decimal(28,10))=1
   and regexp_full_match(symbol,'[A-Z]{4}[0-9]{1,2}')
   group by a.source_record_id,a.symbol having first_investment is not null order by a.symbol""",[batch]).fetchall()
 total=0;failures=[]
 for record,symbol,first_investment in rows:
  try: body,when=fetch([symbol],start_date=first_investment)
  except ValueError as error:
   failures.append({'symbol':symbol,'start_date':str(first_investment),'error':str(error)});continue
  with connect(Path(database).resolve(strict=True)) as db: total+=capture(db,[(record,symbol)],body,when)['points']
 return {'assets':len(rows),'points_processed':total,'failed':failures,'policy':'from_first_investment'}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database',type=Path,required=True);p.add_argument('--batch',required=True);p.add_argument('--range',default='max',help=argparse.SUPPRESS)
 a=p.parse_args();print(json.dumps(run(a.database,a.batch,a.range)))
if __name__=='__main__':main()
