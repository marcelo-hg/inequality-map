CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
INSERT INTO schema_version VALUES (1);
CREATE TABLE ingestion_runs (
    run_id VARCHAR PRIMARY KEY, status VARCHAR NOT NULL, started_at VARCHAR,
    finished_at VARCHAR, code_json JSON NOT NULL, config_json JSON NOT NULL,
    manifest_sha256 VARCHAR NOT NULL
);
CREATE TABLE sources (
    source_id VARCHAR PRIMARY KEY, provider VARCHAR NOT NULL, dataset VARCHAR NOT NULL,
    dataset_version VARCHAR NOT NULL, url VARCHAR, publication_date VARCHAR,
    license VARCHAR, citation VARCHAR, notes VARCHAR
);
CREATE TABLE source_files (
    file_id VARCHAR PRIMARY KEY, source_id VARCHAR REFERENCES sources(source_id),
    run_id VARCHAR REFERENCES ingestion_runs(run_id), path VARCHAR NOT NULL,
    url VARCHAR NOT NULL, downloaded_at VARCHAR NOT NULL, last_modified VARCHAR,
    sha256 VARCHAR NOT NULL, payload_sha256 VARCHAR NOT NULL, payload_bytes BIGINT,
    kind VARCHAR NOT NULL, area VARCHAR
);
CREATE TABLE countries (
    iso3 VARCHAR PRIMARY KEY, iso2 VARCHAR UNIQUE, country_name VARCHAR NOT NULL,
    region VARCHAR, subregion VARCHAR, code_status VARCHAR NOT NULL
);
CREATE TABLE areas (
    area_id VARCHAR PRIMARY KEY, provider VARCHAR NOT NULL, original_code VARCHAR NOT NULL,
    alternate_code VARCHAR,
    area_name VARCHAR NOT NULL, area_type VARCHAR NOT NULL,
    iso3 VARCHAR REFERENCES countries(iso3), file_id VARCHAR REFERENCES source_files(file_id),
    UNIQUE(provider, original_code)
);
CREATE TABLE series (
    series_id VARCHAR PRIMARY KEY, area_id VARCHAR REFERENCES areas(area_id),
    source_id VARCHAR REFERENCES sources(source_id), indicator_code VARCHAR NOT NULL,
    original_variable VARCHAR NOT NULL, statistic VARCHAR NOT NULL,
    income_definition VARCHAR, population_basis VARCHAR, statistical_unit VARCHAR,
    unit VARCHAR, currency VARCHAR, price_basis VARCHAR, price_year INTEGER,
    method VARCHAR, citation VARCHAR, quality VARCHAR, metadata_json JSON,
    metadata_file_id VARCHAR REFERENCES source_files(file_id),
    UNIQUE(area_id, indicator_code)
);
CREATE TABLE percentile_groups (
    group_id VARCHAR PRIMARY KEY, original_code VARCHAR UNIQUE NOT NULL,
    lower_bound DOUBLE NOT NULL, upper_bound DOUBLE,
    population_share DOUBLE, is_interval BOOLEAN NOT NULL,
    CHECK(lower_bound >= 0 AND lower_bound <= 100),
    CHECK(upper_bound IS NULL OR (upper_bound > lower_bound AND upper_bound <= 100))
);
CREATE TABLE observations (
    observation_id VARCHAR PRIMARY KEY, series_id VARCHAR REFERENCES series(series_id),
    year INTEGER NOT NULL, group_id VARCHAR REFERENCES percentile_groups(group_id),
    value DOUBLE, original_value VARCHAR, data_status VARCHAR NOT NULL,
    source_quality VARCHAR, source_status VARCHAR, is_requested BOOLEAN NOT NULL,
    file_id VARCHAR REFERENCES source_files(file_id), source_row BIGINT,
    UNIQUE(series_id, year, group_id)
);
CREATE TABLE ppp_conversions (
    conversion_id VARCHAR PRIMARY KEY, area_id VARCHAR REFERENCES areas(area_id),
    currency VARCHAR NOT NULL, price_year INTEGER NOT NULL, ppp_reference VARCHAR,
    factor DOUBLE NOT NULL CHECK(factor > 0),
    ppp_observation_id VARCHAR REFERENCES observations(observation_id),
    price_observation_id VARCHAR REFERENCES observations(observation_id),
    method VARCHAR NOT NULL, data_status VARCHAR NOT NULL
);
CREATE TABLE issues (
    issue_id VARCHAR PRIMARY KEY, severity VARCHAR NOT NULL, code VARCHAR NOT NULL,
    area_id VARCHAR, year INTEGER, indicator_code VARCHAR, details VARCHAR NOT NULL
);
CREATE VIEW country_codes AS
SELECT provider, original_code, alternate_code, iso3, area_type FROM areas;
CREATE VIEW income_ppp AS
SELECT o.observation_id, a.iso3, a.area_id, s.indicator_code, s.statistic,
       o.year, g.original_code AS percentile, g.lower_bound, g.upper_bound, g.population_share,
       o.value AS income_lcu, o.value / c.factor AS income_ppp,
       s.currency, c.price_year, c.ppp_reference, 'USD_PPP' AS ppp_currency,
       s.population_basis, s.statistical_unit, s.income_definition,
       o.data_status AS input_status, 'derived' AS ppp_status,
       c.conversion_id, c.ppp_observation_id, c.price_observation_id,
       o.file_id, s.metadata_file_id, o.is_requested
FROM observations o JOIN series s USING(series_id) JOIN areas a USING(area_id)
JOIN percentile_groups g USING(group_id)
JOIN ppp_conversions c ON c.area_id = a.area_id AND c.currency = s.currency AND c.price_year = s.price_year
WHERE s.statistic IN ('mean', 'threshold', 'total') AND s.income_definition IS NOT NULL;
CREATE VIEW income_percentiles AS
SELECT * FROM income_ppp WHERE indicator_code = 'aptinc992j'
AND upper_bound - lower_bound = 1 AND lower_bound = floor(lower_bound) AND is_requested;
