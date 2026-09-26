"""Validated catalog edits over immutable imported records."""
import hashlib,json,re
from datetime import date
from decimal import Decimal,InvalidOperation
from uuid import uuid4
from warehouse.database import connect,migrate

# field -> (label, referenced catalog kind); None means free text.
KINDS={
 'titular':('Titulares',{'nome':('Nome',None)}),
 'instituicao':('Instituições',{'nome':('Nome',None),'abrev':('Abreviação',None)}),
 'moeda':('Moedas',{'nome':('Nome',None),'abrev':('Código',None)}),
 'carteira':('Carteiras',{'nome':('Nome',None)}),
 'classe':('Classes',{'nome':('Nome',None)}),
 'tipo':('Tipos',{'nome':('Nome',None)}),
 'produto':('Produtos',{'nome':('Nome',None)}),
 'setor':('Setores',{'nome':('Nome',None)}),
 'indice':('Índices',{'nome':('Nome',None),'abrev':('Código',None)}),
 'conta':('Contas',{'nome':('Nome',None),'titular_id':('Titular','titular'),
    'instituicao_id':('Instituição','instituicao'),'moeda_id':('Moeda','moeda')}),
 'ativo':('Ativos',{'nome':('Nome',None),'abrev':('Símbolo',None),'moeda_id':('Moeda','moeda'),
    'classe_id':('Classe','classe'),'tipo_id':('Tipo','tipo'),'produto_id':('Produto','produto'),
    'setor_id':('Setor','setor'),'indice_id':('Índice','indice'),
    'isin':('ISIN',None),'cnpj':('CNPJ',None),'emissor':('Emissor',None),
    'vencimento':('Vencimento (AAAA-MM-DD)',None),'indexador':('Indexador contratado',None),
    'taxa':('Taxa contratada (%)',None),
    'statement_aliases':('Nomes alternativos em extratos (separados por |)',None)}),
 'aplicacao':('Aplicações',{'nome':('Nome',None),'conta_id':('Conta','conta'),'ativo_id':('Ativo','ativo'),
    'statement_aliases':('Nomes alternativos em extratos (separados por |)',None)}),
 'aplicacao_carteira':('Vínculos com carteiras',{'aplicacao_id':('Aplicação','aplicacao'),'carteira_id':('Carteira','carteira')})
}
STATUS_KINDS = {'titular','instituicao','produto','ativo'}
for _kind in STATUS_KINDS:
    KINDS[_kind][1]['status'] = ('Status',None)
KINDS['conta'][1]['decisao'] = ('Status',None)
OPTIONAL={'abrev','tipo_id','produto_id','setor_id','indice_id','isin','cnpj','emissor','vencimento','indexador','taxa','status','decisao','statement_aliases'}

def _validate_aliases(payload):
    """Validate and normalise the statement_aliases field (pipe-separated)."""
    raw = payload.get('statement_aliases')
    if not raw:
        payload['statement_aliases'] = None
        return
    aliases = [a.strip() for a in str(raw).split('|') if a.strip()]
    if len(aliases) > 20:
        raise ValueError('Nomes alternativos: máximo de 20 entradas')
    if any(len(a) > 100 for a in aliases):
        raise ValueError('Nome alternativo: máximo de 100 caracteres cada')
    payload['statement_aliases'] = '|'.join(aliases)


def records(db,batch,kind):
    if kind not in KINDS:raise ValueError('Cadastro desconhecido')
    rows=db.execute('''select e.record_id,e.legacy_id,e.payload,coalesce(c.revision,0)
      from catalog.effective_record e left join catalog.record c on c.record_id=e.record_id
      where e.batch_id=? and e.database_name='db.sqlite3' and e.table_name=?
      order by lower(coalesce(json_extract_string(e.payload,'$.nome'),'')),e.legacy_id''',[batch,'fin1_'+kind]).fetchall()
    return [{'record_id':r[0],'legacy_id':r[1],'payload':json.loads(r[2]),'revision':r[3]} for r in rows]

def save(database,*,batch,kind,values,record_id=None,revision=0,request_key,image=None,image_root=None):
    if kind not in KINDS:raise ValueError('Cadastro desconhecido')
    if not re.fullmatch('[a-f0-9]{32}',request_key or ''):raise ValueError('Chave de envio inválida')
    with connect(database) as db:
        migrate(db)
        prior=db.execute('select record_id from catalog.audit where request_key=?',[request_key]).fetchone()
        if prior:return prior[0]
        if not db.execute('select 1 from import_batch where batch_id=?',[batch]).fetchone():raise ValueError('Lote desconhecido')
        existing=next((r for r in records(db,batch,kind) if r['record_id']==record_id),None) if record_id else None
        if record_id and not existing:raise ValueError('Registro desconhecido')
        if not existing and int(revision)!=0:raise ValueError('Revisão inicial inválida')
        if existing and existing['revision']!=int(revision):raise ValueError('O cadastro foi alterado em outra página. Recarregue antes de salvar.')
        before=existing['payload'] if existing else None
        payload=dict(before or {})
        for field,(label,target) in KINDS[kind][1].items():
            if kind=='aplicacao' and field=='nome' and not existing:
                continue
            value=str(values.get(field) or '').strip()
            if field in ('status','decisao'):
                if field not in values:
                    value = str(payload.get(field) or '').strip()
                value = value.upper()
                allowed = {'','ZERADO'} if field == 'status' else {'','MANTER','ZERADA'}
                if value not in allowed:
                    raise ValueError('Status inválido')
                payload[field] = value
                continue
            if not value:
                if field not in OPTIONAL:raise ValueError(f'{label}: preenchimento obrigatório')
                value=None
            elif target:
                try:value=int(value)
                except ValueError:raise ValueError(f'{label}: referência inválida') from None
                if not any(r['legacy_id']==value for r in records(db,batch,target)):raise ValueError(f'{label}: referência inválida')
            else:
                value=' '.join(value.split())
                if len(value)>200:raise ValueError(f'{label}: máximo de 200 caracteres')
            if existing and target and before.get(field)!=value:
                raise ValueError(f'{label}: não é possível trocar vínculos de um cadastro existente; crie um novo cadastro.')
            payload[field]=value
        if kind=='ativo':
            if payload.get('isin'):
                payload['isin']=payload['isin'].upper()
                if not re.fullmatch('[A-Z]{2}[A-Z0-9]{9}[0-9]',payload['isin']):raise ValueError('ISIN: formato inválido')
            if payload.get('cnpj'):
                payload['cnpj']=re.sub(r'[./-]','',payload['cnpj'])
                if not re.fullmatch('[0-9]{14}',payload['cnpj']):raise ValueError('CNPJ: informe 14 dígitos')
            if payload.get('vencimento'):
                try:date.fromisoformat(payload['vencimento'])
                except ValueError:raise ValueError('Vencimento: data inválida') from None
            if payload.get('taxa'):
                try:
                    rate=Decimal(payload['taxa'].replace(',','.'))
                    if not rate.is_finite():raise InvalidOperation
                except InvalidOperation:raise ValueError('Taxa contratada inválida') from None
                payload['taxa']=str(rate)
            _validate_aliases(payload)
        if kind=='aplicacao':
            if not existing:
                account_id=payload.get('conta_id')
                asset_id=payload.get('ativo_id')
                account_record=next((r for r in records(db,batch,'conta')
                                     if r['legacy_id']==account_id),None)
                asset_record=next((r for r in records(db,batch,'ativo')
                                   if r['legacy_id']==asset_id),None)
                if not account_record or not asset_record:
                    raise ValueError('Conta e ativo devem ser selecionados')
                account_label=(account_record['payload'].get('abrev')
                               or account_record['payload'].get('nome') or '').strip()
                asset_label=(asset_record['payload'].get('abrev')
                             or asset_record['payload'].get('nome') or '').strip()
                if not account_label or not asset_label:
                    raise ValueError('Conta e ativo precisam ter abreviação ou nome')
                payload['nome']=f'{account_label} {asset_label}'
            _validate_aliases(payload)
        others=[r for r in records(db,batch,kind) if r['record_id']!=record_id]
        if kind=='aplicacao_carteira':
            if any(all(r['payload'].get(f)==payload[f] for f in KINDS[kind][1]) for r in others):raise ValueError('Vínculo já cadastrado')
        elif any(str(r['payload'].get('nome') or '').casefold()==payload['nome'].casefold() for r in others):
            raise ValueError('Já existe um cadastro com este nome')
        if existing:legacy_id=existing['legacy_id']
        else:
            legacy_id=max([0]+[r['legacy_id'] for r in others])+1
            record_id=hashlib.sha256(uuid4().bytes).hexdigest()
            payload['id']=legacy_id
            if kind=='conta':payload['saldo']='0'
            if kind=='aplicacao':payload.update(em_carteira='0',financeiro='0',preco_medio='0',recebido='0')
        if image is not None:
            if kind != 'titular' or image_root is None:
                raise ValueError('Upload de imagem disponível apenas para titulares.')
            from fin2.portfolio.catalog_image_uploads import store_image
            payload['imagem'] = store_image(image_root, image)
        new_revision=int(revision)+1
        db.execute('BEGIN')
        try:
            db.execute('''insert into catalog.record values (?,?,?,?,?,?)
              on conflict(record_id) do update set payload=excluded.payload,revision=excluded.revision''',
              [record_id,batch,'fin1_'+kind,legacy_id,json.dumps(payload),new_revision])
            db.execute('''insert into catalog.audit(audit_id,record_id,revision,before_payload,after_payload,request_key)
              values (?,?,?,?,?,?)''',[uuid4().hex,record_id,new_revision,json.dumps(before) if before else None,json.dumps(payload),request_key])
            if kind=='ativo':
                db.execute("""insert into market.asset_price_update_method(source_record_id,method)
                  values (?,'BRAPI') on conflict do nothing""",[record_id])
            db.execute('COMMIT')
        except Exception:db.execute('ROLLBACK');raise
    return record_id
