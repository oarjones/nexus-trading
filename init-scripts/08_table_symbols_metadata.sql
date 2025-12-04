-- Symbols Metadata Table
-- Stores symbol information including sector classification
-- Created for Fix #5: Externalizing sector mapping

CREATE TABLE IF NOT EXISTS symbols_metadata (
    symbol VARCHAR(20) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    sector VARCHAR(100) NOT NULL,
    industry VARCHAR(100),
    exchange VARCHAR(50) NOT NULL,
    currency VARCHAR(10) DEFAULT 'EUR',
    country VARCHAR(50),
    market_cap_category VARCHAR(20),  -- 'large', 'mid', 'small'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add index for sector lookups
CREATE INDEX IF NOT EXISTS idx_symbols_sector ON symbols_metadata(sector);
CREATE INDEX IF NOT EXISTS idx_symbols_active ON symbols_metadata(is_active);

-- Insert initial Spanish stock data (IBEX 35)
INSERT INTO symbols_metadata (symbol, name, sector, industry, exchange, market_cap_category) VALUES
    ('SAN.MC', 'Banco Santander', 'Banking', 'Banking', 'BME', 'large'),
    ('BBVA.MC', 'Banco Bilbao Vizcaya Argentaria', 'Banking', 'Banking', 'BME', 'large'),
    ('ITX.MC', 'Inditex', 'Retail', 'Apparel Retail', 'BME', 'large'),
    ('IBE.MC', 'Iberdrola', 'Utilities', 'Electric Utilities', 'BME', 'large'),
    ('TEF.MC', 'Telefónica', 'Telecommunications', 'Telecom Services', 'BME', 'large'),
    ('REP.MC', 'Repsol', 'Energy', 'Oil & Gas', 'BME', 'large'),
    ('CABK.MC', 'CaixaBank', 'Banking', 'Banking', 'BME', 'large'),
    ('FER.MC', 'Ferrovial', 'Industrials', 'Engineering & Construction', 'BME', 'large'),
    ('ACS.MC', 'ACS', 'Industrials', 'Engineering & Construction', 'BME', 'large'),
    ('ENG.MC', 'Enagás', 'Utilities', 'Gas Utilities', 'BME', 'mid'),
    ('IAG.MC', 'International Airlines Group', 'Industrials', 'Airlines', 'BME', 'large'),
    ('AENA.MC', 'Aena', 'Industrials', 'Airport Services', 'BME', 'large'),
    ('GRF.MC', 'Grifols', 'Healthcare', 'Biotechnology', 'BME', 'mid'),
    ('MAP.MC', 'Mapfre', 'Financials', 'Insurance', 'BME', 'mid'),
    ('ACX.MC', 'Acerinox', 'Materials', 'Steel', 'BME', 'mid')
ON CONFLICT (symbol) DO UPDATE SET
    name = EXCLUDED.name,
    sector = EXCLUDED.sector,
    industry = EXCLUDED.industry,
    updated_at = NOW();

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_symbols_metadata_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
CREATE TRIGGER trigger_symbols_metadata_updated_at
    BEFORE UPDATE ON symbols_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_symbols_metadata_updated_at();

-- Comment on table
COMMENT ON TABLE symbols_metadata IS 'Metadata for trading symbols including sector classification';
COMMENT ON COLUMN symbols_metadata.sector IS 'Primary sector classification (Banking, Retail, Utilities, etc.)';
COMMENT ON COLUMN symbols_metadata.market_cap_category IS 'Market capitalization category: large, mid, or small cap';
