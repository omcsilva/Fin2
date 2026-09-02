"""Apply portfolio projections and export a private reconciliation report offline."""
import argparse
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path

from warehouse.database import connect, migrate
from warehouse.repositories.dashboard import query


def prepare(database):
    database = Path(database).resolve(strict=True)
    with connect(database) as connection:
        migrate(connection)
        # Materialize every typed column to detect bad casts rather than silently
        # turning invalid legacy values into zero or relying on COUNT pruning.
        counts = {}
        for table in ("investor","institution","currency","collection","account","asset",
                      "application","membership","operation","movement","cash_entry","position","cash_check","cash_detail","quantity_detail","valuation","valuation_totals","allocation"):
            counts[table] = len(connection.execute(f"SELECT * FROM portfolio.{table}").fetchall())
        for table in ('asset_catalog', 'identifier_candidate', 'price_observation'):
            counts['market.'+table] = len(connection.execute(f'SELECT * FROM market.{table}').fetchall())
        discrepancies = query(connection,"SELECT batch_id,application_id,legacy_quantity,all_settled_quantity,legacy_delta,incomplete_count FROM portfolio.quantity_check WHERE legacy_delta<>0 OR legacy_delta IS NULL ORDER BY batch_id,application_id")
        cash_discrepancies=query(connection,"SELECT batch_id,legacy_id,legacy_balance,reconstructed_balance,legacy_delta,incomplete_count FROM portfolio.cash_check WHERE legacy_delta<>0 OR legacy_delta IS NULL ORDER BY batch_id,legacy_id")
        cash_quality=query(connection,"SELECT batch_id,count(*) FILTER (WHERE account_id IS NULL) AS unassigned_entries,count(*) FILTER (WHERE running_delta<>0) AS running_balance_differences FROM portfolio.cash_detail GROUP BY batch_id")
        return {"counts":counts,"quantity_discrepancies":discrepancies,"cash_discrepancies":cash_discrepancies,"cash_quality":cash_quality,
                "policy":"Exact DECIMAL comparison against legacy quantities and cash balances. Cutoff values shown separately. No source corrections, external-statement reconciliation, or portfolio valuation validation."}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args()
    if args.report.resolve().is_relative_to(Path(__file__).resolve().parents[2]) or args.report.exists():
        parser.error("Report must be a new file outside the repository")
    result=prepare(args.database)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    with args.report.open('x',encoding='utf-8') as output:
        json.dump(result,output,ensure_ascii=False,indent=2,default=str)
    print(json.dumps({"counts":result["counts"],"quantity_discrepancies":len(result["quantity_discrepancies"]),"cash_discrepancies":len(result["cash_discrepancies"]),"cash_quality":result['cash_quality']}))


if __name__ == '__main__':
    main()
