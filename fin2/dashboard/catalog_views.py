"""Catalog maintenance views without Django ORM or session storage."""
from uuid import uuid4
from urllib.parse import urlencode
from django import forms
from django.conf import settings
from django.http import Http404,HttpResponse
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from warehouse.repositories.dashboard import reader,Unavailable,query
from fin2.portfolio.catalog import KINDS,OPTIONAL,records,save
from fin2.dashboard.views import context
from fin2.dashboard.catalog_images import manifest
from fin2.portfolio.catalog_image_uploads import validate_upload


class CatalogImageField(forms.FileField):
    def clean(self, data, initial=None):
        upload = super().clean(data, initial)
        if not upload:
            return None
        try:
            return validate_upload(upload)
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc


@require_http_methods(['GET','POST'])
def catalog(request,kind='titular'):
    if kind not in KINDS:raise Http404
    error=None
    try:
        with reader(settings.WAREHOUSE_PATH) as db:
            data=context(request,db);batch=data['batch']['batch_id']
            items=records(db,batch,kind)
            application_accounts=[]
            application_assets=[]
            application_search=''
            application_account_filter=''
            application_asset_filter=''
            application_filter_query=''
            if kind == 'aplicacao':
                account_records=records(db,batch,'conta')
                asset_records=records(db,batch,'ativo')
                accounts_by_id={str(row['legacy_id']):row['payload'] for row in account_records}
                assets_by_id={str(row['legacy_id']):row['payload'] for row in asset_records}
                application_accounts=[
                    (row['legacy_id'], row['payload'].get('abrev') or row['payload'].get('nome') or row['legacy_id'])
                    for row in account_records]
                application_assets=[
                    (row['legacy_id'], row['payload'].get('abrev') or row['payload'].get('nome') or row['legacy_id'])
                    for row in asset_records]
                application_account_filter=(request.GET.get('conta')
                    or request.GET.get('conta_id',''))
                application_asset_filter=request.GET.get('ativo','')
                application_search=request.GET.get('q','')[:200].strip()
                filtered=[]
                for item in items:
                    payload=item['payload']
                    account_id=str(payload.get('conta_id') or '')
                    asset_id=str(payload.get('ativo_id') or '')
                    if application_account_filter and account_id != application_account_filter:
                        continue
                    if application_asset_filter and asset_id != application_asset_filter:
                        continue
                    account_payload=accounts_by_id.get(account_id,{})
                    asset_payload=assets_by_id.get(asset_id,{})
                    searchable=' '.join(str(value or '') for value in (
                        payload.get('nome'),payload.get('statement_aliases'),
                        account_payload.get('nome'),account_payload.get('abrev'),
                        asset_payload.get('nome'),asset_payload.get('abrev'),
                        asset_payload.get('isin'),asset_payload.get('cnpj')))
                    if application_search and application_search.casefold() not in searchable.casefold():
                        continue
                    filtered.append(item)
                items=filtered
                application_filter_query=urlencode({key:value for key,value in {
                    'conta':application_account_filter,
                    'ativo':application_asset_filter,'q':application_search,
                }.items() if value})
            identifier=request.GET.get('edit')
            selected=next((r for r in items if r['record_id']==identifier),None)
            if identifier and not selected:raise Http404
            initial = selected['payload'] if selected else {}
            if kind == 'aplicacao' and not selected:
                initial = {**initial, 'conta_id': request.GET.get('conta_id') or request.GET.get('conta', '')}
            form=forms.Form(request.POST if request.method=='POST' else None,
                            files=request.FILES if request.method=='POST' else None,
                            initial=initial)
            labels={}
            for field,(label,target) in KINDS[kind][1].items():
                if kind == 'aplicacao' and field == 'nome' and not selected:
                    continue
                if field in ('status','decisao'):
                    choices = [('', 'Sem status'), ('ZERADO', 'ZERADO')] if field == 'status' else [
                        ('','Sem status'), ('MANTER','MANTER'), ('ZERADA','ZERADO')]
                    form.fields[field] = forms.ChoiceField(label=label,choices=choices,required=False)
                    labels[field] = dict(choices)
                elif target:
                    choices=[(str(r['legacy_id']),r['payload'].get('nome') or str(r['legacy_id'])) for r in records(db,batch,target)]
                    labels[field]=dict(choices)
                    form.fields[field]=forms.ChoiceField(label=label,choices=[('','Selecione')]+choices,required=field not in OPTIONAL)
                else:form.fields[field]=forms.CharField(label=label,max_length=200,required=field not in OPTIONAL)
            if kind == 'titular':
                form.fields['imagem_upload'] = CatalogImageField(
                    label='Imagem', required=False,
                    help_text='PNG, JPEG ou WebP, até 5 MB. Sem novo arquivo, a imagem atual será mantida.',
                    widget=forms.FileInput(attrs={'accept': 'image/png,image/jpeg,image/webp'}))
            images = manifest()
            for item in items:
                item['image'] = images.get(item['payload'].get('imagem'))
                item['cells']=[labels.get(field,{}).get(str(item['payload'].get(field)),item['payload'].get(field) or '—') for field in KINDS[kind][1]]
            history=query(db,'select revision,created_at from catalog.audit where record_id=? order by revision desc',[identifier]) if identifier else []
            data.update(catalog_kinds=list(KINDS.items()),catalog_kind=kind,catalog_title=KINDS[kind][0],
              catalog_columns=[value[0] for value in KINDS[kind][1].values()],catalog_items=items,
              catalog_selected=selected,catalog_history=history,catalog_form=form,
              catalog_request_key=request.POST.get('request_key') or uuid4().hex,
              catalog_revision=request.POST.get('revision') if request.method=='POST' else (selected['revision'] if selected else 0),
              catalog_writable=settings.WRITE_ENABLED,
              catalog_application_form=(kind == 'aplicacao' and not selected),
              application_accounts=application_accounts,
              application_assets=application_assets,
              application_account_filter=application_account_filter,
              application_asset_filter=application_asset_filter,
              application_search=application_search,
              application_filter_query=application_filter_query,
              catalog_has_images=any(item['image'] for item in items))
        if request.method=='POST':
            if not settings.WRITE_ENABLED:return HttpResponse('Escrita desabilitada',status=403)
            if form.is_valid():
                try:
                    record=save(settings.WAREHOUSE_PATH,batch=batch,kind=kind,values=form.cleaned_data,
                      image=form.cleaned_data.get('imagem_upload'),image_root=settings.CATALOG_IMAGE_ROOT,
                      record_id=identifier,revision=request.POST.get('revision','0'),request_key=request.POST.get('request_key',''))
                    return redirect('/fin2/cadastros/'+kind+'/?'+urlencode({'batch':batch,'edit':record,'saved':'1'}))
                except ValueError as exc:error=str(exc)
            else:error='Confira os campos indicados.'
        data.update(catalog_error=error,catalog_saved=request.GET.get('saved')=='1')
        return render(request,'dashboard/catalog.html',data,status=400 if error else 200)
    except Unavailable:return render(request,'dashboard/unavailable.html',status=503)
