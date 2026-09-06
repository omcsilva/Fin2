from uuid import uuid4
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from warehouse.repositories.dashboard import reader,query,Unavailable
from fin2.dashboard.views import context,paged
from fin2.dashboard.report_scope import scoped_connection
from fin2.portfolio.manual_prices import create


@require_http_methods(['GET','POST'])
def manual_prices(request):
    error=None
    if request.method=='POST':
        if not settings.WRITE_ENABLED:return HttpResponse('Escrita desabilitada',status=403)
        try:
            create(settings.WAREHOUSE_PATH,asset_record=request.POST.get('asset',''),
                price=request.POST.get('price',''),currency=request.POST.get('currency',''),
                reference_date=request.POST.get('reference_date',''),source=request.POST.get('source',''),
                note=request.POST.get('note',''),document_id=request.POST.get('document') or None,
                request_key=request.POST.get('request_key',''))
            return redirect(request.path+('?' + request.GET.urlencode() if request.GET else ''))
        except ValueError as exc:error=str(exc)
    try:
        with reader(settings.WAREHOUSE_PATH) as raw:
            db=scoped_connection(raw,request.GET.get('include_zeroed')=='1')
            data=context(request,db);batch=data['batch']['batch_id'];portfolio=data['portfolio_filter']
            scope="""a.batch_id=? AND (?='' OR EXISTS(SELECT 1 FROM portfolio.application ap
                JOIN portfolio.membership pm ON pm.batch_id=ap.batch_id AND pm.application_id=ap.legacy_id
                WHERE ap.batch_id=a.batch_id AND ap.asset_id=a.legacy_id AND CAST(pm.collection_id AS VARCHAR)=?))"""
            data['assets']=query(db,'SELECT a.source_record_id,a.name,a.symbol,a.currency FROM market.asset_catalog_effective a WHERE '+scope+' ORDER BY a.name',[batch,portfolio,portfolio])
            data['documents']=query(db,'SELECT document_id,original_filename FROM source_document WHERE batch_id=? ORDER BY original_filename',[batch])
            data.update(paged(request,db,'''SELECT m.*,a.name asset_name,d.original_filename FROM market.manual_price m
                JOIN market.asset_catalog_effective a ON a.source_record_id=m.source_record_id
                LEFT JOIN source_document d ON d.document_id=m.document_id WHERE '''+scope+'''
                AND m.reference_date<=? ORDER BY m.reference_date DESC,m.recorded_at DESC,m.price_id DESC''',
                [batch,portfolio,portfolio,data['analysis_cutoff']]))
            data.update(write_error=error,form_values=request.POST if error else {},
                request_key=request.POST.get('request_key') if error else uuid4().hex,can_write=settings.WRITE_ENABLED)
            return render(request,'dashboard/manual_prices.html',data,status=400 if error else 200)
    except Unavailable:
        return render(request,'dashboard/unavailable.html',status=503)
