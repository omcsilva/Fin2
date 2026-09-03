"""Record reviewed final-import cash decisions without rewriting Fin1 data."""

import argparse
import hashlib
import json
from pathlib import Path
from decimal import Decimal

from warehouse.database import connect, migrate


def identifier(batch, subject_type, subject_id):
    return hashlib.sha256(f"{batch}:{subject_type}:{subject_id}".encode()).hexdigest()


def put(db, batch, kind, subject, status, resolution, amount, rationale, evidence):
    db.execute("""
      INSERT INTO ledger.reconciliation_decision
      (decision_id,batch_id,subject_type,subject_id,status,resolution,quantity_override,
       rationale,evidence,amount_override)
      VALUES (?,?,?,?,?,?,NULL,?,?,?)
      ON CONFLICT (batch_id,subject_type,subject_id) DO UPDATE SET
        status=excluded.status,resolution=excluded.resolution,
        quantity_override=excluded.quantity_override,rationale=excluded.rationale,
        evidence=excluded.evidence,amount_override=excluded.amount_override,
        decided_at=now()
    """, [identifier(batch,kind,subject),batch,kind,subject,status,resolution,rationale,
          json.dumps(evidence,ensure_ascii=False),amount])


def apply(database, batch):
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        if not db.execute("SELECT 1 FROM import_batch WHERE batch_id=?",[batch]).fetchone():
            raise ValueError("Unknown import batch")
        db.execute("BEGIN")
        try:
            for account in (1,5,8):
                row=db.execute("select legacy_balance,entry_count,reconstructed_balance from ledger.cash_account_reconciliation where batch_id=? and account_id=?",[batch,account]).fetchone()
                if row != (None,0,0): raise ValueError(f"Evidence changed for empty account {account}: {row}")
                put(db,batch,'account',account,'resolved','empty_account',0,
                    'Conta sem lançamentos; saldo operacional canônico zero, preservando saldo legado ausente.',
                    {'legacy_balance':None,'entry_count':0})
            for account,entries,expected_running_mismatches in ((2,132,4),(6,239,0)):
                row=db.execute("select legacy_balance,entry_count,reconstructed_balance,running_mismatch_count from ledger.cash_account_reconciliation where batch_id=? and account_id=?",[batch,account]).fetchone()
                if row != (0,entries,0,expected_running_mismatches): raise ValueError(f"Evidence changed for closed account {account}: {row}")
                put(db,batch,'account',account,'resolved','closed_account',0,
                    'Os valores importados já possuem sinal; sua soma e todos os acumulados coincidem com saldo zero.',
                    {'legacy_balance':'0','entry_count':entries,'source_value_sum':'0','running_mismatches':expected_running_mismatches})
            account=13
            row=db.execute("select legacy_balance,entry_count,reconstructed_balance,running_mismatch_count from ledger.cash_account_reconciliation where batch_id=? and account_id=?",[batch,account]).fetchone()
            if row != (0,14,Decimal('12666.49'),0): raise ValueError(f"Evidence changed for account 13: {row}")
            statement_paths=[
                'ANEXOS/APXMC/202307_APEX Marcos.pdf','ANEXOS/APXMC/202308_APEX Marcos.pdf',
                'ANEXOS/APXMC/202309_APEX Marcos.pdf','ANEXOS/APXMC/202311_APEX Marcos.pdf',
                'ANEXOS/APXMC/202312_APEX Marcos.pdf','ANEXOS/APXMC/202401_APEX Marcos.pdf',
                'ANEXOS/APXMC/202402_APEX Marcos.pdf']
            account_record=db.execute("select source_record_id from portfolio.account where batch_id=? and legacy_id=13",[batch]).fetchone()[0]
            documents=db.execute("select document_id,source_path from source_document where batch_id=? and source_path in (select unnest(?)) order by source_path",[batch,statement_paths]).fetchall()
            if len(documents)!=len(statement_paths): raise ValueError(f"Missing APEX statements: {documents}")
            for document_id,_ in documents:
                db.execute("insert into document_record_link values (?,?,?) on conflict do nothing",[document_id,account_record,'account_statement'])
            put(db,batch,'account',account,'pending','incomplete_statement_history',None,
                'O histórico do Fin1 soma 12.666,49, mas o extrato APEX de fevereiro de 2024 fecha o caixa em 42.876,79; não há eventos suficientes para derivar o saldo.',
                {'legacy_balance':'0','entry_count':14,'source_value_sum':'12666.49','running_mismatches':0,
                 'latest_statement':'ANEXOS/APXMC/202402_APEX Marcos.pdf','statement_closing_cash':'42876.79'})
            for entry,duplicate in ((941,945),(942,946),(943,947),(944,948)):
                row=db.execute("select account_id,source_value,description from portfolio.cash_detail where batch_id=? and legacy_id=?",[batch,entry]).fetchone()
                if not row or row[0] is not None: raise ValueError(f"Evidence changed for orphan entry {entry}: {row}")
                other=db.execute("select account_id,source_value,description,settlement_date from portfolio.cash_detail where batch_id=? and legacy_id=?",[batch,duplicate]).fetchone()
                original_date=db.execute("select settlement_date from portfolio.cash_detail where batch_id=? and legacy_id=?",[batch,entry]).fetchone()[0]
                if other != (4,row[1],row[2],original_date): raise ValueError(f"Duplicate evidence changed for {entry}/{duplicate}: {other}")
                put(db,batch,'cash_entry',entry,'resolved','duplicate_source_row',None,
                    'Cópia sem conta e com indicador de crédito incorreto; a linha equivalente associada à conta 4 é mantida.',
                    {'source_value':str(row[1]),'description':row[2],'retained_legacy_id':duplicate,'retained_account_id':4})
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK"); raise
        return dict(db.execute("select status,count(*) from ledger.reconciliation_decision where batch_id=? group by status",[batch]).fetchall())


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database',type=Path,required=True);p.add_argument('--batch',required=True)
    a=p.parse_args();print(json.dumps(apply(a.database,a.batch),ensure_ascii=False))


if __name__=='__main__': main()
