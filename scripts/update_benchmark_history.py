"""Load Fin1 benchmark series from 2000-01-01."""
import argparse,json
from pathlib import Path
from fin2.portfolio.benchmark_history import fetch,capture
from warehouse.database import connect,migrate
def run(database,batch):
 database=Path(database).resolve(strict=True)
 with connect(database) as db:
  migrate(db);rows=db.execute("select source_record_id,abbreviation,provider_family,provider_symbol from market.benchmark_catalog where batch_id=? order by provider_family,provider_symbol",[batch]).fetchall()
 total=0;failures=[]
 for family in ('macro','currency','stocks'):
  group=[r for r in rows if r[2]==family]
  if not group: continue
  try:
   body,when=fetch(family,[r[3] for r in group])
   with connect(database) as db: total+=capture(db,group,body,when)
  except ValueError as error: failures.append({'family':family,'symbols':[r[3] for r in group],'error':str(error)})
 return {'benchmarks':len(rows),'points_processed':total,'failed':failures,'start_date':'2000-01-01'}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database',type=Path,required=True);p.add_argument('--batch',required=True);a=p.parse_args();print(json.dumps(run(a.database,a.batch)))
if __name__=='__main__':main()
