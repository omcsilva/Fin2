"""Read-only report scopes shared by current and historical projections.

Filter base relations and their materialized projections consistently, before
aggregation and pagination. Catalog writes and source evidence remain untouched.
"""
import json
import re


# Relation -> entity key used by that projection. These are developer constants.
RELATIONS = {
    'account': [('portfolio.account','source_record_id'),
        ('portfolio.cash_check','source_record_id'),('ledger.cash_dashboard','source_record_id'),
        ('ledger.cash_account_reconciliation','source_record_id'),
        ('ledger.investment_cash_entry','account_source_record_id')],
    'asset': [('portfolio.asset','source_record_id'),('market.asset_catalog','source_record_id'),
        ('market.asset_catalog_effective','source_record_id'),('market.latest_external_price','source_record_id'),
        ('market.latest_ledger_price','source_record_id'),('market.ledger_price_observation','source_record_id'),
        ('market.manual_price','source_record_id'),
        ('market.daily_close','source_record_id'),('market.price_observation','source_record_id')],
    'application': [('portfolio.application','source_record_id'),('portfolio.position','source_record_id')],
    'investor': [('portfolio.investor','source_record_id')],
    'institution': [('portfolio.institution','source_record_id')],
}


def _literal(value):
    return "'"+str(value).replace("'", "''")+"'"


class ReportConnection:
    """Delegate reads, adding fixed predicates to known report relations."""
    def __init__(self, connection, predicates):
        self.connection = connection
        self.predicates = predicates
        names = '|'.join(re.escape(name) for name in sorted(predicates,key=len,reverse=True))
        self.pattern = re.compile(r'\b(FROM|JOIN)\s+('+names+r')\b', re.IGNORECASE) if names else None

    def execute(self, sql, parameters=()):
        if self.pattern:
            sql = self.pattern.sub(lambda m: m[1]+' (SELECT * FROM '+m[2]+' WHERE '+
                ' AND '.join(self.predicates[m[2].lower()])+')',sql)
        return self.connection.execute(sql,parameters)


def scoped_connection(connection, include_zeroed=False):
    if include_zeroed:
        return connection
    records = connection.execute('''SELECT record_id,batch_id,legacy_id,table_name,payload
        FROM catalog.effective_record WHERE database_name='db.sqlite3'
        AND table_name IN ('fin1_conta','fin1_ativo','fin1_aplicacao','fin1_titular',
            'fin1_instituicao','fin1_produto')''').fetchall()
    by_kind = {}
    for record, batch, identifier, table, payload in records:
        values = json.loads(payload)
        zeroed = any(str(values.get(key,'')).strip().upper() in ('ZERADO','ZERADA')
                     for key in ('status','situacao','decisao'))
        by_kind.setdefault(table,[]).append(dict(record=record,batch=batch,id=identifier,
                                               payload=values,zeroed=zeroed))
    hidden = {}
    def collect(kind, parents=()):
        result = set()
        for row in by_kind.get('fin1_'+kind,[]):
            if row['zeroed'] or any((row['batch'],row['payload'].get(field)) in hidden.get(parent,set())
                                    for field,parent in parents):
                result.add((row['batch'],row['id']))
        hidden[kind] = result
    for kind in ('titular','instituicao','produto'): collect(kind)
    collect('conta',[('titular_id','titular'),('instituicao_id','instituicao')])
    collect('ativo',[('produto_id','produto')])
    collect('aplicacao',[('conta_id','conta'),('ativo_id','ativo')])
    predicates = {}
    def exclude(relation, key, values):
        if values:
            predicates.setdefault(relation,[]).append('('+key+' IS NULL OR '+key+' NOT IN ('+
                ','.join(_literal(value) for value in sorted(values))+'))')
    def exclude_composite(relation,key,kind):
        for batch in sorted({batch for batch,_ in hidden[kind]}):
            identifiers = sorted(identifier for b,identifier in hidden[kind] if b==batch)
            predicates.setdefault(relation,[]).append('(batch_id<>'+_literal(batch)+' OR '+key+
                ' IS NULL OR '+key+' NOT IN ('+','.join(str(int(i)) for i in identifiers)+'))')
    aliases={'account':'conta','asset':'ativo','application':'aplicacao',
             'investor':'titular','institution':'instituicao'}
    for entity,relations in RELATIONS.items():
        kind = aliases[entity]
        ids = {row['record'] for row in by_kind.get('fin1_'+kind,[])
               if (row['batch'],row['id']) in hidden[kind]}
        for relation,key in relations: exclude(relation,key,ids)
    for relation in ('portfolio.movement','portfolio.quantity_detail','portfolio.quantity_check',
                     'ledger.event','ledger.cash_flow_effective_v3'):
        exclude_composite(relation,'application_id','aplicacao')
    for relation in ('portfolio.cash_entry','portfolio.cash_detail','ledger.cash_entry_canonical',
                     'ledger.cash_entry_dashboard','ledger.cash_flow_effective_v3'):
        exclude_composite(relation,'account_id','conta')
    account_ids={r['record'] for r in by_kind.get('fin1_conta',[]) if (r['batch'],r['id']) in hidden['conta']}
    application_ids={r['record'] for r in by_kind.get('fin1_aplicacao',[]) if (r['batch'],r['id']) in hidden['aplicacao']}
    exclude('ledger.manual_event','account_source_record_id',account_ids)
    exclude('ledger.manual_event','application_source_record_id',application_ids)
    exclude('ledger.purchase_contribution','account_source_record_id',account_ids)
    # The Result Account projection has no account/application columns: resolve its
    # source ids once, preserving original entry ids and unclassified evidence.
    hidden_entries=set()
    for entry,batch,account,application in connection.execute('''SELECT cash_component_id,
        batch_id,account_id,application_id FROM ledger.cash_flow_effective_v3''').fetchall():
        if (batch,account) in hidden['conta'] or (batch,application) in hidden['aplicacao']:
            hidden_entries.add(entry)
    for entry,account,application in connection.execute('''SELECT event_id,
        account_source_record_id,application_source_record_id FROM ledger.manual_event''').fetchall():
        if account in account_ids or application in application_ids: hidden_entries.add(entry)
    exclude('ledger.result_account_entry','entry_id',hidden_entries)
    # Funding shares its entry id with the purchase. Account-only filtering
    # misses purchases hidden through an asset or product in an active account.
    exclude('ledger.purchase_contribution','entry_id',hidden_entries)
    return ReportConnection(connection,predicates)
