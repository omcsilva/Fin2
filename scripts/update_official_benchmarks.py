"""Load official BCB benchmark series from 2000-01-01 in bounded windows."""
import argparse,json
from datetime import date
from pathlib import Path
from fin2.portfolio.bcb_history import fetch,capture
from warehouse.database import connect,migrate
def run(database,batch):
 database=Path(database).resolve(strict=True)
 with connect(database) as db:
  migrate(db);rows=db.execute('select source_record_id,abbreviation,sgs_code,unit,frequency from market.official_benchmark_catalog where batch_id=? order by legacy_id',[batch]).fetchall()
 total=0;counts={};failures=[];today=date.today()
 for row in rows:
  cursor=date(2000,1,1);counts[row[1]]=0
  while cursor<=today:
   end=date(min(cursor.year+8,today.year),12,31) if cursor.year+8<today.year else today
   try:
    endpoint,body,when=fetch(row[2],cursor,end)
    with connect(database) as db: n=capture(db,row,endpoint,body,when,cursor,end)
    total+=n;counts[row[1]]+=n
   except ValueError as error: failures.append({'benchmark':row[1],'start':str(cursor),'end':str(end),'error':str(error)})
   cursor=date(end.year+1,1,1)
 return {'benchmarks':counts,'points_processed':total,'failed':failures,'start_date':'2000-01-01'}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database',type=Path,required=True);p.add_argument('--batch',required=True);a=p.parse_args();print(json.dumps(run(a.database,a.batch),ensure_ascii=False))
if __name__=='__main__':main()
