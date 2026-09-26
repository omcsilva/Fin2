"""Audited XP evidence, account bindings and atomic financial decisions."""
from datetime import date, datetime, timedelta
from decimal import Decimal
import hashlib
import json
import re
from pathlib import Path
from uuid import uuid4

from warehouse.database import connect, migrate
from fin2.imports.xp_statement import extract, plain


def records(db, sql, args=()):
    cursor = db.execute(sql, args)
    return [dict(zip([c[0] for c in cursor.description], row)) for row in cursor.fetchall()]


def accounts(db):
    return records(db, """select a.*, i.name holder, c.abbreviation currency,
      inst.name institution from portfolio.account a
      left join portfolio.investor i on i.batch_id=a.batch_id and i.legacy_id=a.investor_id
      left join portfolio.currency c on c.batch_id=a.batch_id and c.legacy_id=a.currency_id
      left join portfolio.institution inst on inst.batch_id=a.batch_id and inst.legacy_id=a.institution_id
      order by i.name,a.name""")


def account(db, identifier):
    found = next((a for a in accounts(db) if a['source_record_id'] == identifier), None)
    if not found or found['currency'] not in ('BRL', 'REAL'):
        raise ValueError('Selecione uma conta cadastrada em BRL')
    return found


def applications(db, identifier):
    return records(db, """select ap.source_record_id, ap.name, upper(a.symbol) symbol,
      a.name asset_name, a.cnpj, a.issuer,
      a.statement_aliases asset_aliases,
      ap.statement_aliases app_aliases
      from portfolio.application ap join portfolio.account c on c.batch_id=ap.batch_id and c.legacy_id=ap.account_id
      left join portfolio.asset a on a.batch_id=ap.batch_id and a.legacy_id=ap.asset_id
      where c.source_record_id=? order by ap.name""", [identifier])


def attachment_documents(db, import_id):
    """Return documents staged as evidence for this statement import."""
    return records(db, """select f.import_id attachment_import_id,
            f.original_filename,f.document_type,f.row_count,f.error_count,f.status,
            f.document_id, s.account_record
            from ledger.import_attachment x
            join ledger.file_import f on f.import_id=x.attachment_import_id
            left join ledger.xp_statement s on s.import_id=x.parent_import_id
            where x.parent_import_id=? order by f.created_at""", [import_id])


def attachment_rows(db, import_id):
    """Return normalized rows from each staged attachment, grouped by document."""
    documents = attachment_documents(db, import_id)
    result = {}
    for document in documents:
        rows = records(db, """select normalized from ledger.import_staging_line
          where import_id=? order by row_number""", [document['attachment_import_id']])
        result[document['document_id']] = [
            {**json.loads(row['normalized']),
             'document_name': document['original_filename']}
            for row in rows]
    return result


def _selected_attachment_rows(db, item, document_id):
    documents = {row['document_id']: row for row in attachment_documents(
        db, item['import_id'])}
    document = documents.get(document_id)
    if not document:
        raise ValueError('Documento complementar não pertence a este extrato')
    return [json.loads(row['normalized']) for row in records(
        db, """select normalized from ledger.import_staging_line
        where import_id=? and state<>'rejected' order by row_number""",
        [document['attachment_import_id']])]


def entries(db, identifier):
    # Canonical cash only: no second copy from investment movements.
    return records(db, """select e.cash_entry_id entry_id,e.settlement_date,e.signed_amount amount,
      e.description,'fin1' origin,NULL::VARCHAR application_record,
      (select list(distinct m.trade_date) from portfolio.movement m
       where m.batch_id=e.batch_id and m.cash_entry_id=e.legacy_id) trade_dates
      from ledger.cash_entry_canonical e join portfolio.account a on a.batch_id=e.batch_id and a.legacy_id=e.account_id
      where a.source_record_id=? and not exists (select 1 from ledger.reconciliation_decision d
        where d.batch_id=e.batch_id and d.subject_type='cash_entry' and d.subject_id=e.legacy_id and d.resolution='duplicate_source_row')
      union all select m.event_id,m.settlement_date,m.amount,m.description,'manual',m.application_source_record_id,[m.trade_date]
      from ledger.manual_event m where m.account_source_record_id=? and m.reverses_event_id is null
      and not exists(select 1 from ledger.manual_event r where r.reverses_event_id=m.event_id)
      and not exists(select 1 from ledger.manual_transfer t join ledger.manual_transfer r on r.reverses_transfer_id=t.transfer_id
        where t.transfer_id=m.transfer_id or r.transfer_id=m.transfer_id)""", [identifier, identifier])


def _dates_match(entry, row):
    dates = {str(value) for value in (entry.get('trade_dates') or []) if value is not None}
    if entry.get('settlement_date') is not None:
        dates.add(str(entry['settlement_date']))
    return bool(dates & {row.get('trade_date'), row.get('settlement_date')})


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10]) if value else None


def _ledger_entries_for_row(available, row):
    trade_date = _as_date(row.get('trade_date'))
    settlement_date = _as_date(row.get('settlement_date'))
    if not trade_date or not settlement_date:
        return [], None, None
    start = trade_date - timedelta(days=21)
    end = settlement_date + timedelta(days=21)
    result = []
    for entry in available:
        entry_dates = [_as_date(value)
                       for value in (entry.get('trade_dates') or [])]
        entry_dates.append(_as_date(entry.get('settlement_date')))
        if any(value and start <= value <= end for value in entry_dates):
            result.append(entry)
    return result, start, end


def _extract_asset_hint(description):
    """Strip XP category prefixes and auxiliary fragments from a statement description,
    returning the residual tokens that identify the underlying asset or fund."""
    text = plain(description)
    for prefix in (
        'JUROS S/ CAPITAL PROPRIO', 'JUROS S/ CAPITAL',
        'DIVIDENDOS', 'RENDIMENTOS', 'IRRF S/RESGATE', 'RESGATE',
        'APLICACAO PREVIDENCIA', 'OPERACOES EM BOLSA',
        'TRANSFERENCIA', 'TED ',
    ):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    text = re.sub(r'\bS/\d[\d.,]*\b', '', text)              # income base: S/100
    text = re.sub(r'\s*-\s*(PN|ON|UNT|CI|ED)\b', '', text)   # share class suffix
    text = re.sub(r'\bNOTA\s*N[OoºO.]?\s*\d+\b', '', text)   # brokerage note ref
    return ' '.join(text.split())


def _match_aliases(alias_string, description_plain):
    """Return True if any pipe-separated alias occurs in the normalised description."""
    if not alias_string:
        return False
    return any(
        plain(alias) in description_plain
        for alias in str(alias_string).split('|')
        if alias.strip()
    )


def _resolve_unique(candidates):
    """Return the single source_record_id if exactly one candidate, else None."""
    ids = {a['source_record_id'] for a in candidates}
    return next(iter(ids)) if len(ids) == 1 else None


def identify_application(row, apps):
    """Cascade match a statement row against the account's applications.

    Returns (source_record_id, method) or (None, None) when ambiguous.

    Cascade order (most-to-least reliable):
      1. exact_symbol  — ticker regex matches app.symbol
      2. cnpj          — 14-digit CNPJ in description matches app.cnpj
      3. alias         — app.asset_aliases or app.app_aliases substring match
      4. asset_name    — residual hint tokens match app.asset_name
      5. app_name      — residual hint tokens match app.name
      6. issuer        — issuer tokens appear in description
    """
    if not apps:
        return None, None

    desc_plain = plain(row.get('description', ''))

    # Step 1: ticker symbol
    symbol = row.get('symbol')
    if symbol:
        matches = [a for a in apps if a.get('symbol') == symbol]
        result = _resolve_unique(matches)
        if result:
            return result, 'exact_symbol'

    # Step 2: CNPJ (14 digits, with or without formatting)
    cnpj_match = re.search(r'\d{2}[.\-]?\d{3}[.\-]?\d{3}[/]?\d{4}[-]?\d{2}', row.get('description', ''))
    if cnpj_match:
        raw_cnpj = re.sub(r'[./-]', '', cnpj_match.group())
        if len(raw_cnpj) == 14:
            matches = [a for a in apps if a.get('cnpj') and re.sub(r'[./-]', '', a['cnpj']) == raw_cnpj]
            result = _resolve_unique(matches)
            if result:
                return result, 'cnpj'

    # Step 3: statement aliases (asset or application)
    matches = [a for a in apps
               if _match_aliases(a.get('asset_aliases'), desc_plain)
               or _match_aliases(a.get('app_aliases'), desc_plain)]
    result = _resolve_unique(matches)
    if result:
        return result, 'alias'

    # Steps 4 & 5: name-based matching using residual hint from description
    hint = _extract_asset_hint(row.get('description', ''))
    if hint:
        # Step 4: asset name
        matches = [a for a in apps if a.get('asset_name') and plain(a['asset_name']) and hint in plain(a['asset_name'])]
        result = _resolve_unique(matches)
        if result:
            return result, 'asset_name'

        # Step 5: application name
        matches = [a for a in apps if a.get('name') and hint in plain(a['name'])]
        result = _resolve_unique(matches)
        if result:
            return result, 'app_name'

    # Step 6: issuer tokens
    matches = [a for a in apps
               if a.get('issuer') and plain(a['issuer']) and plain(a['issuer']) in desc_plain]
    result = _resolve_unique(matches)
    if result:
        return result, 'issuer'

    return None, None


def _load(db, identifier, mutable=False):
    result = records(db, """select f.*,s.account_record,s.documented_at,s.financial_status
      from ledger.file_import f join ledger.xp_statement s using(import_id) where import_id=?""", [identifier])
    if not result or (mutable and (result[0]['status'] != 'preview' or result[0]['financial_status'] == 'confirmed')):
        raise ValueError('Extrato indisponível para revisão')
    item = result[0]
    item['document_metadata'] = json.loads(item['document_metadata'])
    item['rows'] = []
    for row in records(db, 'select * from ledger.xp_statement_line where import_id=? order by line_number', [identifier]):
        raw = json.loads(row['raw'])
        raw.update(row_number=row['line_number'], decision=json.loads(row['decision']) if row['decision'] else None)
        item['rows'].append(raw)
    return item


def stage(database, storage_root, filename, body, media_type, options):
    metadata, sources = extract(body)
    digest = hashlib.sha256(body).hexdigest()
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        selected = account(db, options.get('account_record'))
        if selected['institution'] and not re.search(r'\bXP\b', plain(selected['institution'])):
            raise ValueError('A instituição da conta selecionada não é XP')
        named_number = re.search(r'\b(\d{4,}[.\d]*-?\d*)\b', selected['name'] or '')
        if named_number and (re.sub(r'\D', '', named_number[1]).lstrip('0') or '0') != metadata['account_number']:
            raise ValueError('Número XP diverge do número no cadastro da conta')
        binding = db.execute('select account_record,holder from ledger.xp_account_binding where account_number=?', [metadata['account_number']]).fetchone()
        if binding and (binding[0] != selected['source_record_id'] or plain(binding[1]) != plain(metadata['holder'])):
            raise ValueError('Número XP ou titular diverge da associação já registrada')
        # Catalogs may use a short display name (Marcos/Luciana); every
        # display-name token must still match the holder in the statement.
        if not selected['holder'] or not set(plain(selected['holder']).split()).issubset(set(plain(metadata['holder']).split())):
            raise ValueError(
                'Titular do extrato difere do titular cadastrado; corrija o cadastro antes de associar')
        if not binding:
            if db.execute('select 1 from ledger.xp_account_binding where account_record=?', [selected['source_record_id']]).fetchone():
                raise ValueError('Conta cadastrada já associada a outro número XP')
            if not options.get('confirm_identity'):
                raise ValueError('Confirme o número e o titular do extrato antes da primeira associação')
            identity_reason = ' '.join(str(options.get('identity_reason', '')).split())
            if not 5 <= len(identity_reason) <= 500:
                raise ValueError('Informe justificativa de 5 a 500 caracteres para associar a conta XP')
        existing = db.execute('select import_id,status from ledger.file_import where sha256=?', [digest]).fetchone()
        if existing:
            return existing
        identifier = uuid4().hex
        document_id = hashlib.sha256(f"{selected['batch_id']}:file-import:{digest}".encode()).hexdigest()
        root = Path(storage_root).resolve()
        target = root / 'imports' / digest[:2] / digest
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        preview = [dict(s.values, row_number=s.locator['item'], source_locator=s.locator,
                        account_record=selected['source_record_id'], account=selected['name']) for s in sources]
        db.execute('BEGIN')
        try:
            if not binding:
                db.execute('insert into ledger.xp_account_binding(account_number,account_record,holder,reason) values (?,?,?,?)',
                           [metadata['account_number'], selected['source_record_id'], metadata['holder'], identity_reason])
            db.execute('''insert into source_document(document_id,batch_id,source_path,original_filename,sha256,byte_size,storage_key)
              values (?,?,?,?,?,?,?)''', [document_id, selected['batch_id'], f'FIN2/imports/{digest}/{Path(filename).name}',
                                        Path(filename).name, digest, len(body), target.relative_to(root).as_posix()])
            db.execute('insert into document_record_link(document_id,record_id,relation) values (?,?,?)',
                       [document_id, selected['source_record_id'], 'account_statement'])
            db.execute('''insert into ledger.file_import(import_id,sha256,original_filename,storage_key,media_type,status,
              row_count,error_count,preview,byte_size,adapter_id,adapter_version,document_type,detection_confidence,batch_id,document_id,document_metadata)
              values (?,?,?,?,?,'preview',?,?,?,?,'xp-account-statement','1','account_statement',99,?,?,?)''',
                       [identifier, digest, Path(filename).name, target.relative_to(root).as_posix(), media_type,
                        len(preview), sum(bool(r['errors']) for r in preview), json.dumps(preview), len(body),
                        selected['batch_id'], document_id, json.dumps(metadata)])
            db.execute('insert into ledger.xp_statement(import_id,account_record) values (?,?)', [identifier, selected['source_record_id']])
            for row in preview:
                db.execute('insert into ledger.xp_statement_line(import_id,line_number,fingerprint,raw) values (?,?,?,?)',
                           [identifier, row['row_number'], row['fingerprint'], json.dumps(row)])
            from fin2.imports.staging import seed
            seed(db, identifier, preview)
            db.execute('COMMIT')
        except Exception:
            db.execute('ROLLBACK')
            raise
    return identifier, 'preview'


def detail(db, identifier):
    item = _load(db, identifier)
    available = entries(db, item['account_record'])
    apps = applications(db, item['account_record'])
    item['attachment_documents'] = attachment_documents(db, identifier)
    projected_by_document = attachment_rows(db, identifier)
    counts = {'new': 0, 'linked': 0, 'pending': 0, 'divergent': 0, 'excluded': 0}
    # Review state per row: ready = resolved, pending = still needs information,
    # excluded = the reviewer dropped the line from the load.
    states = {state: 0 for state in REVIEW_STATES}
    reserved = set()
    for row in item['rows']:
        row['candidates'] = [dict(e, label=f"{e['origin']} · {e['description']} · {e['amount']} · Liquidação {e['settlement_date']}") for e in available
                             if _dates_match(e, row)]
        row['ledger_entries'], row['ledger_period_start'], row['ledger_period_end'] = _ledger_entries_for_row(
            available, row)
        row['suggested_ids'] = [e['entry_id'] for e in row['candidates'] if e['amount'] == Decimal(row.get('amount', '0'))]
        row['applications'] = apps
        row['attachment_documents'] = item['attachment_documents']
        row['projected_events'] = projected_by_document.get(
            (row['decision'] or {}).get('document_id'), [])
        _app_id, _match_method = identify_application(row, apps)
        row['suggested_application'] = _app_id or ''
        row['match_method'] = _match_method or ''
        row['suggested_application_name'] = next(
            (a['name'] for a in apps if a['source_record_id'] == _app_id), '') if _app_id else ''
        claim = db.execute('select import_id,line_number from ledger.xp_statement_claim where account_record=? and fingerprint=?',
                           [item['account_record'], row['fingerprint']]).fetchone()
        row['prior_claim'] = claim[0] if claim and claim[0] != identifier else None
        row['situation'] = ('linked' if item['financial_status'] == 'confirmed' else 'divergent' if row['errors'] else 'linked' if row['prior_claim'] else
                            row['decision']['action'] if row['decision'] else 'pending')
        if row['situation'] == 'link': row['situation'] = 'linked'
        counts[row['situation']] += 1
        # The reviewer's decision wins. Without one, the system identifies what
        # the statement and the ledger allow, and leaves a hint when the data is
        # not enough to record the line.
        decision = row['decision']
        if decision:
            row['identified'], row['identification_missing'], complete = None, [], False
            reserved.update(decision.get('entry_ids') or [])
        else:
            row['identified'], row['identification_missing'], complete = _identify(db, item, row, available, apps, reserved)
            if complete:
                reserved.update(row['identified'].get('entry_ids') or [])
        effective = decision or row['identified']
        row['effective_application'] = (effective or {}).get('application_record') or ''
        row['effective_quantity'] = (effective or {}).get('quantity')
        row['effective_application_name'] = next(
            (a['name'] for a in apps if a['source_record_id'] == row['effective_application']), '')
        action = (effective or {}).get('action')
        row['state'] = ('excluded' if action == 'excluded' else
                        'ready' if action in ('new', 'link') and not row['errors'] and bool(decision or complete) else 'pending')
        states[row['state']] += 1
    item['created_count'] = db.execute("select count(*) from ledger.audit_log where entity_type='manual_event' and action='create' and json_extract_string(payload,'$.import_id')=?", [identifier]).fetchone()[0]
    item['counts'] = counts
    item['states'] = states
    item['decision_history'] = records(db, 'select line_number,payload,created_at from ledger.xp_statement_decision where import_id=? order by created_at desc', [identifier])
    history_by_line = {}
    for history in item['decision_history']:
        history['payload'] = json.loads(history['payload'])
        history['action_label'] = ACTION_LABELS.get(history['payload'].get('action'), history['payload'].get('action') or '')
        history_by_line.setdefault(history['line_number'], []).append(history)
    # Each row carries only its own revisions; the modal shows them expanded.
    for row in item['rows']:
        row['history'] = history_by_line.get(row['row_number'], [])
    metadata = item['document_metadata']
    for boundary, operator, date in (('opening', '<', metadata['period_start']), ('closing', '<=', metadata['period_end'])):
        value = db.execute(f'''select coalesce(sum(amount),0) from ledger.investment_cash_entry
          where account_source_record_id=? and settlement_date {operator} ?''', [item['account_record'], date]).fetchone()[0]
        metadata[f'ledger_{boundary}'] = str(value)
        metadata[f'{boundary}_difference'] = str(Decimal(metadata[f'{boundary}_balance']) - value) if metadata.get(f'{boundary}_balance') else None
    item['can_confirm'] = not metadata['errors'] and states['pending'] == 0 and item['status'] == 'preview'
    # The save button is only usable while there is something ready to record.
    item['can_commit'] = not metadata['errors'] and states['ready'] > 0 and item['status'] == 'preview'
    item['redemption_lines'] = [r for r in item['rows'] if r['category'] == 'redemption']
    item['transfer_accounts'] = [a for a in accounts(db) if a['source_record_id'] != item['account_record']]
    item['category_options'] = CATEGORY_OPTIONS
    return item


# Statement categories and the ledger event each one produces. The reviewer can
# replace the extracted category, and the event type follows from it.
CATEGORY_EVENT = {
    'jcp': 'income', 'dividend': 'income', 'income': 'income',
    'transfer': 'transfer', 'redemption_tax': 'tax',
    'redemption': 'redemption', 'pension': 'buy',
}
# Review states of a statement line, in the order the reviewer sees them.
REVIEW_STATES = ('ready', 'pending', 'excluded')
# Reviewer actions, as shown in the revision history of a line.
ACTION_LABELS = {
    'new': 'Lançamento novo',
    'link': 'Vínculo a movimento existente',
    'excluded': 'Excluído do ledger',
    'pending': 'Pendente',
}
CATEGORY_OPTIONS = (
    ('jcp', 'JCP'),
    ('dividend', 'Dividendo'),
    ('income', 'Rendimento'),
    ('brokerage', 'Operações em bolsa'),
    ('transfer', 'Transferência / movimentação'),
    ('redemption_tax', 'IRRF sobre resgate'),
    ('redemption', 'Resgate'),
    ('pension', 'Previdência (aplicação)'),
)


def category_label(value):
    """Category wording shown to the reviewer, never the internal slug."""
    return dict(CATEGORY_OPTIONS).get(value, value or '')


# Wording of the ledger entry each event type produces, shown before confirming.
EVENT_LABELS = {
    'income': 'Provento / rendimento',
    'transfer': 'Transferência entre contas próprias',
    'deposit': 'Aporte externo',
    'withdrawal': 'Retirada externa',
    'tax': 'Imposto do resgate',
    'redemption': 'Resgate documentado',
    'buy': 'Aplicação em previdência documentada',
}


def _validate(db, item, row, decision, used):
    if decision['action'] == 'excluded':
        # The reviewer dropped this line from the load; nothing is written for it.
        return
    if row['errors']:
        raise ValueError('Linha com erro de extração não pode ser confirmada')
    if (row.get('category') == 'brokerage' and decision['action'] == 'new'
            and decision.get('category') != 'brokerage'):
        raise ValueError(
            'Categoria exige vínculo com movimentos existentes ou documento detalhado; não gere operação pelo saldo líquido')
    if row.get('category') == 'brokerage' and decision['action'] == 'new':
        if decision.get('document_id') and db.execute(
            """select 1 from ledger.xp_statement_line
               where import_id=? and line_number<>? and
                 json_extract_string(decision,'$.document_id')=?""",
                [item['import_id'], row['row_number'], decision['document_id']]).fetchone():
            raise ValueError(
                'O documento já está associado a outra linha deste extrato')
        projected = _selected_attachment_rows(
            db, item, decision.get('document_id'))
        if not projected or any(projected_row.get('errors') for projected_row in projected):
            raise ValueError(
                'A nota associada possui linhas que precisam de revisão')
        apps = {a['source_record_id']
                for a in applications(db, item['account_record'])}
        total = Decimal('0')
        for projected_row in projected:
            event_type = projected_row.get('event_type')
            amount = Decimal(projected_row.get('amount', '0'))
            if projected_row.get('account_record') != item['account_record']:
                raise ValueError('A nota possui operação de outra conta')
            if event_type not in {'buy', 'sell', 'fee', 'tax'} or not projected_row.get('settlement_date'):
                raise ValueError('A nota possui operação financeira inválida')
            if event_type in {'buy', 'sell'}:
                if projected_row.get('application_record') not in apps or not projected_row.get('quantity'):
                    raise ValueError(
                        'A nota possui operação sem aplicação ou quantidade')
                if Decimal(projected_row['quantity']) <= 0:
                    raise ValueError('A nota possui quantidade inválida')
            if amount == 0 or (event_type == 'buy' and amount >= 0) or (event_type in {'sell'} and amount <= 0):
                raise ValueError('A nota possui sinal financeiro incompatível')
            total += amount
        if total != Decimal(row['amount']):
            raise ValueError(
                'O total líquido da nota difere do valor do extrato')
        return
    available = {e['entry_id']: e for e in entries(db, item['account_record'])}
    if decision['action'] == 'link':
        ids = decision.get('entry_ids', [])
        if not ids or len(ids) != len(set(ids)) or any(i not in available for i in ids):
            raise ValueError('Selecione movimentos existentes válidos desta conta')
        selected = [available[i] for i in ids]
        if any(not _dates_match(e, row) for e in selected):
            raise ValueError('Movimentos selecionados não correspondem à movimentação ou liquidação')
        if sum(e['amount'] for e in selected) != Decimal(row['amount']):
            raise ValueError('A soma dos movimentos selecionados difere do valor do extrato')
        for identifier in ids:
            if identifier in used:
                raise ValueError('Mesmo movimento usado por duas linhas distintas')
            # Read from the claim, not the line: the review staging is discarded
            # when the load concludes, and this check still has to hold.
            other = db.execute('''select c.fingerprint from ledger.xp_statement_link l
              join ledger.xp_statement_claim c on c.import_id=l.import_id and c.line_number=l.line_number
              where l.entry_id=?''', [identifier]).fetchall()
            if any(fingerprint != row['fingerprint'] for (fingerprint,) in other):
                raise ValueError('Movimento já conciliado com outra linha; revise possível reexportação divergente')
            used.add(identifier)
        return
    if decision['action'] != 'new':
        raise ValueError('Decisão pendente')
    kind = decision.get('category') or row['category']
    allowed = {'jcp': {'income'}, 'dividend': {'income'}, 'income': {'income'},
               'transfer': {'deposit','withdrawal','transfer'}, 'redemption_tax': {'tax'},
               'redemption': {'redemption'}, 'pension': {'buy'}}
    event_type = decision.get('event_type')
    if event_type == 'transfer' and decision.get('counterparty') == 'RESULTADO':
        amount = Decimal(row['amount'])
        event_type = 'deposit' if amount > 0 else 'withdrawal'
        decision['event_type'] = event_type
        decision['counterparty'] = None

    if event_type not in allowed.get(kind, set()):
        raise ValueError('Categoria exige vínculo com registros existentes ou documento detalhado; não gere operação pelo saldo líquido')
    amount = Decimal(row['amount'])
    if amount == 0 or (event_type in {'income','deposit','redemption'} and amount < 0) or (event_type in {'tax','withdrawal','buy'} and amount > 0):
        raise ValueError('Sinal incompatível com o tipo escolhido')
    apps = {a['source_record_id']: a for a in applications(db, item['account_record'])}
    if event_type in {'income','tax','redemption','buy'}:
        if decision.get('application_record') not in apps:
            raise ValueError('Selecione uma aplicação desta conta')
        if row.get('symbol') and apps[decision['application_record']]['symbol'] != row['symbol']:
            raise ValueError('Ativo selecionado diverge do provento')
    if event_type not in {'buy','redemption'} and decision.get('quantity'):
        raise ValueError('Quantidade só se aplica a resgate/previdência')
    if decision.get('document_id'):
        valid_documents = {document['document_id']
                           for document in attachment_documents(db, item['import_id'])}
        if decision['document_id'] not in valid_documents:
            raise ValueError(
                'Documento complementar não pertence a este extrato')
    if event_type in {'deposit','withdrawal','transfer'} and decision.get('application_record'):
        decision['application_record'] = None
    if event_type in {'buy', 'redemption'} and decision.get('quantity'):
        try:
            qty = Decimal(str(decision.get('quantity', '')))
            if not qty.is_finite() or qty <= 0: raise ValueError()
        except Exception:
            raise ValueError('Informe quantidade positiva comprovada') from None
    if event_type in {'buy', 'redemption'} and decision.get('document_id'):
        if decision['document_id'] == item['document_id']:
            raise ValueError(
                'Selecione documento complementar deste extrato que comprove produto e quantidade')
    if event_type == 'tax':
        related = next((r for r in item['rows'] if str(r['row_number']) == str(decision.get('related_line'))), None)
        if not related or related['category'] != 'redemption' or related.get('settlement_date') != row['settlement_date']:
            raise ValueError('Vincule o imposto à linha de resgate na mesma data')
    if event_type == 'transfer':
        source = account(db, item['account_record'])
        destination = account(db, decision.get('counterparty'))
        if source['source_record_id'] == destination['source_record_id'] or source['batch_id'] != destination['batch_id'] or source['investor_id'] != destination['investor_id']:
            raise ValueError('Transferência própria exige outra conta BRL do mesmo titular e lote')
        # If the other side already exists, link/complete it outside this batch instead of duplicating it.
        if any(str(e['settlement_date']) == row['settlement_date'] and e['amount'] == -amount for e in entries(db, destination['source_record_id'])):
            raise ValueError('Contraparte já possui movimento compatível; concilie a transferência existente antes de confirmar')
    # A reviewer can distinguish genuine equal movements, but must explicitly acknowledge the candidates.
    suspects = [e['entry_id'] for e in available.values() if _dates_match(e, row) and e['amount'] == amount]
    if suspects and (not decision.get('distinct_confirmed') or sorted(suspects) != decision.get('reviewed_entries')):
        raise ValueError('Há movimentos de mesma data e valor. Vincule-os ou confirme que esta é uma ocorrência distinta')
    # Changes to already confirmed reexports never become silent new movements.
    # The claim outlives the review staging and carries the line evidence.
    for existing in records(db, '''select fingerprint,description,settlement_date from ledger.xp_statement_claim
      where account_record=? and description is not null''', [item['account_record']]):
        if (existing['fingerprint'] != row['fingerprint']
                and existing['settlement_date'] == row.get('settlement_date')
                and plain(existing['description']) == plain(row.get('description', ''))):
            if not decision.get('distinct_confirmed'):
                raise ValueError('Extrato sobreposto contém lançamento semelhante ou alterado; revise e justifique ocorrência distinta')


def _apply_category(decision):
    """Fill the event type (and the fixed counterparty) from the chosen category.

    Returns False when the category has no ledger event of its own.
    """
    event_type = CATEGORY_EVENT.get(decision.get('category'))
    if not event_type:
        return False
    decision['event_type'] = event_type
    # The counterparty of every movement is the result account; portability is
    # handled outside this review.
    if event_type == 'transfer' and not decision.get('counterparty'):
        decision['counterparty'] = 'RESULTADO'
    return True


# Short wording for the validations that are not a simple missing field.
MISSING_LABELS = {
    'Sinal incompatível com o tipo escolhido': 'Tipo do lançamento',
    'Ativo selecionado diverge do provento': 'Aplicação',
    'Documento complementar não pertence ao lote': 'Documento complementar',
    'Quantidade só se aplica a resgate/previdência': 'Quantidade',
    'Vincule o imposto à linha de resgate na mesma data': 'Resgate relacionado',
    'Há movimentos de mesma data e valor. Vincule-os ou confirme que esta é uma ocorrência distinta': 'Confirmação de ocorrência distinta',
    'Extrato sobreposto contém lançamento semelhante ou alterado; revise e justifique ocorrência distinta': 'Confirmação de ocorrência distinta',
    'Selecione movimentos existentes válidos desta conta': 'Vínculo com movimento existente',
    'Movimentos selecionados não correspondem à movimentação ou liquidação': 'Vínculo com movimento existente',
    'A soma dos movimentos selecionados difere do valor do extrato': 'Vínculo com movimento existente',
}


def _missing_items(decision):
    """Which items still have to be informed before the line can be recorded."""
    event_type = CATEGORY_EVENT.get(decision.get('category'))
    if not event_type:
        return ['Categoria']
    missing = []
    if event_type in ('income', 'tax', 'redemption', 'buy') and not decision.get('application_record'):
        missing.append('Aplicação')
    if event_type == 'tax' and not decision.get('related_line'):
        missing.append('Resgate relacionado')
    return missing


def _identify(db, item, row, available, apps, reserved):
    """Ledger decision offered for one line, from the statement and the database.

    Returns (decision, missing, complete). A complete decision can be recorded
    as it is, so the line is ready; otherwise the decision is None and `missing`
    lists, in the reviewer's words, what still has to be provided.
    """
    if row['errors']:
        return None, ['Erro de leitura da linha'], False
    dated = [e for e in available if _dates_match(e, row)]
    candidates = [e for e in dated if e['amount'] == Decimal(row['amount'])]
    exact = [e for e in candidates if plain(e['description']) == plain(row['description'])]
    if (len(candidates) == 1 and len(exact) == 1 and exact[0]['entry_id'] not in reserved
            and str(exact[0]['settlement_date']) == row['settlement_date']):
        decision = {'action': 'link', 'category': row['category'], 'entry_ids': [exact[0]['entry_id']],
                    'reviewed_entries': [],
                    'reason': 'Identificação automática: mesma conta, liquidação, valor e descrição'}
        try:
            _validate(db, item, row, decision, set(reserved))
        except ValueError as exc:
            return None, [MISSING_LABELS.get(str(exc), str(exc))], False
        return decision, [], True
    if candidates:
        return None, ['Escolha entre os movimentos existentes'], False
    app_id, match_method = identify_application(row, apps)
    decision = {'action': 'new', 'category': row['category'], 'reviewed_entries': [],
                'reason': f'Identificação automática: {match_method}' if match_method else 'Identificação automática'}
    if app_id:
        decision['application_record'] = app_id
        decision['match_method'] = match_method
    _apply_category(decision)
    if row['category'] == 'redemption_tax':
        same_date = [r for r in item['rows'] if r['category'] == 'redemption'
                     and r.get('settlement_date') == row.get('settlement_date')]
        if len(same_date) == 1:
            decision['related_line'] = same_date[0]['row_number']
    missing = _missing_items(decision)
    if missing:
        return None, missing, False
    try:
        _validate(db, item, row, decision, set(reserved))
    except ValueError as exc:
        return None, [MISSING_LABELS.get(str(exc), str(exc))], False
    return decision, [], True


def review(database, identifier, line_number, decision):
    reason = str(decision.get('reason', '')).strip()
    if len(reason) > 500:
        raise ValueError('Informe justificativa de até 500 caracteres')
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        db.execute('BEGIN')
        try:
            item = _load(db, identifier, True)
            row = next((r for r in item['rows'] if r['row_number'] == line_number), None)
            if not row: raise ValueError('Linha desconhecida')
            if decision.get('category') and decision.get('category') != 'brokerage' and not _apply_category(decision):
                raise ValueError('Categoria inválida para lançamento novo')
            decision['reviewed_entries'] = sorted(e['entry_id'] for e in entries(db,item['account_record']) if _dates_match(e, row) and e['amount'] == Decimal(row.get('amount','0')))
            if decision['action'] != 'pending': _validate(db, item, row, decision, set())
            payload = json.dumps(decision)
            db.execute('update ledger.xp_statement_line set decision=? where import_id=? and line_number=?', [payload, identifier, line_number])
            db.execute('insert into ledger.xp_statement_decision(decision_id,import_id,line_number,payload) values (?,?,?,?)', [uuid4().hex, identifier, line_number, payload])
            db.execute('COMMIT')
        except Exception:
            db.execute('ROLLBACK')
            raise


def _document(db, item):
    metadata = item['document_metadata']
    if not item['documented_at']:
        if metadata.get('opening_balance') is not None and not metadata['errors']:
            db.execute('''insert into ledger.statement_balance_observation
              (observation_id,batch_id,account_record_id,document_id,period_start,period_end,currency,
               opening_balance,closing_balance,note,source_locator,opening_inferred)
              values (?,?,?,?,?,?,?,?,?,?,?,true)''',
                       [uuid4().hex, item['batch_id'], item['account_record'], item['document_id'],
                        metadata['period_start'], metadata['period_end'], 'BRL', metadata['opening_balance'],
                        metadata['closing_balance'], 'Extrato XP; saldo inicial inferido; conciliação financeira independente', json.dumps(metadata['source_locator'])])
        db.execute('update ledger.xp_statement set documented_at=now() where import_id=?', [item['import_id']])


def document(database, identifier):
    """Approve the load: record the statement evidence, with no decision log."""
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        db.execute('BEGIN')
        try:
            _document(db, _load(db, identifier, True))
            db.execute('COMMIT')
        except Exception:
            db.execute('ROLLBACK')
            raise


def _create(db, item, row, decision):
    event_type = decision['event_type']
    transfer_id = uuid4().hex if event_type == 'transfer' else None
    amount = Decimal(row['amount'])
    primary = uuid4().hex
    events = [(primary, item['account_record'], event_type, amount)]
    if transfer_id:
        other = decision['counterparty']
        source, destination = (item['account_record'], other) if amount < 0 else (other, item['account_record'])
        db.execute('''insert into ledger.manual_transfer(transfer_id,source_account_record_id,destination_account_record_id,
          settlement_date,currency,amount,description) values (?,?,?,?,?,?,?)''',
                   [transfer_id, source, destination, row['settlement_date'], 'BRL', abs(amount), row['description']])
        events = [(primary, item['account_record'], 'deposit' if amount > 0 else 'withdrawal', amount),
                  (uuid4().hex, other, 'withdrawal' if amount > 0 else 'deposit', -amount)]
    for event_id, account_id, kind, value in events:
        db.execute('''insert into ledger.manual_event(event_id,account_source_record_id,application_source_record_id,
          event_type,trade_date,settlement_date,currency,quantity,amount,description,transfer_id)
          values (?,?,?,?,?,?,?,?,?,?,?)''', [event_id, account_id, decision.get('application_record') if not transfer_id else None,
                                             kind, row['trade_date'], row['settlement_date'], 'BRL', decision.get('quantity') or None,
                                             value, row['description'], transfer_id])
        if decision.get('document_id'):
            db.execute('insert into ledger.manual_event_document(event_id,document_id) values (?,?)',
                       [event_id, decision['document_id']])
        if kind == 'buy':
            db.execute(
                "insert into ledger.purchase_funding values (?,'investment_balance')", [event_id])
        db.execute("insert into ledger.audit_log(audit_id,entity_type,entity_id,action,payload) values (?,'manual_event',?,'create',?)",
                   [uuid4().hex, event_id, json.dumps({'import_id': item['import_id'], 'line_number': row['row_number'], 'decision': decision, 'subtype': row['category']})])
    return [event_id for event_id, _account_id, _kind, _value in events], len(events)


def _create_attachment_events(db, item, row, decision):
    projected = _selected_attachment_rows(db, item, decision['document_id'])
    ids = []
    for projected_row in projected:
        event_id = uuid4().hex
        db.execute('''insert into ledger.manual_event
          (event_id,account_source_record_id,application_source_record_id,event_type,
           trade_date,settlement_date,currency,quantity,amount,description,transfer_id)
          values (?,?,?,?,?,?,?,?,?,?,NULL)''',
                   [event_id, item['account_record'], projected_row.get('application_record'),
                    projected_row['event_type'], projected_row.get(
                        'trade_date'),
                    projected_row['settlement_date'], projected_row.get(
                        'currency', 'BRL'),
                    projected_row.get('quantity'), projected_row['amount'],
                    projected_row.get('description', 'Nota associada')])
        if projected_row['event_type'] == 'buy':
            db.execute(
                "insert into ledger.purchase_funding values (?,'investment_balance')", [event_id])
        db.execute('insert into ledger.manual_event_document(event_id,document_id) values (?,?)',
                   [event_id, decision['document_id']])
        db.execute("""insert into ledger.audit_log
          (audit_id,entity_type,entity_id,action,payload) values (?,'manual_event',?,'create',?)""",
                   [uuid4().hex, event_id, json.dumps({'import_id': item['import_id'],
                    'line_number': row['row_number'], 'decision': decision,
                    'subtype': row['category'], 'document_id': decision['document_id']})])
        ids.append(event_id)
    return ids, len(ids)


def _finalize_attachments(db, import_id):
    """Conclude child document imports while preserving their evidence."""
    attachments = db.execute(
        'select attachment_import_id from ledger.import_attachment where parent_import_id=?',
        [import_id]).fetchall()
    for (attachment_id,) in attachments:
        db.execute('delete from ledger.import_staging_line where import_id=?', [
                   attachment_id])
        db.execute("""update ledger.file_import set status='committed',committed_at=now()
          where import_id=? and status='preview'""", [attachment_id])


def commit(database, identifier):
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        db.execute('BEGIN')
        try:
            item = _load(db, identifier, True)
            if item['document_metadata']['errors']:
                raise ValueError('Extrato com divergências de extração/saldo')
            selected = account(db, item['account_record'])
            binding = db.execute('select account_record,holder from ledger.xp_account_binding where account_number=?', [item['document_metadata']['account_number']]).fetchone()
            if not binding or binding[0] != item['account_record'] or plain(binding[1]) != plain(item['document_metadata']['holder']) or not set(plain(selected['holder']).split()).issubset(set(plain(binding[1]).split())):
                raise ValueError('Associação de conta/titular mudou; revise o cadastro')
            used = set()
            available = entries(db, item['account_record'])
            apps = applications(db, item['account_record'])
            prepared = []
            for row in item['rows']:
                claim = db.execute('select import_id,line_number from ledger.xp_statement_claim where account_record=? and fingerprint=?',
                                   [item['account_record'], row['fingerprint']]).fetchone()
                decision = row['decision']
                if claim:
                    ids = [r[0] for r in db.execute('select entry_id from ledger.xp_statement_link where import_id=? and line_number=?', claim).fetchall()]
                    decision = {'action': 'link', 'entry_ids': ids, 'reason': 'Mesma linha em extrato já confirmado'}
                elif not decision:
                    # Nothing was decided by hand: record the same identification
                    # the review screen presented, when it is complete.
                    decision, _hint, complete = _identify(db, item, row, available, apps, used)
                    if not complete:
                        decision = None
                if not decision: raise ValueError('Resolva todas as linhas antes de confirmar lançamentos')
                _validate(db, item, row, decision, used)
                prepared.append((row, decision, claim))
            count = 0
            for row, decision, claim in prepared:
                if decision['action'] == 'excluded':
                    # Dropped during review: no event, no link and no claim.
                    continue
                if decision['action'] == 'new':
                    if row.get('category') == 'brokerage':
                        ids, created = _create_attachment_events(
                            db, item, row, decision)
                    else:
                        ids, created = _create(db, item, row, decision)
                    count += created
                else:
                    ids = decision['entry_ids']
                for entry_id in ids:
                    db.execute('insert into ledger.xp_statement_link values (?,?,?)', [identifier, row['row_number'], entry_id])
                if not claim:
                    db.execute('''insert into ledger.xp_statement_claim
                      (account_record,fingerprint,import_id,line_number,description,settlement_date)
                      values (?,?,?,?,?,?)''',
                      [item['account_record'], row['fingerprint'], identifier, row['row_number'],
                       row.get('description'), row.get('settlement_date')])
            _document(db, item)
            _finalize_attachments(db, identifier)
            db.execute("update ledger.file_import set status='committed',committed_at=now() where import_id=?", [identifier])
            # Step 4: the review is over, so the temporary staging is discarded.
            # The link to the statement (xp_statement_link) and the deduplication
            # claim (xp_statement_claim) stay, because later loads rely on both.
            db.execute(
                'delete from ledger.import_staging_line where import_id=?', [identifier])
            db.execute('delete from ledger.xp_statement_decision where import_id=?', [identifier])
            db.execute('delete from ledger.xp_statement_line where import_id=?', [identifier])
            db.execute('delete from ledger.xp_statement where import_id=?', [identifier])
            db.execute('COMMIT')
            return count
        except Exception:
            db.execute('ROLLBACK')
            raise


def created_entries(db, identifier):
    """Ledger entries generated by a concluded load, for the completed step.

    The statement link outlives the review staging, and every created event
    carries its import and line numbers in the audit entry, so the entries stay
    tied to the statement that produced them.
    """
    return records(db, """select e.event_id,e.event_type,e.trade_date,e.settlement_date,e.quantity,e.amount,
        e.description,a.name application_name
      from ledger.manual_event e
      join ledger.audit_log l on l.entity_type='manual_event' and l.entity_id=e.event_id
      left join portfolio.application a on a.source_record_id=e.application_source_record_id
      where json_extract_string(l.payload,'$.import_id')=?
      order by e.settlement_date,e.event_id""", [identifier])
