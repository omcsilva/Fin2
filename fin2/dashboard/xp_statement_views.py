from urllib.parse import urlencode
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from fin2.imports import xp_reconciliation as xp


@require_POST
def update(request, identifier):
    if not settings.WRITE_ENABLED:
        return HttpResponse('Escrita desabilitada', status=403)
    query = {'preview': identifier}
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
            xp.document(settings.WAREHOUSE_PATH, identifier)
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
        return redirect('/fin2/importar/?' + urlencode(dict(query, error=str(exc))))
    return redirect('/fin2/importar/?' + urlencode(query))
