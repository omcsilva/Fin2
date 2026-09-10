-- Expand portfolio views with matching-relevant asset fields and statement_aliases.
-- Uses CREATE OR REPLACE VIEW — no data is modified.

CREATE OR REPLACE VIEW portfolio.asset AS
SELECT batch_id, record_id AS source_record_id, legacy_id,
       json_extract_string(payload,'$.nome') AS name,
       json_extract_string(payload,'$.abrev') AS symbol,
       CAST(json_extract_string(payload,'$.moeda_id') AS BIGINT) AS currency_id,
       CAST(json_extract_string(payload,'$.classe_id') AS BIGINT) AS class_id,
       CAST(json_extract_string(payload,'$.tipo_id') AS BIGINT) AS type_id,
       CAST(json_extract_string(payload,'$.produto_id') AS BIGINT) AS product_id,
       CAST(json_extract_string(payload,'$.setor_id') AS BIGINT) AS sector_id,
       CAST(json_extract_string(payload,'$.indice_id') AS BIGINT) AS index_id,
       CAST(json_extract_string(payload,'$.cotacao') AS DECIMAL(28,10)) AS legacy_price,
       CAST(substr(json_extract_string(payload,'$.dt_cotacao'),1,10) AS DATE) AS price_date,
       json_extract_string(payload,'$.cnpj') AS cnpj,
       json_extract_string(payload,'$.emissor') AS issuer,
       json_extract_string(payload,'$.indexador') AS indexer,
       CAST(json_extract_string(payload,'$.vencimento') AS DATE) AS maturity_date,
       json_extract_string(payload,'$.taxa') AS contracted_rate,
       json_extract_string(payload,'$.statement_aliases') AS statement_aliases
FROM catalog.effective_record
WHERE database_name='db.sqlite3' AND table_name='fin1_ativo';


CREATE OR REPLACE VIEW portfolio.application AS
SELECT batch_id, record_id AS source_record_id, legacy_id,
       json_extract_string(payload,'$.nome') AS name,
       CAST(json_extract_string(payload,'$.conta_id') AS BIGINT) AS account_id,
       CAST(json_extract_string(payload,'$.ativo_id') AS BIGINT) AS asset_id,
       CAST(json_extract_string(payload,'$.em_carteira') AS DECIMAL(28,10)) AS legacy_quantity,
       CAST(json_extract_string(payload,'$.financeiro') AS DECIMAL(28,4)) AS legacy_net_invested,
       CAST(json_extract_string(payload,'$.preco_medio') AS DECIMAL(28,4)) AS legacy_average_price,
       CAST(json_extract_string(payload,'$.recebido') AS DECIMAL(28,4)) AS legacy_received,
       json_extract_string(payload,'$.statement_aliases') AS statement_aliases
FROM catalog.effective_record
WHERE database_name='db.sqlite3' AND table_name='fin1_aplicacao';
