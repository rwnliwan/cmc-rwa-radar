"""RWA Radar — configuration for the CMC RWA API entry.

Written for the "Build with CMC: API Hackathon, Round 2" (Real World Assets
track). Python 3.10+ standard library only; this module holds NO secrets —
the API key lives in `.env.local` (gitignored) and is read by cmc_adapter.

Versions (schema / method / policy): v0.3.0 — see DESIGN-CMC-RWA.md §3.
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
# Versions (bumped 23 Nov 2026 follow-up round: v0.3.0 = binary flag —
# one threshold instead of WATCH/EXTREME; per-issuer deviation from the
# median in every token entry. v0.2.0 was the robust spread metric +
# empirical thresholds + new decision rules; v0.1.0 was the max-min-only
# metric with guessed thresholds)
# ---------------------------------------------------------------------------
SCHEMA_VERSION = "cmc-radar-schema v0.4.0"
METHOD_VERSION = "cmc-radar-method v0.4.0"
POLICY_VERSION = "cmc-radar-policy v0.1.0"

# ---------------------------------------------------------------------------
# Issuer-spread threshold — an EXPLORATORY HEURISTIC, not a validated
# threshold. v0.3.0 removed the second cut point (EXTREME 1.0%): a
# sample of n=23 assets from one live snapshot cannot defend two cut
# points, so the decision is now binary — flagged or not flagged.
# Measured from the live top-25 board (n=23 covered, 23 Nov 2026
# 20:23 WITA): robust-spread median 0.265%, p75 0.440%, p90 0.924%
# (linear interpolation — see calibration/recompute_calibration.py,
# which reproduces every number here from the stored snapshot,
# including the 18 OK / 5 WATCH counts and the v0.2.0-vs-v0.3.0
# equivalence on that frozen input). The 0.5% line sits at ~p83 of
# that board (19 of 23 assets at or below it). It is NOT a
# statistically validated anomaly threshold, risk score or trading
# signal — re-measure on a larger sample before calling it
# calibrated. The threshold applies to ROBUST_SPREAD_PCT
# (IQR/median, below), NOT to the raw max-min spread_pct, which is
# still reported as-is.
# ---------------------------------------------------------------------------
ROBUST_SPREAD_FLAG_PCT = 0.5

# Mixed-underlying detection (EXPERIMENTAL, added 23 Nov 2026; line
# raised 50% -> 100% in the 23 Nov 2026 recalibration): a priced token
# whose price deviates from the MEDIAN priced token by more than this
# is flagged as a SUSPECTED comparability issue (mapping, unit,
# freshness or instrument differences are all possible — price alone
# does not establish a different underlying; live case: SPCX — 10
# tokens ~$131 plus SPACEX PreStocks ~$531 and tSpaceX ~$512, spread
# 305%). The token is NEVER dropped from the spread — it is flagged
# with reason code `mixed_underlying` and listed in the snapshot, so
# the extreme spread is shown, not hidden.
# 100% is the "suspected different instrument" line: ordinary issuer
# outliers seen live (AMZN Hyperliquid -20%, TSLA -44%, MU +28% from
# the median) stay far below it; SPCX outliers sit 290-304% above it.
MIXED_UNDERLYING_MEDIAN_DEVIATION_PCT = 100.0

# ---------------------------------------------------------------------------
# Watchlist + board defaults
# ---------------------------------------------------------------------------
BOARD_ASSET_TYPE = "stock"
BOARD_SORT = "rwa_rank"
BOARD_LIMIT = 100          # assets/list page size used by the budget
                           # measurement (gate item 6) — NOT the CLI
                           # board default (25, see cmc_run.py).
WATCHLIST_SIZE = 20        # top-20 rwa_id by rank, plus any user ticker
HISTORICAL_COUNT = 30      # daily-period observations for sparkline +
                           # % change (each is the FIRST value in its
                           # period, not a close)
HISTORICAL_INTERVAL = "daily"

# ---------------------------------------------------------------------------
# Credit mode + cadence (design §3.4).
# "startup": hackathon grant — 450,000 credits/mo, 600 req/min.
# "basic":  fallback while the Startup upgrade has not landed on the
#           dashboard (Basic is 10,000 credits/mo on the dashboard, 15,000
#           on the billing page — re-verify the exact figure before relying
#           on either). Switch with the flag, never by editing code.
# DEFAULT IS "basic": the dashboard still showed Basic on 23 Nov 2026
# and the Startup upgrade is unconfirmed — shipping the Startup cadence
# as the default would burn a Basic allowance (or hit 429s) for anyone
# running the entry as-is. Flip to "startup" once the upgrade is
# confirmed on the dashboard.
# ---------------------------------------------------------------------------
CREDIT_MODE = "basic"    # "startup" | "basic"

CADENCE = {
    "startup": {
        "board_seconds": 300,        # assets/list top-100 every 5 min
        "quotes_seconds": 60,        # quotes/latest watchlist every 60 s
        "historical_seconds": 900,   # historical every 15 min
        "historical_assets": 20,
        # 96/hr scheduled (12 board + 60 quotes + 24 historical) x 720h
        # = 69,120, + ~150/month on-demand info/issuers = 69,270.
        # historical_assets is ENFORCED by cmd_monitor (the historical
        # request is sliced to this many ids) — the budget below is
        # derived from that capped request path, not assumed. With
        # the cap ignored (20 ids in Basic too) the Basic total would
        # be 7,920/month; the cap is what keeps it at 6,840.
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
