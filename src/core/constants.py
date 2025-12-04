"""
System-wide Constants.

Centralizes magic numbers and configuration values used across the trading system.
Created for Fix #10: Extract magic numbers to constants.
"""

# ===== Timeout & Timing Constants =====

# Orchestrator timeouts
PENDING_VALIDATION_TIMEOUT_SECONDS = 30  # Max time to wait for risk response
EXPIRED_VALIDATION_CHECK_INTERVAL_SECONDS = 1  # How often to check for expired validations

# Risk Manager timing
DRAWDOWN_CHECK_INTERVAL_SECONDS = 10  # How often to check portfolio drawdown
HEARTBEAT_TTL_SECONDS = 60  # Redis heartbeat time-to-live

# MCP Client
MCP_REQUEST_TIMEOUT_SECONDS = 30.0  # HTTP timeout for MCP calls
MCP_MAX_RETRIES = 3  # Maximum retry attempts for failed MCP calls
MCP_RETRY_MIN_WAIT_SECONDS = 1  # Minimum wait between retries
MCP_RETRY_MAX_WAIT_SECONDS = 10  # Maximum wait between retries

# Agent processing
AGENT_PROCESS_LOOP_SLEEP_MS = 100  # Yield time for agent main loops (milliseconds)
MAX_CONSECUTIVE_ERRORS = 5  # Max errors before agent stops

# ===== Trading Signal Constants =====

# Signal validity
SIGNAL_DEFAULT_TTL_SECONDS = 300  # Default time-to-live for trading signals (5 min)

# Confidence thresholds (Orchestrator)
DECISION_THRESHOLD = 0.65  # Min confidence for full execution
REDUCED_THRESHOLD = 0.50  # Min confidence for reduced execution (50% size)

# Technical Analysis
DEFAULT_ATR_MULTIPLIER_STOP = 2.0  # ATR multiplier for stop loss
DEFAULT_ATR_MULTIPLIER_TARGET = 3.0  # ATR multiplier for take profit
DEFAULT_ATR_FALLBACK_PCT = 0.02  # Fallback ATR as % of price if not available

# Signal confidence adjustments
CONFIDENCE_BOOST_HIGH_VOLUME = 0.05  # Boost for high volume
CONFIDENCE_BOOST_STRONG_TREND = 0.05  # Boost for ADX > 25
CONFIDENCE_MAX = 0.95  # Maximum allowed confidence

# Volume threshold
HIGH_VOLUME_MULTIPLIER = 1.5  # Volume must be 1.5x average

# ADX threshold
STRONG_TREND_ADX_THRESHOLD = 25  # ADX value for strong trend

# ===== Risk Management Constants =====
# Note: Risk limits are in src/core/risk_limits.py

# Position sizing
DEFAULT_RISK_PER_TRADE = 0.01  # Default risk per trade (1%)
KELLY_FRACTION_DEFAULT = 0.25  # Default Kelly criterion fraction (25%)
DEFAULT_STOP_DISTANCE_PCT = 0.02  # Default stop distance if none calculated

# Correlation
HIGH_CORRELATION_THRESHOLD = 0.5  # Threshold to trigger size reduction
CORRELATION_SIZE_REDUCTION_FACTOR = 0.7  # Reduce to 70% of original size

# Volatility regime
VOLATILITY_SIZE_REDUCTION_FACTOR = 0.5  # Reduce to 50% in high volatility

# Portfolio metrics
PORTFOLIO_VALUE_HISTORY_SIZE = 100  # How many historical values to keep for drawdown
SECTOR_WARNING_THRESHOLD_PCT = 0.30  # Warn when sector exposure > 30%

# ===== Redis Key Patterns =====

REDIS_KEY_PREFIX_HEARTBEAT = "agent:heartbeat:"  # Heartbeat key pattern
REDIS_KEY_PREFIX_POSITIONS = "positions"  # Current positions hash
REDIS_KEY_PORTFOLIO_CAPITAL = "portfolio:capital"  # Current capital
REDIS_KEY_PORTFOLIO_VALUE_HISTORY = "portfolio:value_history"  # Value history list
REDIS_KEY_AUDIT_DECISIONS = "audit:decisions"  # Decision audit log
REDIS_AUDIT_LOG_MAX_SIZE = 1000  # Max audit log entries to keep

# ===== Database Constants =====

# Sector cache
SECTOR_CACHE_DEFAULT_SIZE = 100  # Max symbols to cache in memory

# ===== Agent Weights (Orchestrator) =====
# Weights for weighted scoring when multiple analysts are active

WEIGHT_TECHNICAL_ANALYST = 0.40
WEIGHT_FUNDAMENTAL_ANALYST = 0.30  # Future implementation
WEIGHT_SENTIMENT_ANALYST = 0.30  # Future implementation

# ===== Exponential Backoff =====

BACKOFF_BASE = 2  # Base for exponential backoff
BACKOFF_MAX_SECONDS = 60  # Maximum backoff time

# ===== Logging =====

LOG_LEVEL_DEFAULT = "INFO"
LOG_FORMAT_JSON = True  # Use structured JSON logging
