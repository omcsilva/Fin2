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


def approval_table(request, selected):
    """Search and order the full statement before paginating its preview."""
    rows = selected['rows']
    selected['has_reading_errors'] = any(row.get('errors') for row in rows)
    term = request.GET.get('q', '')[:200].strip()
    sort = request.GET.get('sort', 'line')
    if sort not in ('line', 'trade_date', 'settlement_date', 'description', 'amount', 'balance', 'errors'):
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
            )).casefold()
        rows = [row for row in rows if term.casefold() in searchable(row)]
    def key(row):
        value = row['source_locator']['row'] if sort == 'line' else row.get(sort)
        if sort in ('line', 'amount', 'balance'):
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
    selected['page'] = Paginator(rows, 20).get_page(request.GET.get('page'))
    selected['rows'] = selected['page'].object_list
    selected['table_query'] = urlencode({'preview': selected['import_id'], 'q': term, 'sort': sort, 'dir': direction})
    selected.update(table_term=term, table_sort=sort, table_direction=direction)


@require_POST
def update(request, identifier):
    if not settings.WRITE_ENABLED:
        return HttpResponse('Escrita desabilitada', status=403)
    query = {}
    target = reverse('xp-statement-review', args=[identifier])
    if request.POST.get('return_page','').isdigit(): query['page'] = request.POST['return_page']
    if request.POST.get('pending') == '1': query['pending'] = '1'
    try:
        if request.POST.get('operation') == 'bulk_review':
            lines = request.POST.getlist('bulk_line')
            configurations = {line: {field: request.POST.get(f'bulk_{line}_{field}') for field in
                ('event_type','application_record','counterparty','quantity','document_id','related_line','reason')} for line in lines}
            count = xp.bulk_review(settings.WAREHOUSE_PATH, identifier, lines, request.POST.get('bulk_token',''), configurations)
            query['bulk_accepted'] = str(count)
        elif request.POST.get('operation') == 'document':
            xp.document(settings.WAREHOUSE_PATH, identifier, request.POST.get('reason', ''))
        else:
            xp.review(settings.WAREHOUSE_PATH, identifier, int(request.POST.get('line_number', '0')), {
                'action': request.POST.get('action', 'pending'),
                'reason': request.POST.get('reason', ''),
                'entry_ids': request.POST.getlist('entry_ids'),
                'event_type': request.POST.get('event_type', ''),
                'application_record': request.POST.get('application_record') or None,
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
