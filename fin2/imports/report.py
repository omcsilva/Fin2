"""Export a private exception report from the imported audit layer."""

import argparse
import json
from pathlib import Path

import duckdb

from fin2.imports.fin1 import REPOSITORY, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY) or output.exists():
        parser.error("Report must be a new file outside the repository")
    with duckdb.connect(str(args.database.resolve()), read_only=True) as connection:
        batches = [r[0] for r in connection.execute("SELECT batch_id FROM import_batch ORDER BY imported_at").fetchall()]
        report = {"batches": []}
        for batch in batches:
            item = summary(connection, batch)
            item["issues"] = [{"code": code,"source_database": db,"source_table": table,"legacy_id": identifier,"details":json.loads(details)}
                for code,db,table,identifier,details in connection.execute(
                    "SELECT i.code,r.database_name,r.table_name,r.legacy_id,i.details FROM import_issue i LEFT JOIN source_record r USING(record_id) WHERE i.batch_id=? ORDER BY i.code,r.legacy_id,i.issue_id", [batch]
                ).fetchall()]
            item["table_counts"] = [{"database":db,"table":table,"rows":count} for db,table,count in connection.execute(
                "SELECT database_name,table_name,row_count FROM source_table WHERE batch_id=? ORDER BY database_name,table_name",[batch]
            ).fetchall()]
            report["batches"].append(item)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2)
    print("Private report written; batches:",len(batches))


if __name__ == "__main__":
    main()
