-- Editable catalog overlay; imported source records remain untouched.
CREATE SCHEMA catalog;
CREATE TABLE catalog.record (
 record_id VARCHAR PRIMARY KEY, batch_id VARCHAR NOT NULL,
 table_name VARCHAR NOT NULL, legacy_id BIGINT NOT NULL,
 payload JSON NOT NULL, revision INTEGER NOT NULL,
 UNIQUE(batch_id,table_name,legacy_id)
);
CREATE TABLE catalog.audit (
 audit_id VARCHAR PRIMARY KEY, record_id VARCHAR NOT NULL, revision INTEGER NOT NULL,
 before_payload JSON, after_payload JSON NOT NULL,
 request_key VARCHAR NOT NULL UNIQUE, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(record_id,revision)
);
CREATE VIEW catalog.effective_record AS
 SELECT s.batch_id,s.record_id,s.database_name,s.table_name,s.legacy_id,
        coalesce(c.payload,s.payload) payload
 FROM source_record s LEFT JOIN catalog.record c ON c.record_id=s.record_id
 UNION ALL
 SELECT c.batch_id,c.record_id,'db.sqlite3',c.table_name,c.legacy_id,c.payload
 FROM catalog.record c WHERE NOT EXISTS(SELECT 1 FROM source_record s WHERE s.record_id=c.record_id);
CREATE OR REPLACE VIEW portfolio.reference AS
SELECT batch_id, record_id AS source_record_id, legacy_id,
       substr(table_name, 6) AS kind,
       json_extract_string(payload, '$.nome') AS name,
       json_extract_string(payload, '$.abrev') AS abbreviation,
       payload
FROM catalog.effective_record WHERE database_name = 'db.sqlite3'
AND table_name IN ('fin1_titular','fin1_instituicao','fin1_moeda','fin1_carteira',
                  'fin1_classe','fin1_tipo','fin1_produto','fin1_setor','fin1_indice');

CREATE OR REPLACE VIEW portfolio.investor AS SELECT * FROM portfolio.reference WHERE kind='titular';
CREATE OR REPLACE VIEW portfolio.institution AS SELECT * FROM portfolio.reference WHERE kind='instituicao';
CREATE OR REPLACE VIEW portfolio.currency AS SELECT * FROM portfolio.reference WHERE kind='moeda';
CREATE OR REPLACE VIEW portfolio.collection AS SELECT * FROM portfolio.reference WHERE kind='carteira';

CREATE OR REPLACE VIEW portfolio.account AS
SELECT batch_id, record_id AS source_record_id, legacy_id,
       json_extract_string(payload,'$.nome') AS name,
       CAST(json_extract_string(payload,'$.titular_id') AS BIGINT) AS investor_id,
       CAST(json_extract_string(payload,'$.instituicao_id') AS BIGINT) AS institution_id,
       CAST(json_extract_string(payload,'$.moeda_id') AS BIGINT) AS currency_id,
       CAST(json_extract_string(payload,'$.saldo') AS DECIMAL(28,4)) AS legacy_balance
FROM catalog.effective_record WHERE database_name='db.sqlite3' AND table_name='fin1_conta';

CREATE OR REPLACE VIEW portfolio.asset AS
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
FROM catalog.effective_record WHERE database_name='db.sqlite3' AND table_name='fin1_ativo';

CREATE OR REPLACE VIEW portfolio.application AS
SELECT batch_id,record_id AS source_record_id,legacy_id,
       json_extract_string(payload,'$.nome') AS name,
       CAST(json_extract_string(payload,'$.conta_id') AS BIGINT) AS account_id,
       CAST(json_extract_string(payload,'$.ativo_id') AS BIGINT) AS asset_id,
       CAST(json_extract_string(payload,'$.em_carteira') AS DECIMAL(28,10)) AS legacy_quantity,
       CAST(json_extract_string(payload,'$.financeiro') AS DECIMAL(28,4)) AS legacy_net_invested,
       CAST(json_extract_string(payload,'$.preco_medio') AS DECIMAL(28,4)) AS legacy_average_price,
       CAST(json_extract_string(payload,'$.recebido') AS DECIMAL(28,4)) AS legacy_received
FROM catalog.effective_record WHERE database_name='db.sqlite3' AND table_name='fin1_aplicacao';

CREATE OR REPLACE VIEW portfolio.membership AS
SELECT batch_id,record_id AS source_record_id,legacy_id,
       CAST(json_extract_string(payload,'$.aplicacao_id') AS BIGINT) AS application_id,
       CAST(json_extract_string(payload,'$.carteira_id') AS BIGINT) AS collection_id
FROM catalog.effective_record WHERE database_name='db.sqlite3' AND table_name='fin1_aplicacao_carteira';

