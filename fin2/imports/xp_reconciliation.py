"""Audited XP evidence, account bindings and atomic financial decisions."""
from decimal import Decimal
from collections import Counter
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
        if not binding:
            if not options.get('confirm_identity') or not str(options.get('identity_reason', '')).strip():
                raise ValueError(f"Confirme a associação da conta XP {metadata['account_number']} / {metadata['holder']} com a conta selecionada e informe a justificativa")
            # Catalogs may use a short display name (Marcos/Luciana). Explicit
            # association is still required; every display-name token must match.
            if not selected['holder'] or not set(plain(selected['holder']).split()).issubset(set(plain(metadata['holder']).split())):
                raise ValueError('Titular do extrato difere do titular cadastrado; corrija o cadastro antes de associar')
            if db.execute('select 1 from ledger.xp_account_binding where account_record=?', [selected['source_record_id']]).fetchone():
                raise ValueError('Conta cadastrada já associada a outro número XP')
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
                           [metadata['account_number'], selected['source_record_id'], metadata['holder'], options['identity_reason']])
            db.execute('''insert into source_document(document_id,batch_id,source_path,original_filename,sha256,byte_size,storage_key)
              values (?,?,?,?,?,?,?)''', [document_id, selected['batch_id'], f'FIN2/imports/{digest}/{Path(filename).name}',
                                        Path(filename).name, digest, len(body), target.relative_to(root).as_posix()])
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
            db.execute('COMMIT')
        except Exception:
            db.execute('ROLLBACK')
            raise
    return identifier, 'preview'


def detail(db, identifier):
    item = _load(db, identifier)
    available = entries(db, item['account_record'])
    apps = applications(db, item['account_record'])
    counts = {'new': 0, 'linked': 0, 'pending': 0, 'divergent': 0}
    for row in item['rows']:
        row['candidates'] = [dict(e, label=f"{e['origin']} · {e['description']} · {e['amount']} · Liquidação {e['settlement_date']}") for e in available
                             if _dates_match(e, row)]
        row['suggested_ids'] = [e['entry_id'] for e in row['candidates'] if e['amount'] == Decimal(row.get('amount', '0'))]
        row['applications'] = apps
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
    item['bulk_suggestions'], item['bulk_token'] = _bulk_suggestions(db, item, available, apps)
    item['bulk_new_count'] = sum(s['decision']['action'] == 'new' and not s['needs_input'] for s in item['bulk_suggestions'])
    item['bulk_link_count'] = sum(s['decision']['action'] == 'link' for s in item['bulk_suggestions'])
    item['bulk_input_count'] = sum(s['needs_input'] for s in item['bulk_suggestions'])
    item['bulk_applications'] = apps
    item['created_count'] = db.execute("select count(*) from ledger.audit_log where entity_type='manual_event' and action='create' and json_extract_string(payload,'$.import_id')=?", [identifier]).fetchone()[0]
    item['counts'] = counts
    item['decision_history'] = records(db, 'select line_number,payload,created_at from ledger.xp_statement_decision where import_id=? order by created_at desc', [identifier])
    for history in item['decision_history']:
        history['payload'] = json.loads(history['payload'])
    metadata = item['document_metadata']
    for boundary, operator, date in (('opening', '<', metadata['period_start']), ('closing', '<=', metadata['period_end'])):
        value = db.execute(f'''select coalesce(sum(amount),0) from ledger.investment_cash_entry
          where account_source_record_id=? and settlement_date {operator} ?''', [item['account_record'], date]).fetchone()[0]
        metadata[f'ledger_{boundary}'] = str(value)
        metadata[f'{boundary}_difference'] = str(Decimal(metadata[f'{boundary}_balance']) - value) if metadata.get(f'{boundary}_balance') else None
    item['can_confirm'] = not metadata['errors'] and not counts['pending'] and not counts['divergent'] and item['status'] == 'preview'
    item['redemption_lines'] = [r for r in item['rows'] if r['category'] == 'redemption']
    item['transfer_accounts'] = [a for a in accounts(db) if a['source_record_id'] != item['account_record']]
    return item


def _validate(db, item, row, decision, used):
    if row['errors']:
        raise ValueError('Linha com erro de extração não pode ser confirmada')
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
            other = db.execute('''select l.import_id,l.line_number,r.fingerprint from ledger.xp_statement_link l
              join ledger.xp_statement_line r on r.import_id=l.import_id and r.line_number=l.line_number
              where l.entry_id=?''', [identifier]).fetchall()
            if any(fingerprint != row['fingerprint'] for _, _, fingerprint in other):
                raise ValueError('Movimento já conciliado com outra linha; revise possível reexportação divergente')
            used.add(identifier)
        return
    if decision['action'] != 'new':
        raise ValueError('Decisão pendente')
    kind = row['category']
    allowed = {'jcp': {'income'}, 'dividend': {'income'}, 'income': {'income'},
               'transfer': {'deposit','withdrawal','transfer'}, 'redemption_tax': {'tax'},
               'redemption': {'redemption'}, 'pension': {'buy'}}
    event_type = decision.get('event_type')
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
        doc = db.execute('select batch_id from source_document where document_id=?', [decision['document_id']]).fetchone()
        if not doc or doc[0] != item['batch_id']:
            raise ValueError('Documento complementar não pertence ao lote')
    if event_type in {'deposit','withdrawal','transfer'} and decision.get('application_record'):
        decision['application_record'] = None
    if event_type in {'buy','redemption'}:
        try:
            qty = Decimal(str(decision.get('quantity', '')))
            if not qty.is_finite() or qty <= 0: raise ValueError()
        except Exception:
            raise ValueError('Informe quantidade positiva comprovada') from None
        document = db.execute('select batch_id from source_document where document_id=?', [decision.get('document_id')]).fetchone()
        if not document or document[0] != item['batch_id'] or decision['document_id'] == item['document_id']:
            raise ValueError('Selecione documento complementar deste lote que comprove produto e quantidade')
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
    for existing in records(db, '''select r.raw from ledger.xp_statement_line r join ledger.xp_statement_claim c
      on c.import_id=r.import_id and c.line_number=r.line_number where c.account_record=?''', [item['account_record']]):
        other = json.loads(existing['raw'])
        if other['fingerprint'] != row['fingerprint'] and other.get('settlement_date') == row['settlement_date'] and plain(other['description']) == plain(row['description']):
            if not decision.get('distinct_confirmed'):
                raise ValueError('Extrato sobreposto contém lançamento semelhante ou alterado; revise e justifique ocorrência distinta')


def _bulk_suggestions(db, item, available=None, apps=None):
    """Only unreviewed, unambiguous decisions; never infer transfer destinations."""
    if item['status'] != 'preview' or item['document_metadata']['errors']:
        return [], ''
    available = entries(db, item['account_record']) if available is None else available
    apps = applications(db, item['account_record']) if apps is None else apps
    reserved = {entry for row in item['rows'] for entry in (row.get('decision') or {}).get('entry_ids', [])}
    proposals = []
    for row in item['rows']:
        if row['errors'] or row.get('decision'):
            continue
        if db.execute('select 1 from ledger.xp_statement_claim where account_record=? and fingerprint=?',
                      [item['account_record'], row['fingerprint']]).fetchone():
            continue
        dated = [e for e in available if _dates_match(e, row)]
        candidates = [e for e in dated if e['amount'] == Decimal(row['amount'])]
        exact = [e for e in candidates if plain(e['description']) == plain(row['description'])]
        decision = None
        label = ''
        needs_input = False
        if len(candidates) == 1 and len(exact) == 1 and exact[0]['entry_id'] not in reserved and str(exact[0]['settlement_date']) == row['settlement_date']:
            decision = {'action': 'link', 'entry_ids': [exact[0]['entry_id']],
                        'reason': 'Revisão em lote: mesma conta, liquidação, valor e descrição'}
            label = 'Vincular ao registro existente'
        else:
            app_id, match_method = identify_application(row, apps)
            app_name = next((a['name'] for a in apps if a['source_record_id'] == app_id), '') if app_id else ''
            category_event = {
                'jcp': 'income', 'dividend': 'income', 'income': 'income',
                'redemption_tax': 'tax',
            }
            if not candidates and app_id and row['category'] in category_event:
                event_type = category_event[row['category']]
                decision = {
                    'action': 'new', 'event_type': event_type,
                    'application_record': app_id, 'reviewed_entries': [],
                    'match_method': match_method,
                    'reason': f'Revisão em lote: {match_method}, sem candidato de mesma data e valor',
                }
                if row['category'] == 'redemption_tax':
                    same_date = [r for r in item['rows']
                                 if r['category'] == 'redemption'
                                 and r.get('settlement_date') == row.get('settlement_date')]
                    if len(same_date) == 1:
                        decision['related_line'] = same_date[0]['row_number']
                label = f"Novo provento · {app_name}" if event_type == 'income' else f"Novo imposto · {app_name}"
            elif not dated and row['category'] in {'transfer', 'redemption', 'redemption_tax', 'pension', 'income', 'jcp', 'dividend'}:
                base_decision = {
                    'action': 'new', 'reviewed_entries': [],
                    'reason': 'Revisão em lote: novo lançamento sem movimento nas datas de movimentação ou liquidação',
                }
                if app_id:
                    base_decision['application_record'] = app_id
                    base_decision['match_method'] = match_method
                decision = base_decision
                needs_input = True
                label = (f'Novo lançamento · {app_name} — completar dados' if app_name
                         else 'Novo lançamento — completar dados')
        if decision is None:
            continue
        if not needs_input:
            try:
                _validate(db, item, row, decision, set(reserved))
            except ValueError:
                continue
        proposals.append({'row_number': row['row_number'], 'source_locator': row['source_locator'],
                          'description': row['description'], 'settlement_date': row['settlement_date'],
                          'amount': row['amount'], 'label': label, 'decision': decision,
                          'category': row['category'], 'needs_input': needs_input,
                          'application_name': next((a['name'] for a in apps
                                                    if a['source_record_id'] == decision.get('application_record')), '')})
    usage = Counter(entry for proposal in proposals for entry in proposal['decision'].get('entry_ids', []))
    proposals = [p for p in proposals if all(usage[e] == 1 for e in p['decision'].get('entry_ids', []))]
    token = hashlib.sha256(json.dumps(proposals, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return proposals, token


def bulk_review(database, identifier, line_numbers, token, configurations=None):
    """Atomically accept the displayed suggestions, without creating ledger events."""
    try:
        selected = {int(value) for value in line_numbers}
    except (ValueError, TypeError):
        raise ValueError('Seleção de linhas inválida') from None
    if not selected:
        raise ValueError('Selecione ao menos uma sugestão')
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        db.execute('BEGIN')
        try:
            item = _load(db, identifier, True)
            proposals, current_token = _bulk_suggestions(db, item)
            if not token or token != current_token:
                raise ValueError('As sugestões mudaram. Recarregue a prévia e confira o lote novamente')
            by_line = {p['row_number']: p for p in proposals}
            if not selected.issubset(by_line):
                raise ValueError('Há linhas sem sugestão válida na seleção')
            used = {entry for row in item['rows'] for entry in (row.get('decision') or {}).get('entry_ids', [])}
            batch_key = uuid4().hex
            for row in item['rows']:
                if row['row_number'] not in selected:
                    continue
                proposal = by_line[row['row_number']]
                decision = dict(proposal['decision'], bulk_review_id=batch_key)
                if proposal['needs_input']:
                    values = (configurations or {}).get(str(row['row_number']), {})
                    for field in ('event_type','application_record','counterparty','quantity','document_id','related_line'):
                        decision[field] = values.get(field) or None
                    reason = str(values.get('reason') or '').strip()
                    if not reason or len(reason) > 500:
                        raise ValueError(f"Linha {row['source_locator']['row']}: informe a classificação/contraparte na justificativa")
                    decision['reason'] += ': ' + reason
                _validate(db, item, row, decision, used)
                payload = json.dumps(decision)
                db.execute('update ledger.xp_statement_line set decision=? where import_id=? and line_number=?',
                           [payload, identifier, row['row_number']])
                db.execute('insert into ledger.xp_statement_decision(decision_id,import_id,line_number,payload) values (?,?,?,?)',
                           [uuid4().hex, identifier, row['row_number'], payload])
            db.execute('COMMIT')
            return len(selected)
        except Exception:
            db.execute('ROLLBACK')
            raise


def review(database, identifier, line_number, decision):
    reason = str(decision.get('reason', '')).strip()
    if not reason or len(reason) > 500:
        raise ValueError('Informe justificativa de até 500 caracteres')
    with connect(Path(database).resolve(strict=True)) as db:
        migrate(db)
        db.execute('BEGIN')
        try:
            item = _load(db, identifier, True)
            row = next((r for r in item['rows'] if r['row_number'] == line_number), None)
            if not row: raise ValueError('Linha desconhecida')
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
        if kind == 'buy':
            db.execute("insert into ledger.purchase_funding values (?,'investment_balance')", [event_id])
        for doc in {item['document_id'], decision.get('document_id')} - {None, ''}:
            db.execute('insert into ledger.manual_event_document(event_id,document_id) values (?,?)', [event_id, doc])
        db.execute("insert into ledger.audit_log(audit_id,entity_type,entity_id,action,payload) values (?,'manual_event',?,'create',?)",
                   [uuid4().hex, event_id, json.dumps({'import_id': item['import_id'], 'line_number': row['row_number'], 'decision': decision, 'subtype': row['category']})])
    return [primary], len(events)


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
            prepared = []
            for row in item['rows']:
                claim = db.execute('select import_id,line_number from ledger.xp_statement_claim where account_record=? and fingerprint=?',
                                   [item['account_record'], row['fingerprint']]).fetchone()
                decision = row['decision']
                if claim:
                    ids = [r[0] for r in db.execute('select entry_id from ledger.xp_statement_link where import_id=? and line_number=?', claim).fetchall()]
                    decision = {'action': 'link', 'entry_ids': ids, 'reason': 'Mesma linha em extrato já confirmado'}
                if not decision: raise ValueError('Resolva todas as linhas antes de confirmar lançamentos')
                _validate(db, item, row, decision, used)
                prepared.append((row, decision, claim))
            count = 0
            for row, decision, claim in prepared:
                if decision['action'] == 'new':
                    ids, created = _create(db, item, row, decision)
                    count += created
                else:
                    ids = decision['entry_ids']
                for entry_id in ids:
                    db.execute('insert into ledger.xp_statement_link values (?,?,?)', [identifier, row['row_number'], entry_id])
                if not claim:
                    db.execute('insert into ledger.xp_statement_claim values (?,?,?,?)', [item['account_record'], row['fingerprint'], identifier, row['row_number']])
            _document(db, item)
            db.execute("update ledger.file_import set status='committed',committed_at=now() where import_id=?", [identifier])
            db.execute("update ledger.xp_statement set financial_status='confirmed' where import_id=?", [identifier])
            db.execute('COMMIT')
            return count
        except Exception:
            db.execute('ROLLBACK')
            raise
