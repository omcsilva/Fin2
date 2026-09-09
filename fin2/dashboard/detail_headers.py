"""Images and parent links shared by the financial detail pages."""
import json
from urllib.parse import urlencode

from django.urls import reverse
from fin2.dashboard.catalog_images import manifest
from fin2.portfolio.catalog import KINDS
from warehouse.repositories.dashboard import query

DETAIL_ROUTES = {'conta': 'account-detail', 'instituicao': 'institution-detail',
                 'titular': 'investor-detail', 'produto': 'product-detail', 'classe': 'class-detail'}


def detail_header(connection, record_id, global_query, title=None):
    records = query(connection, 'SELECT * FROM catalog.effective_record WHERE record_id=?', [record_id])
    if not records:
        return {}
    record = records[0]
    kind = record['table_name'].removeprefix('fin1_')
    payload = json.loads(record['payload']) if isinstance(record['payload'], str) else record['payload']
    images = manifest()
    image = images.get(payload.get('imagem'))
    parents = []
    seen = set()

    def add_parents(source_kind, source_payload):
        for field, (label, target) in KINDS.get(source_kind, ('', {}))[1].items():
            identifier = source_payload.get(field)
            if not target or identifier is None or (target, str(identifier)) in seen:
                continue
            seen.add((target, str(identifier)))
            matches = query(connection, '''SELECT * FROM catalog.effective_record
                WHERE batch_id=? AND database_name='db.sqlite3' AND table_name=? AND legacy_id=?''',
                [record['batch_id'], 'fin1_' + target, identifier])
            if not matches:
                continue
            parent = matches[0]
            content = json.loads(parent['payload']) if isinstance(parent['payload'], str) else parent['payload']
            url = (reverse(DETAIL_ROUTES[target], args=[parent['legacy_id']]) if target in DETAIL_ROUTES
                   else reverse('catalog-kind', args=[target]))
            params = global_query
            if target not in DETAIL_ROUTES:
                params += ('&' if params else '') + urlencode({'edit': parent['record_id']})
            parents.append(dict(label=label, name=content.get('nome') or content.get('abrev') or f'#{identifier}',
                                url=url + ('?' + params if params else ''),
                                image=images.get(content.get('imagem')), kind=target))
            if source_kind == 'aplicacao' and target in ('conta', 'ativo'):
                add_parents(target, content)

    add_parents(kind, payload)
    return {'detail_header': dict(title=title or payload.get('nome') or payload.get('abrev') or f'#{record["legacy_id"]}',
                                  image=image, parents=parents,
                                  account_images=[p for p in parents if p['kind'] in ('titular', 'instituicao') and p['image']] if kind == 'conta' else [],
                                  catalog_url=reverse('catalog-kind', args=[kind]) + '?' + global_query,
                                  catalog_label=KINDS[kind][0])}
