"""Consolidated investor counterparty, with currencies kept separate."""

from decimal import Decimal

from warehouse.repositories.dashboard import query


def investment_balances(connection, batch, cutoff):
    return query(connection, """SELECT e.account_source_record_id,a.name,e.currency,
        sum(e.amount) cash_value,count(*) FILTER(WHERE e.amount IS NULL) pending
        FROM ledger.investment_cash_entry e
        JOIN portfolio.account a ON a.source_record_id=e.account_source_record_id
        WHERE e.batch_id=? AND e.settlement_date<=?
        GROUP BY e.account_source_record_id,a.name,e.currency ORDER BY a.name,e.currency""",
        [batch,cutoff])


def summarize(connection, batch, cutoff, positions, cash_balances=()):
    aliases = {'REAL': 'BRL', 'DOL': 'USD', 'DOLAR': 'USD'}
    rows = {}

    def bucket(currency):
        currency = (currency or '').strip().upper()
        currency = aliases.get(currency, currency)
        return rows.setdefault(currency, dict(currency=currency, invested=Decimal(0),
            withdrawn=Decimal(0), current_value=Decimal(0), cash_value=Decimal(0), pending=0, stale=0))

    for entry in query(connection, """SELECT currency, amount, category, settlement_date
        FROM ledger.result_account_entry WHERE batch_id=?
        AND (settlement_date<=? OR settlement_date IS NULL)
        AND (reversed_at IS NULL OR reversed_at>?)""", [batch, cutoff, cutoff]):
        row = bucket(entry['currency'])
        amount = entry['amount']
        if entry['settlement_date'] is None or amount is None:
            row['pending'] += 1
        elif entry['category'] == 'external_contribution' and amount >= 0:
            row['invested'] += amount
        elif entry['category'] == 'external_withdrawal' and amount <= 0:
            row['withdrawn'] -= amount
        else:
            row['pending'] += 1
    for position in positions:
        row = bucket(position['currency'])
        status = position['valuation_status']
        if status == 'closed':
            continue
        if status in ('priced', 'stale_price') and position['reference_value'] is not None:
            row['current_value'] += position['reference_value']
            row['stale'] += status == 'stale_price'
        else:
            row['pending'] += 1
    for cash in cash_balances:
        row = bucket(cash['currency'])
        row['cash_value'] += cash['cash_value'] or Decimal(0)
        row['pending'] += cash['pending']
    for row in rows.values():
        if row['cash_value'] < 0:
            row['pending'] += 1
        row['investment_value'] = row['current_value'] + row['cash_value']
        row['result'] = (row['withdrawn'] + row['investment_value'] - row['invested']
                         if not row['pending'] and row['currency'] else None)
    return sorted(rows.values(), key=lambda row: row['currency'])
