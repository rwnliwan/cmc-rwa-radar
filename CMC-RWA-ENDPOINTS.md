# CMC RWA API Endpoints — Research Notes

- **Researched:** 23 Nov 2026 (public docs only; no sign-in, no API key used)
- **Purpose:** backbone data for the "Build with CMC: API Hackathon, Round 2" RWA-track entry — a tokenised-equities screener/monitor.
- **Sources (all live, checked 23 Nov 2026):**
  - RWA product page: https://coinmarketcap.com/api/real-world-assets-api/
  - Pro API reference, Real World Assets: https://coinmarketcap.com/api/documentation/pro-api-reference/real-world-assets
  - Changelog: https://coinmarketcap.com/api/documentation/changelog (v3.0.9, 18 Nov 2026; RWA launch, 7 Jul 2026)
  - Academy — "Real-World Assets Arrive on CoinMarketCap Pro API" (13 Jul 2026): https://coinmarketcap.com/academy/article/real-world-assets-rwas-arrive-coinmarketcap-pro-api
  - Academy — "How to Pull SpaceX Real-World Asset Data" (16 Jul 2026): https://coinmarketcap.com/academy/article/how-to-pull-spacex-real-world-asset-data-coinmarketcap-pro-api
  - Academy — "How to Look Up Tokenized Asset Issuers" (8 Sep 2026): https://coinmarketcap.com/api/resources/how-to-look-up-tokenized-asset-issuers-with-the-coinmarketcap-api/
  - Hackathon page: https://coinmarketcap.com/api/resources/api-hackathon-2026-11/

## At a glance

- **Universe:** ~7,800–7,937 tokenised RWAs (Academy says 7,937 at launch; product page says 7.8K+).
- **Asset types (6):** `stock` (tokenised equities), `commodity` (e.g. gold), `currency`, `government_security` (treasuries), `etf`, `real_estate`. Filter with `asset_type` on map/list calls.
- **Base URL:** `https://pro-api.coinmarketcap.com`
- **Auth:** API key in the `X-CMC_PRO_API_KEY` header on every request. RWA endpoints are **not** on the Keyless Public API — a key is required.
- **Response envelope:** standard CMC envelope — `data` + `status` (`timestamp`, `error_code`, `error_message`, `elapsed`, `credit_count`, `notice`); errors return `data: null` with non-zero `error_code`. Lists nest under `data.rwa_assets` with `total_size` / `has_more`. Times are ISO 8601.
- **Identifiers:** `rwa_id` (integer, stable primary key for the asset itself — use this, not the ticker); `rwa_slug`; `symbol`. Only **one identifier type per request** on map/info/list/quotes. `crypto_id` is the separate id of the underlying on-chain token (use it with the standard crypto endpoints). `issuer_id` is a 24-char hex string.
- **`rwa_rank`:** market-cap rank inside the RWA universe (separate from crypto `cmc_rank`); available as a sort on map and list.

## Endpoint inventory (8 total: 7 launched 7 Jul 2026 + 1 added 18 Nov 2026)

| # | Endpoint | Returns | Plans | Credit cost | Update freq |
|---|---|---|---|---|---|
| 1 | `GET /v5/real-world-assets/map` | ID map: every RWA asset → `rwa_id` (+ name, symbol, slug, `asset_type`, `rwa_rank`, `has_tokens`). No market data. | Basic+ | **0** | 30 s |
| 2 | `GET /v5/real-world-assets/info` | Static metadata: nominal + company fields + About block (description, logo, website). Equities add `employees`, `founded`, `industry`, `primary_exchange`, `cik` (null for non-equities). | Basic+ | 1 per 250 assets | 30 s |
| 3 | `GET /v5/real-world-assets/assets/list` | Paginated tracked assets **with tokenised aggregate quotes**. Defaults to `rwa_rank` ascending. | Basic+ | 1 per 250 assets | 1 min |
| 4 | `GET /v5/real-world-assets/quotes/latest` | Latest market data for named assets: tokenised aggregates + underlying tokens + TradFi markets. | Basic+ | 1 per 250 assets | 60 s |
| 5 | `GET /v5/real-world-assets/quotes/historical` | Time series of tokenised aggregates (avg price, mcap, 24h volume), one point per interval. **New in v3.0.9, 18 Nov 2026.** | Basic+ (window varies by plan) | 1 per 100 data points | 5 min |
| 6 | `GET /v5/real-world-assets/market-pairs/list` | All active markets CMC tracks for one asset's underlying tokens. | **Growth+ ONLY** | 1 per 250 pairs | 1 min |
| 7 | `GET /v5/real-world-assets/issuers/list` | Paginated issuers (e.g. Backed Finance, Paxos, Backpack, bStocks) with linked-token count. | Basic+ | 1 per request | 30 s |
| 8 | `GET /v5/real-world-assets/issuers` | One issuer by `issuer_id` + full list of tokens it issued (each with `crypto_id`, `rwa_id`, symbol, name). | Basic+ | 1 per request | 30 s |

Extra convert currencies beyond the first cost +1 credit each on list/quotes/historical. Pagination on list endpoints: `start` + `limit` (default 100, max 250).

### 1. RWA ID Map — `GET /v5/real-world-assets/map`
- **Required params:** none to list all; filter by `symbol`, `rwa_id`, or `rwa_slug` (one type only), and/or `asset_type`.
- **Key fields:** `rwa_id`, `name`, `symbol`, `slug`, `asset_type`, `rwa_rank`, `has_tokens`.
- **Notes:** free (0 credits) — the place to start; resolve tickers to `rwa_id` once, then use `rwa_id` everywhere. `sort` by `rwa_rank` available.

### 2. Metadata — `GET /v5/real-world-assets/info`
- **Required params:** at least one of `rwa_id`, `rwa_slug`, `symbol` (one type only).
- **Key fields:** nominal + company fields; About block (`description`, `logo`, `website`); equities: `employees`, `founded`, `industry`, `primary_exchange`, `cik`.
- **Notes:** 1 credit per 250 assets returned.

### 3. RWA List — `GET /v5/real-world-assets/assets/list`
- **Required params:** none (paginated; defaults `rwa_rank` asc). Optional: `asset_type`, `sort`, `start`, `limit`, `convert`/`convert_id` (up to 120 currencies).
- **Key fields:** per asset — identity fields plus tokenised aggregate quotes (`average_tokenized_price`, `tokenized_market_cap`, `tokenized_volume_24h`).
- **Notes:** the screener workhorse — one call returns a ranked, filterable page of equities with quotes. 1 credit per 250 assets.

### 4. Quotes Latest — `GET /v5/real-world-assets/quotes/latest`
- **Required params:** at least one of `rwa_id`, `rwa_slug`, `symbol` (one type only).
- **Key fields (per asset):** `average_tokenized_price`, `tokenized_market_cap`, `tokenized_volume_24h`; `tokens[]` (each: `symbol`, `name`, `price`, `crypto_id`, `market_cap`); `tradfi_markets[]`.
- **Notes:** 1 credit per 250 assets; up to 120 convert currencies. **No percent-change fields appear in the docs' example response** — a 24h change must be computed (e.g. from `quotes/historical` daily points) or read per-token via the standard crypto quotes endpoint. Verify live once the key exists.
- **Example (from docs, GOLD):** `average_tokenized_price` 4018.18, `tokenized_market_cap` 1,884,879,975, `tokenized_volume_24h` 139,285,845; tokens PAXG (price 4024.36, `crypto_id` 4705) and XAUM (4030.17, `crypto_id` 34212); `tradfi_markets: []`.

### 5. Quotes Historical — `GET /v5/real-world-assets/quotes/historical`
- **Required params:** at least one of `rwa_id`, `rwa_slug`, `symbol` (one type only). Optional: `time_start`, `time_end`, `count` (default 10), `interval` (`5m`–`365d`: `5m`/`15m`/`30m`/`45m`/`1h`…`12h`/`hourly`/`daily`/`weekly`/`monthly`/`yearly`/`1d`…`365d`), `convert`/`convert_id` (max 3).
- **Key fields:** per data point — first recorded value in the period, stamped at period start: average tokenised price, tokenised market cap, 24h tokenised volume. Daily+ periods start 00:00 UTC for commodities, midnight New York time for stocks/ETFs; weekly starts Monday, monthly on the 1st.
- **Limits:** history from 1 Jan 2020; max 10,000 data points per request (assets × periods); `hourly`/`1h`–`12h` reach back max 100 days, `5m`–`45m` max 10 days; `5m`–`45m` Enterprise only. Out-of-window request → `403` code `1014`.
- **Plan windows:** Basic — hourly 1 month, daily 1 year; Builder — hourly 1 month, daily 3 years; **Startup — hourly 1 month, daily from 2020**; Growth — hourly 3 months, daily from 2020; Professional/Enterprise — hourly 100 days, daily from 2020.
- **Credit:** 1 per 100 data points returned (rounded up, across all assets) + 1 per extra convert; 0 if no data points.
- **Notes:** this is the endpoint for sparklines, 24h/7d change computation, and deviation-vs-history features. Added 18 Nov 2026 — the product page FAQ still says "a historical endpoint is not among them", which is **stale**; the changelog + reference are authoritative.

### 6. Market Pairs — `GET /v5/real-world-assets/market-pairs/list`
- **Required params:** exactly one identifier (`rwa_id` / `rwa_slug` / `symbol`).
- **Key fields:** per pair — market/exchange, pair, `market_pair_quote` (quote currency, added v3.0.9).
- **⚠️ Plan gate: Growth, Professional, Enterprise ONLY. Not available on Startup — so NOT available with the hackathon's free Startup tier.** Do not design the entry around it; use `quotes/latest`'s `tokens[]` + `tradfi_markets[]` instead.

### 7. Issuers List — `GET /v5/real-world-assets/issuers/list`
- **Required params:** none. Optional: `start`, `limit`, `active` filter.
- **Key fields:** `issuer_id`, `name`, `website`, `logo`, `num_tokens`. Identity/roster only — no custody, audit, regulatory, or financial data.

### 8. Issuer — `GET /v5/real-world-assets/issuers`
- **Required params:** `issuer_id`.
- **Key fields:** issuer identity + `tokens[]` (each: `crypto_id`, `name`, `symbol`, `rwa_id`).
- **Notes:** the bridge from RWA → on-chain token → standard crypto endpoints (e.g. `/v2/cryptocurrency/quotes/latest?id=<crypto_id>` for a live single-token price).

## Plans, credits, rate limits

| Plan | Monthly credits | Req/min | Price (annual billing) |
|---|---|---|---|
| Basic (free) | 15,000 | 50 | $0 |
| Builder | 150,000 | 300 | $29/mo |
| **Startup (hackathon grant)** | **450,000** | **600** | $79/mo normally — **free for the event window** |
| Growth | 2,000,000 | 750 | $299/mo |
| Professional | 5,000,000 | 1,200 | $699/mo |

- The hackathon grants every participant the Startup tier for the event (upgrade applied to your own existing API key after DoraHacks registration with the matching CMC account email). 450k credits/mo is far more than a screener needs: e.g. a full 250-asset `assets/list` page costs 1 credit; a 250-asset `quotes/latest` refresh costs 1 credit; a 30-day daily history for 20 assets costs ~6 credits.
- **Sandbox / trial:** CMC has a sandbox API (`sandbox-api.coinmarketcap.com`) with **mock data** — explicitly not for real applications. There is also a Trial Pro API (`pro-api.coinmarketcap.com/trial-pro-api`) that works with no signup on a subset of endpoints. **Unverified whether RWA endpoints are in the trial subset** — do not assume; test only after the real key exists, or check the trial docs page.
- **Auth reminder:** key goes in the `X-CMC_PRO_API_KEY` header. Never commit a key to the public repo — the hackathon rules say a leaked key costs code-quality points and triggers a rotation request.

## Recommendation for the tokenised-equities screener/monitor

**Backbone (3 endpoints):**
1. **`/v5/real-world-assets/assets/list`** — the screener itself: `asset_type=stock`, sort by `rwa_rank`, paginate 250/page. One call = a ranked equities board with tokenised price/mcap/24h volume. 1 credit per page.
2. **`/v5/real-world-assets/quotes/latest`** — the monitor refresh: pass the watchlist's `rwa_id`s, get aggregates + per-token breakdown (`tokens[]` with `crypto_id` — this is also the bridge to per-token deviation vs the Radar/Base side) + `tradfi_markets[]`. 1 credit per 250 assets, 60 s refresh.
3. **`/v5/real-world-assets/quotes/historical`** — sparklines + computed % change (24h/7d) + deviation-vs-history. Daily interval, `count=30`, Startup window reaches back to 2020. ~1 credit per 100 points.

**Supporting (as needed):**
- `/v5/real-world-assets/map` (free) — resolve user-typed tickers to `rwa_id` at startup.
- `/v5/real-world-assets/info` — detail pane (company fields, About, `primary_exchange`, `cik`).
- `/v5/real-world-assets/issuers` + `/issuers/list` — "who issued this token" view (Backed, Backpack, bStocks…); cheap (1 credit/request).

**Do NOT build on:** `/v5/real-world-assets/market-pairs/list` (Growth+ only — unavailable on the hackathon Startup tier).

**Design notes / gotchas:**
- Aggregates are across all tokens representing an asset, not one wrapper — a tokenised NVDA price is the *average* across issuers; per-issuer prices live in `tokens[]`. A screener that shows issuer spread (max-min across `tokens[]`) is a genuine, cheap differentiator and maps to the Exit Radar "deviation" know-how.
- No percent-change in the aggregate quote example — compute it from `quotes/historical`, don't assume the field exists.
- `has_tokens: false` assets return empty `quotes` arrays — filter or handle them (they exist in map/list).
- Daily bars for stocks/ETFs start at midnight New York time, not UTC — mind this when aligning CMC daily history with Base/on-chain daily bars.
- `symbol` is not unique across asset types (e.g. SPCX is both the Nasdaq equity and the token) — always resolve via map and carry `rwa_id`.

## Minimal first API call (from the docs; key is a placeholder)

```bash
# 1. Resolve a ticker to rwa_id — free, 0 credits
curl -G 'https://pro-api.coinmarketcap.com/v5/real-world-assets/map' \
  --data-urlencode 'symbol=NVDA' \
  -H 'X-CMC_PRO_API_KEY: YOUR_API_KEY' \
  -H 'Accept: application/json'
# → { "data": { "rwa_assets": [ { "name": "Nvidia Corp", "symbol": "NVDA",
#     "slug": "nvidia", "rwa_id": 2, "asset_type": "stock",
#     "rwa_rank": 2, "has_tokens": true } ] } }

# 2. Latest quote for that asset (rwa_id=2) — 1 credit
curl -G 'https://pro-api.coinmarketcap.com/v5/real-world-assets/quotes/latest' \
  --data-urlencode 'rwa_id=2' \
  -H 'X-CMC_PRO_API_KEY: YOUR_API_KEY' \
  -H 'Accept: application/json'

# 3. Top tokenised equities board, one page — 1 credit
curl -G 'https://pro-api.coinmarketcap.com/v5/real-world-assets/assets/list' \
  --data-urlencode 'asset_type=stock' \
  --data-urlencode 'sort=rwa_rank' \
  --data-urlencode 'limit=250' \
  -H 'X-CMC_PRO_API_KEY: YOUR_API_KEY' \
  -H 'Accept: application/json'

# 4. 30-day daily history for NVDA — ~1 credit (30 points)
curl -G 'https://pro-api.coinmarketcap.com/v5/real-world-assets/quotes/historical' \
  --data-urlencode 'rwa_id=2' \
  --data-urlencode 'interval=daily' \
  --data-urlencode 'count=30' \
  -H 'X-CMC_PRO_API_KEY: YOUR_API_KEY' \
  -H 'Accept: application/json'
```

## Unclear / to verify once the API key exists

1. Whether `assets/list` and `quotes/latest` responses include percent-change fields (not in docs examples — likely absent; compute from historical).
2. Whether RWA endpoints are included in the no-signup Trial Pro API subset.
3. Exact `sort` values accepted by `assets/list` (only `rwa_rank` is documented; check for e.g. volume/market-cap sorts).
4. Whether the hackathon Startup grant carries the full 450k credits/mo + 600 req/min, or a reduced event allowance (confirm on the CMC account page after the key is upgraded).
5. The product-page FAQ claim "no historical endpoint" is stale (superseded by the 18 Nov 2026 changelog) — trust the reference, not the FAQ.
