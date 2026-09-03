"""Record reviewed Fin1 position decisions without changing imported records."""

import argparse
import hashlib
import json
from pathlib import Path

from warehouse.database import connect, migrate


ZERO_POSITIONS = {
    165: "SPXI11",
    171: "MSFT34",
    172: "TSMC34",
    173: "AMER3",
}


def decision_id(batch_id, application_id):
    return hashlib.sha256(f"{batch_id}:application:{application_id}".encode()).hexdigest()


def apply(database, batch_id):
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        if not db.execute("SELECT 1 FROM import_batch WHERE batch_id=?", [batch_id]).fetchone():
            raise ValueError("Unknown import batch")
        db.execute("BEGIN")
        try:
            for application_id, symbol in ZERO_POSITIONS.items():
                row = db.execute("""
                    SELECT p.symbol,q.legacy_quantity,q.all_settled_quantity,q.legacy_delta,q.incomplete_count
                    FROM portfolio.quantity_check q JOIN portfolio.position p
                      ON p.batch_id=q.batch_id AND p.legacy_id=q.application_id
                    WHERE q.batch_id=? AND q.application_id=?
                """, [batch_id, application_id]).fetchone()
                if row != (symbol, row[1], 0, -row[1], 0):
                    raise ValueError(f"Evidence changed for application {application_id}: {row}")
                evidence = {"symbol": symbol, "legacy_quantity": str(row[1]),
                            "settled_movement_sum": "0", "legacy_delta": str(row[3])}
                db.execute("""
                    INSERT INTO ledger.reconciliation_decision
                    (decision_id,batch_id,subject_type,subject_id,status,resolution,quantity_override,rationale,evidence)
                    VALUES (?,?, 'application',?,'resolved','closed_position',0,?,?)
                    ON CONFLICT (batch_id,subject_type,subject_id) DO NOTHING
                """, [decision_id(batch_id, application_id), batch_id, application_id,
                      "Compras e vendas liquidadas se anulam; o agregado da aplicação no Fin1 está obsoleto.",
                      json.dumps(evidence)])

            application_id = 316
            row = db.execute("""
                SELECT p.asset_name,p.class_name,q.legacy_quantity,q.all_settled_quantity,
                       count(*) FILTER (WHERE d.source_quantity=0),count(*)
                FROM portfolio.quantity_check q JOIN portfolio.position p
                  ON p.batch_id=q.batch_id AND p.legacy_id=q.application_id
                JOIN portfolio.quantity_detail d
                  ON d.batch_id=q.batch_id AND d.application_id=q.application_id
                WHERE q.batch_id=? AND q.application_id=?
                GROUP BY ALL
            """, [batch_id, application_id]).fetchone()
            if not row or row[1] != "Caixa" or row[2] != 1000 or row[3] != 0 or row[4] != row[5]:
                raise ValueError(f"Evidence changed for application 316: {row}")
            evidence = {"asset": row[0], "class": row[1], "legacy_quantity": str(row[2]),
                        "settled_movement_sum": str(row[3]), "zero_quantity_movements": row[4]}
            db.execute("""
                INSERT INTO ledger.reconciliation_decision
                (decision_id,batch_id,subject_type,subject_id,status,resolution,quantity_override,rationale,evidence)
                VALUES (?,?, 'application',?,'pending','monetary_instrument',NULL,?,?)
                ON CONFLICT (batch_id,subject_type,subject_id) DO NOTHING
            """, [decision_id(batch_id, application_id), batch_id, application_id,
                  "Instrumento de caixa com valores financeiros e quantidades/acumulados incompatíveis; requer reconciliação monetária.",
                  json.dumps(evidence)])
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise
        return dict(db.execute("SELECT status,count(*) FROM ledger.reconciliation_decision WHERE batch_id=? GROUP BY status", [batch_id]).fetchall())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--batch", required=True)
    args = parser.parse_args()
    print(json.dumps(apply(args.database, args.batch), ensure_ascii=False))


if __name__ == "__main__":
    main()
