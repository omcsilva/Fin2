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
                effective_date=db.execute("SELECT max(settlement_date) FROM portfolio.movement WHERE batch_id=? AND application_id=?",
                                          [batch_id,application_id]).fetchone()[0]
                db.execute("""
                    INSERT INTO ledger.reconciliation_decision
                    (decision_id,batch_id,subject_type,subject_id,status,resolution,quantity_override,rationale,evidence,effective_date)
                    VALUES (?,?, 'application',?,'resolved','closed_position',0,?,?,?)
                    ON CONFLICT (batch_id,subject_type,subject_id) DO UPDATE SET
                      status=excluded.status,resolution=excluded.resolution,quantity_override=excluded.quantity_override,
                      rationale=excluded.rationale,evidence=excluded.evidence,effective_date=excluded.effective_date,decided_at=now()
                """, [decision_id(batch_id, application_id), batch_id, application_id,
                      "Compras e vendas liquidadas se anulam; o agregado da aplicação no Fin1 está obsoleto.",
                      json.dumps(evidence),effective_date])

            application_id = 316
            row = db.execute("""
                SELECT p.asset_name,p.class_name,q.legacy_quantity,q.all_settled_quantity,
                       count(*) FILTER (WHERE d.source_quantity=0),count(*),max(d.settlement_date)
                FROM portfolio.quantity_check q JOIN portfolio.position p
                  ON p.batch_id=q.batch_id AND p.legacy_id=q.application_id
                JOIN portfolio.quantity_detail d
                  ON d.batch_id=q.batch_id AND d.application_id=q.application_id
                WHERE q.batch_id=? AND q.application_id=?
                GROUP BY ALL
            """, [batch_id, application_id]).fetchone()
            if (not row or row[1] != "Caixa" or row[2] != 1000 or row[3] != 0
                    or row[4] != row[5] or row[5] != 5 or str(row[6]) != '2025-05-08'):
                raise ValueError(f"Evidence changed for application 316: {row}")
            latest_payload=json.loads(db.execute("""SELECT s.payload FROM portfolio.movement m
                JOIN source_record s ON s.record_id=m.source_record_id
                WHERE m.batch_id=? AND m.application_id=?
                ORDER BY m.settlement_date DESC,m.legacy_id DESC LIMIT 1""",
                [batch_id,application_id]).fetchone()[0])
            if latest_payload.get('em_carteira') != 0 or latest_payload.get('financeiro') != 0:
                raise ValueError(f"Latest legacy state changed for application 316: {latest_payload}")
            evidence = {"asset": row[0], "class": row[1], "legacy_quantity": str(row[2]),
                        "settled_movement_sum": str(row[3]), "zero_quantity_movements": row[4],
                        "latest_movement": str(row[6]), "latest_em_carteira": 0,
                        "latest_financeiro": "0", "latest_description": latest_payload.get('descricao')}
            db.execute("""
                INSERT INTO ledger.reconciliation_decision
                (decision_id,batch_id,subject_type,subject_id,status,resolution,quantity_override,rationale,evidence,effective_date)
                VALUES (?,?, 'application',?,'resolved','closed_position',0,?,?,?)
                ON CONFLICT (batch_id,subject_type,subject_id) DO UPDATE SET
                  status=excluded.status,resolution=excluded.resolution,
                  quantity_override=excluded.quantity_override,rationale=excluded.rationale,
                  evidence=excluded.evidence,effective_date=excluded.effective_date,decided_at=now()
            """, [decision_id(batch_id, application_id), batch_id, application_id,
                  "Controle manual de dinheiro reservado: todos os movimentos têm quantidade zero e o movimento mais recente encerra explicitamente em_carteira e financeiro; o agregado 1.000 da aplicação ficou obsoleto.",
                  json.dumps(evidence),row[6]])

            application_id = 314
            row=db.execute("""SELECT q.legacy_quantity,q.all_settled_quantity,q.movement_count,
                  max(d.settlement_date),count(*) FILTER (WHERE d.operation_name='Venda' AND d.source_value=178839.14),
                  count(*) FILTER (WHERE d.operation_name='Imposto' AND d.source_value=-1507.63)
                FROM portfolio.quantity_check q JOIN portfolio.quantity_detail d
                  ON d.batch_id=q.batch_id AND d.application_id=q.application_id
                WHERE q.batch_id=? AND q.application_id=? GROUP BY ALL""",
                [batch_id,application_id]).fetchone()
            if (not row or row[0] != row[1] or row[2] != 3 or str(row[3]) != '2025-02-25'
                    or row[4] != 1 or row[5] != 1):
                raise ValueError(f"Evidence changed for application 314: {row}")
            latest_payload=json.loads(db.execute("""SELECT s.payload FROM portfolio.movement m
                JOIN source_record s ON s.record_id=m.source_record_id
                WHERE m.batch_id=? AND m.application_id=? AND m.operation_id=2
                ORDER BY m.settlement_date DESC,m.legacy_id DESC LIMIT 1""",
                [batch_id,application_id]).fetchone()[0])
            if (latest_payload.get('em_carteira') != 0 or latest_payload.get('financeiro') != 0):
                raise ValueError(f"Latest legacy state changed for application 314: {latest_payload}")
            evidence={"legacy_quantity":str(row[0]),"redemption_date":str(row[3]),
                      "redemption_value":"178839.14","withholding_tax":"1507.63",
                      "latest_em_carteira":0,"latest_financeiro":"0",
                      "source":latest_payload.get('obs')}
            db.execute("""INSERT INTO ledger.reconciliation_decision
                (decision_id,batch_id,subject_type,subject_id,status,resolution,quantity_override,rationale,evidence,effective_date)
                VALUES (?,?,'application',?,'resolved','closed_position',0,?,?,?)
                ON CONFLICT (batch_id,subject_type,subject_id) DO UPDATE SET
                  status=excluded.status,resolution=excluded.resolution,
                  quantity_override=excluded.quantity_override,rationale=excluded.rationale,
                  evidence=excluded.evidence,effective_date=excluded.effective_date,decided_at=now()""",
                [decision_id(batch_id,application_id),batch_id,application_id,
                 "Resgate integral importado do extrato XP em 25/02/2025; o evento omite a quantidade vendida, mas encerra explicitamente em_carteira e financeiro e possui o IRRF correspondente.",
                 json.dumps(evidence,ensure_ascii=False),row[3]])
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
