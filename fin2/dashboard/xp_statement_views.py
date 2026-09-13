from urllib.parse import urlencode
from decimal import Decimal, InvalidOperation
from django.core.paginator import Paginator
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from fin2.imports import xp_reconciliation as xp
from fin2.dashboard.templatetags.fin2_format import money, short_date


# Page sizes offered by the review list; ALL shows the whole statement.
PAGE_SIZES = ('10', '50', '100')
PAGE_SIZE_ALL = 'todos'
DEFAULT_PAGE_SIZE = '50'
PAGE_SIZE_OPTIONS = tuple((value, value) for value in PAGE_SIZES) + ((PAGE_SIZE_ALL, 'Todos'),)


def review_page_size(value):
    """Validated page size from the query string, defaulting to 50."""
    return value if value in PAGE_SIZES or value == PAGE_SIZE_ALL else DEFAULT_PAGE_SIZE


def category_label(value):
    """Category wording shown to the reviewer."""
    return dict(xp.CATEGORY_OPTIONS).get(value, value or '')


def approval_table(request, selected, review=False):
    """Search and order the full statement before paginating its preview."""
    rows = selected['rows']
    selected['has_reading_errors'] = any(row.get('errors') for row in rows)
    if review:
        for row in rows:
            effective = row.get('decision') or row.get('identified') or {}
            row['table_application'] = row.get('effective_application_name') or row.get('suggested_application_name') or ''
            row['table_quantity'] = row.get('effective_quantity')
            # The detail column carries the identified category and, while the
            # line is pending, the items that still have to be provided.
            action = effective.get('action')
            if action == 'excluded':
                detail = ['Excluído do ledger']
            else:
                detail = [category_label(effective.get('category') or row.get('category'))]
                if action == 'link':
                    detail.append('Vincular a movimento existente')
            missing = row.get('identification_missing') or []
            if missing:
                detail.append('Falta: ' + ', '.join(missing))
            row['table_detail'] = ' · '.join(filter(None, detail))
            row['table_reason'] = effective.get('reason') or ''
            row['table_situation'] = {'ready': 'Pronto', 'excluded': 'Excluído'}.get(row.get('state'), 'Pendente')
    term = request.GET.get('q', '')[:200].strip()
    sort = request.GET.get('sort', 'line')
    allowed = ('line', 'trade_date', 'settlement_date', 'description', 'amount', 'balance', 'errors')
    if review: allowed += ('table_application', 'table_quantity', 'table_situation', 'table_detail')
    if sort not in allowed:
        sort = 'line'
    direction = 'desc' if request.GET.get('dir') == 'desc' else 'asc'
    if term:
        def searchable(row):
            return ' '.join(str(value or '') for value in (
                row['source_locator']['row'], row.get('description'),
                row.get('trade_date'), short_date(row.get('trade_date')),
                row.get('settlement_date'), short_date(row.get('settlement_date')),
                row.get('amount'), money(row.get('amount'), 'BRL'),
                row.get('balance'), money(row.get('balance'), 'BRL'),
                ' '.join(row.get('errors', [])),
                *([row.get(field) for field in ('category', 'table_application', 'table_quantity', 'table_situation', 'table_detail', 'table_reason')] if review else []),
            )).casefold()
        rows = [row for row in rows if term.casefold() in searchable(row)]
    def key(row):
        value = row['source_locator']['row'] if sort == 'line' else row.get(sort)
        if sort in ('line', 'amount', 'balance', 'table_quantity'):
            try:
                value = Decimal(str(value))
                if not value.is_finite(): value = None
            except (InvalidOperation, ValueError):
                value = None
        else:
            value = ' '.join(value) if isinstance(value, list) else str(value or '').casefold()
        return value
    present = [row for row in rows if key(row) is not None]
    missing = [row for row in rows if key(row) is None]
    rows = sorted(present, key=key, reverse=direction == 'desc') + missing
    size = review_page_size(request.GET.get('por_pagina')) if review else None
    per_page = len(rows) if size == PAGE_SIZE_ALL else int(size or 20)
    selected['page'] = Paginator(rows, max(per_page, 1)).get_page(request.GET.get('page'))
    selected['rows'] = selected['page'].object_list
    params = {'q': term, 'sort': sort, 'dir': direction}
    if review:
        params['por_pagina'] = size
        if request.GET.get('situacao') in xp.REVIEW_STATES: params['situacao'] = request.GET['situacao']
    else: params['preview'] = selected['import_id']
    selected['table_query'] = urlencode(params)
    selected.update(table_term=term, table_sort=sort, table_direction=direction)
    if review: selected.update(page_size=size, page_sizes=PAGE_SIZE_OPTIONS)


@require_POST
def update(request, identifier):
    if not settings.WRITE_ENABLED:
        return HttpResponse('Escrita desabilitada', status=403)
    query = {}
    target = reverse('xp-statement-review', args=[identifier])
    for field in ('q', 'sort', 'dir'):
        if request.POST.get(field): query[field] = request.POST[field][:200]
    if request.POST.get('return_page','').isdigit(): query['page'] = request.POST['return_page']
    if request.POST.get('situacao') in xp.REVIEW_STATES: query['situacao'] = request.POST['situacao']
    if request.POST.get('por_pagina'): query['por_pagina'] = review_page_size(request.POST['por_pagina'])
    try:
        if request.POST.get('operation') == 'document':
            xp.document(settings.WAREHOUSE_PATH, identifier)
        else:
            entry_ids = request.POST.getlist('entry_ids')
            # The single review form has no explicit decision field: the action
            # is excluded when asked, otherwise linked when existing movements
            # were chosen and a new entry otherwise.
            action = request.POST.get('action') or ('link' if entry_ids else 'new')
            xp.review(settings.WAREHOUSE_PATH, identifier, int(request.POST.get('line_number', '0')), {
                'action': action,
                'reason': request.POST.get('reason', ''),
                'entry_ids': entry_ids,
                'category': request.POST.get('category') or None,
                # "Alterar sugestão" replaces the identified application; an
                # unknown override is refused by the reconciliation validation.
                'application_record': request.POST.get('application_record_override') or request.POST.get('application_record') or None,
                'counterparty': request.POST.get('counterparty') or None,
                'quantity': request.POST.get('quantity') or None,
                'related_line': request.POST.get('related_line') or None,
                'document_id': request.POST.get('document_id') or None,
                'distinct_confirmed': request.POST.get('distinct_confirmed') == 'on',
            })
    except ValueError as exc:
        if request.POST.get('operation') == 'document':
            target = reverse('file-imports')
            query['preview'] = identifier
        elif request.POST.get('line_number'):
            query['review_line'] = request.POST['line_number']
        return redirect(target + '?' + urlencode(dict(query, error=str(exc))))
    return redirect(target + ('?' + urlencode(query) if query else ''))
