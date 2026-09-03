"""Record reviewed market-provider mappings without changing imported Fin1 data."""
import argparse
import json
from pathlib import Path

from warehouse.database import connect,migrate


def apply(database,batch):
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        row=db.execute("""SELECT source_record_id,symbol,currency,legacy_code,configured_provider,
          configured_multiplier FROM market.asset_catalog WHERE batch_id=? AND legacy_id=182""",
          [batch]).fetchone()
        if (not row or row[1:4] != ('INRD11','REAL','BRINRDCTF002')
                or row[4] is not None or row[5] is not None):
            raise ValueError(f'Evidence changed for INRD11: {row}')
        evidence={'legacy_asset_id':182,'isin':'BRINRDCTF002','symbol':'INRD11',
                  'source':'B3 issuer and corporate-action records'}
        db.execute("""INSERT INTO market.asset_provider_override
          (source_record_id,provider,symbol,multiplier,rationale,evidence)
          VALUES (?,'atuBrAPI','INRD11',1,?,?)
          ON CONFLICT(source_record_id) DO UPDATE SET provider=excluded.provider,
            symbol=excluded.symbol,multiplier=excluded.multiplier,
            rationale=excluded.rationale,evidence=excluded.evidence,decided_at=now()""",
          [row[0],'Ticker e ISIN conferidos em registros oficiais da B3; brapi adotada como fonte operacional de preço.',
           json.dumps(evidence,ensure_ascii=False)])
        return {'source_record_id':row[0],'symbol':'INRD11','provider':'atuBrAPI'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database',type=Path,required=True);p.add_argument('--batch',required=True)
    a=p.parse_args();print(json.dumps(apply(a.database,a.batch),ensure_ascii=False))


if __name__=='__main__': main()
