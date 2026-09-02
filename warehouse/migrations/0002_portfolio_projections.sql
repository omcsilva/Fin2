-- Read-only typed projections. Source records remain the authoritative import.
CREATE SCHEMA portfolio;

CREATE VIEW portfolio.reference AS
SELECT batch_id, record_id AS source_record_id, legacy_id,
       substr(table_name, 6) AS kind,
       json_extract_string(payload, '$.nome') AS name,
       json_extract_string(payload, '$.abrev') AS abbreviation,
       payload
FROM source_record WHERE database_name = 'db.sqlite3'
AND table_name IN ('fin1_titular','fin1_instituicao','fin1_moeda','fin1_carteira',
                  'fin1_classe','fin1_tipo','fin1_produto','fin1_setor','fin1_indice');

CREATE VIEW portfolio.investor AS SELECT * FROM portfolio.reference WHERE kind='titular';
CREATE VIEW portfolio.institution AS SELECT * FROM portfolio.reference WHERE kind='instituicao';
CREATE VIEW portfolio.currency AS SELECT * FROM portfolio.reference WHERE kind='moeda';
CREATE VIEW portfolio.collection AS SELECT * FROM portfolio.reference WHERE kind='carteira';

CREATE VIEW portfolio.account AS
SELECT batch_id, record_id AS source_record_id, legacy_id,
       json_extract_string(payload,'$.nome') AS name,
       CAST(json_extract_string(payload,'$.titular_id') AS BIGINT) AS investor_id,
       CAST(json_extract_string(payload,'$.instituicao_id') AS BIGINT) AS institution_id,
       CAST(json_extract_string(payload,'$.moeda_id') AS BIGINT) AS currency_id,
       CAST(json_extract_string(payload,'$.saldo') AS DECIMAL(28,4)) AS legacy_balance
FROM source_record WHERE database_name='db.sqlite3' AND table_name='fin1_conta';

CREATE VIEW portfolio.asset AS
SELECT batch_id,record_id AS source_record_id,legacy_id,
       json_extract_string(payload,'$.nome') AS name,
       json_extract_string(payload,'$.abrev') AS symbol,
       CAST(json_extract_string(payload,'$.moeda_id') AS BIGINT) AS currency_id,
       CAST(json_extract_string(payload,'$.classe_id') AS BIGINT) AS class_id,
       CAST(json_extract_string(payload,'$.tipo_id') AS BIGINT) AS type_id,
       CAST(json_extract_string(payload,'$.produto_id') AS BIGINT) AS product_id,
       CAST(json_extract_string(payload,'$.setor_id') AS BIGINT) AS sector_id,
       CAST(json_extract_string(payload,'$.indice_id') AS BIGINT) AS index_id,
       CAST(json_extract_string(payload,'$.cotacao') AS DECIMAL(28,10)) AS legacy_price,
       CAST(substr(json_extract_string(payload,'$.dt_cotacao'),1,10) AS DATE) AS price_date
FROM source_record WHERE database_name='db.sqlite3' AND table_name='fin1_ativo';

CREATE VIEW portfolio.application AS
SELECT batch_id,record_id AS source_record_id,legacy_id,
       json_extract_string(payload,'$.nome') AS name,
       CAST(json_extract_string(payload,'$.conta_id') AS BIGINT) AS account_id,
       CAST(json_extract_string(payload,'$.ativo_id') AS BIGINT) AS asset_id,
       CAST(json_extract_string(payload,'$.em_carteira') AS DECIMAL(28,10)) AS legacy_quantity,
       CAST(json_extract_string(payload,'$.financeiro') AS DECIMAL(28,4)) AS legacy_net_invested,
       CAST(json_extract_string(payload,'$.preco_medio') AS DECIMAL(28,4)) AS legacy_average_price,
       CAST(json_extract_string(payload,'$.recebido') AS DECIMAL(28,4)) AS legacy_received
FROM source_record WHERE database_name='db.sqlite3' AND table_name='fin1_aplicacao';

CREATE VIEW portfolio.membership AS
SELECT batch_id,record_id AS source_record_id,legacy_id,
       CAST(json_extract_string(payload,'$.aplicacao_id') AS BIGINT) AS application_id,
       CAST(json_extract_string(payload,'$.carteira_id') AS BIGINT) AS collection_id
FROM source_record WHERE database_name='db.sqlite3' AND table_name='fin1_aplicacao_carteira';

CREATE VIEW portfolio.operation AS
SELECT batch_id,legacy_id,json_extract_string(payload,'$.nome') AS name,
       CAST(json_extract_string(payload,'$.multQuant') AS INTEGER) AS quantity_multiplier,
       CAST(json_extract_string(payload,'$.multValor') AS INTEGER) AS value_multiplier
FROM source_record WHERE database_name='db.sqlite3' AND table_name='fin1_operacao';

CREATE VIEW portfolio.movement AS
SELECT batch_id,record_id AS source_record_id,legacy_id,
       CAST(json_extract_string(payload,'$.aplicacao_id') AS BIGINT) AS application_id,
       CAST(json_extract_string(payload,'$.lancamento_id') AS BIGINT) AS cash_entry_id,
       CAST(json_extract_string(payload,'$.operacao_id') AS BIGINT) AS operation_id,
       CAST(substr(json_extract_string(payload,'$.dtliq'),1,10) AS DATE) AS settlement_date,
       CAST(substr(json_extract_string(payload,'$.dtmov'),1,10) AS DATE) AS trade_date,
       CAST(json_extract_string(payload,'$.quant') AS DECIMAL(28,10)) AS source_quantity,
       CAST(json_extract_string(payload,'$.valor') AS DECIMAL(28,4)) AS source_value
FROM source_record WHERE database_name='db.sqlite3' AND table_name='fin1_movimentacao';

CREATE VIEW portfolio.cash_entry AS
SELECT batch_id,record_id AS source_record_id,legacy_id,
       CAST(json_extract_string(payload,'$.conta_id') AS BIGINT) AS account_id,
       CAST(substr(json_extract_string(payload,'$.dtliq'),1,10) AS DATE) AS settlement_date,
       CAST(json_extract_string(payload,'$.credito') AS BOOLEAN) AS is_credit,
       CAST(json_extract_string(payload,'$.valor') AS DECIMAL(28,4)) AS source_value
FROM source_record WHERE database_name='db.sqlite3' AND table_name='fin1_lancamento';

CREATE VIEW portfolio.quantity_check AS
WITH movements AS (
    SELECT m.*,o.quantity_multiplier,b.as_of_date
    FROM portfolio.movement m JOIN import_batch b USING(batch_id)
    LEFT JOIN portfolio.operation o ON o.batch_id=m.batch_id AND o.legacy_id=m.operation_id
), totals AS (
    SELECT batch_id,application_id,count(*) AS movement_count,
           count(*) FILTER (WHERE settlement_date IS NULL) AS unsettled_count,
           count(*) FILTER (WHERE settlement_date>as_of_date) AS future_count,
           count(*) FILTER (WHERE quantity_multiplier IS NULL OR source_quantity IS NULL) AS incomplete_count,
           sum(abs(source_quantity)*quantity_multiplier) FILTER (WHERE settlement_date IS NOT NULL) AS all_settled_quantity,
           sum(abs(source_quantity)*quantity_multiplier) FILTER (WHERE settlement_date<=as_of_date) AS quantity_at_cutoff
    FROM movements GROUP BY batch_id,application_id
)
SELECT a.batch_id,a.legacy_id AS application_id,a.source_record_id,a.legacy_quantity,
       coalesce(t.movement_count,0) AS movement_count,
       coalesce(t.unsettled_count,0) AS unsettled_count,
       coalesce(t.future_count,0) AS future_count,
       coalesce(t.incomplete_count,0) AS incomplete_count,
       CASE WHEN coalesce(t.incomplete_count,0)=0 THEN coalesce(t.all_settled_quantity,0) END AS all_settled_quantity,
       CASE WHEN coalesce(t.incomplete_count,0)=0 THEN coalesce(t.quantity_at_cutoff,0) END AS quantity_at_cutoff,
       CASE WHEN coalesce(t.incomplete_count,0)=0 THEN coalesce(t.all_settled_quantity,0)-a.legacy_quantity END AS legacy_delta
FROM portfolio.application a LEFT JOIN totals t ON t.batch_id=a.batch_id AND t.application_id=a.legacy_id;

CREATE VIEW portfolio.position AS
SELECT a.*,ac.name AS account_name,i.name AS investor_name,s.name AS asset_name,s.symbol,
       c.abbreviation AS currency,cl.name AS class_name,s.legacy_price,s.price_date,
       q.all_settled_quantity,q.quantity_at_cutoff,q.legacy_delta,q.movement_count,
       q.unsettled_count,q.future_count,q.incomplete_count,
       CASE WHEN s.legacy_price>0 THEN a.legacy_quantity*s.legacy_price END AS legacy_market_value
FROM portfolio.application a
LEFT JOIN portfolio.account ac ON ac.batch_id=a.batch_id AND ac.legacy_id=a.account_id
LEFT JOIN portfolio.investor i ON i.batch_id=a.batch_id AND i.legacy_id=ac.investor_id
LEFT JOIN portfolio.asset s ON s.batch_id=a.batch_id AND s.legacy_id=a.asset_id
LEFT JOIN portfolio.currency c ON c.batch_id=s.batch_id AND c.legacy_id=s.currency_id
LEFT JOIN portfolio.reference cl ON cl.batch_id=s.batch_id AND cl.kind='classe' AND cl.legacy_id=s.class_id
LEFT JOIN portfolio.quantity_check q ON q.batch_id=a.batch_id AND q.application_id=a.legacy_id;
