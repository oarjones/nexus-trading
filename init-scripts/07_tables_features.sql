-- Feature Store Metadata Table
-- Initialize features.catalog table for feature metadata

CREATE TABLE IF NOT EXISTS features.catalog (
    feature_name VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (feature_name, symbol)
);

CREATE INDEX IF NOT EXISTS idx_features_catalog_symbol 
    ON features.catalog(symbol);

CREATE INDEX IF NOT EXISTS idx_features_catalog_updated 
    ON features.catalog(last_updated DESC);

-- Log
DO $$
BEGIN
    RAISE NOTICE 'Features catalog table initialized';
END $$;
