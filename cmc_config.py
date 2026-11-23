"""RWA Radar — configuration for the CMC RWA API entry.

Written for the "Build with CMC: API Hackathon, Round 2" (Real World Assets
track). Python 3.10+ standard library only; this module holds NO secrets —
the API key lives in `.env.local` (gitignored) and is read by cmc_adapter.

Versions (schema / method / policy): v0.1.0 — see DESIGN-CMC-RWA.md §3.
"""

# ---------------------------------------------------------------------------
# API base + RWA endpoints (CoinMarketCap Pro API, /v5/real-world-assets/)
# Source: CMC-RWA-ENDPOINTS.md (docs checked 23 Nov 2026).
# market-pairs/list is deliberately NOT listed here: it is Growth+ only and
# is unavailable on the hackathon's free Startup tier — do not add it.
# ---------------------------------------------------------------------------

BASE_URL = "https://pro-api.coinmarketcap.com"

ENDPOINTS = {
    "map": "/v5/real-world-assets/map",
    "info": "/v5/real-world-assets/info",
    "assets_list": "/v5/real-world-assets/assets/list",
    "quotes_latest": "/v5/real-world-assets/quotes/latest",
    "quotes_historical": "/v5/real-world-assets/quotes/historical",
    "issuers_list": "/v5/real-world-assets/issuers/list",
    "issuers": "/v5/real-world-assets/issuers",
}

# HTTP behaviour (design §3.2 / §3.5)
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 1            # one retry, only for 429 / 5xx responses
RETRY_BACKOFF_SECONDS = 5
USER_AGENT = "RWA-Radar/0.1.0 (Build with CMC hackathon entry)"

# Key file (read at runtime only; never print its value, never commit it)
ENV_FILE = ".env.local"
ENV_KEY_NAME = "CMC_API_KEY"

# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------
SCHEMA_VERSION = "cmc-radar-schema v0.1.0"
METHOD_VERSION = "cmc-radar-method v0.1.0"
POLICY_VERSION = "cmc-radar-policy v0.1.0"

# ---------------------------------------------------------------------------
# Issuer-spread thresholds — EXPERIMENTAL, not calibrated.
# Set from a single live observation (NVDA spread 0.086% on 23 Nov 2026).
# Calibration needs a spread distribution across dozens of assets and is
# post-submission work. Do NOT present these as calibrated in the README/UI.
# ---------------------------------------------------------------------------
SPREAD_WATCH_PCT = 0.5    # EXPERIMENTAL — flag issuer_spread_watch
SPREAD_EXTREME_PCT = 2.0  # EXPERIMENTAL — flag issuer_spread_extreme

# ---------------------------------------------------------------------------
# Watchlist + board defaults
# ---------------------------------------------------------------------------
BOARD_ASSET_TYPE = "stock"
BOARD_SORT = "rwa_rank"
BOARD_LIMIT = 100          # top-100 board (1 page of assets/list)
WATCHLIST_SIZE = 20        # top-20 rwa_id by rank, plus any user ticker
HISTORICAL_COUNT = 30      # daily points for sparkline + % change
HISTORICAL_INTERVAL = "daily"

# ---------------------------------------------------------------------------
# Credit mode + cadence (design §3.4).
# "startup": hackathon grant — 450,000 credits/mo, 600 req/min.
# "basic":  fallback while the Startup upgrade has not landed on the
#           dashboard (Basic is 10,000 credits/mo on the dashboard, 15,000
#           on the billing page — re-verify the exact figure before relying
#           on either). Switch with the flag, never by editing code.
# ---------------------------------------------------------------------------
CREDIT_MODE = "startup"    # "startup" | "basic"

CADENCE = {
    "startup": {
        "board_seconds": 300,        # assets/list top-100 every 5 min
        "quotes_seconds": 60,        # quotes/latest watchlist every 60 s
        "historical_seconds": 900,   # historical every 15 min
        "historical_assets": 20,
        "budget_credits_per_month": 69270,  # ~15% of 450,000
    },
    "basic": {
        "board_seconds": 1800,       # every 30 min
        "quotes_seconds": 600,       # every 10 min
        "historical_seconds": 7200,  # every 2 h, 10 assets
        "historical_assets": 10,
        "budget_credits_per_month": 6840,   # under 10,000
    },
}

# Stale-data flags (design §3.3): quote older than this is labelled stale.
STALE_QUOTE_BOARD_SECONDS = 15 * 60
STALE_QUOTE_MONITOR_SECONDS = 5 * 60

# Daily bars for stocks/ETFs start at midnight NEW YORK time, not UTC —
# never align them with UTC daily bars from other sources (design §3.3).
HISTORICAL_DAY_START = "America/New_York midnight"
