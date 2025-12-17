-- Schema for Competition Module

CREATE SCHEMA IF NOT EXISTS competition;

CREATE TABLE IF NOT EXISTS competition.agent_state (
    agent_id TEXT PRIMARY KEY,
    competition_day INTEGER NOT NULL DEFAULT 0,
    is_onboarded BOOLEAN NOT NULL DEFAULT FALSE,
    start_date TIMESTAMP WITH TIME ZONE,
    
    -- Metrics (Stored as specific columns for query performance)
    total_return_pct NUMERIC,
    daily_return_pct NUMERIC,
    sharpe_ratio NUMERIC,
    max_drawdown_pct NUMERIC,
    win_rate NUMERIC,
    
    -- Full state and history as JSONB for flexibility
    metrics_json JSONB DEFAULT '{}'::jsonb,
    trade_history JSONB DEFAULT '[]'::jsonb,  -- Store recent history
    
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for analytics
CREATE INDEX IF NOT EXISTS idx_agent_state_last_updated ON competition.agent_state(last_updated);
