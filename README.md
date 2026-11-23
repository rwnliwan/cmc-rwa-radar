# RWA Radar — Tokenised-Equities Screener & Issuer-Spread Monitor

> One stock, many issuers, different prices. RWA Radar screens 4,812 tokenised
> equities on the CoinMarketCap RWA API and flags when the same stock costs
> different amounts depending on who issued the token.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Stdlib only](https://img.shields.io/badge/deps-stdlib%20only-green)](https://docs.python.org/3/library/)
[![Data](https://img.shields.io/badge/data-CoinMarketCap%20RWA%20API-orange)](https://coinmarketcap.com/api/real-world-assets-api/)

**Status: in build.** Milestone 24 Nov done — repo cleaned of the Base
prototype, `cmc_config.py` + `cmc_adapter.py` written, live API verification
passed (see [Live evidence](#live-evidence)). Coming next: `cmc_pipeline.py`
+ gate (25 Nov), CLI (26 Nov), dashboard (27 Nov), demo (28 Nov),
submission target **5 Dec 2026** (hard deadline 9 Dec 23:59 UTC).
Built for the **Build with CMC: API Hackathon, Round 2 — Real World Assets
track**. Read-only: no trading, no wallet, no private keys.

## What it does

- **Ranked board** — 4,812 tokenised stocks ordered by `rwa_rank`, with
  tokenised price, market cap and 24h volume from `assets/list`.
- **Issuer-spread monitor** — for one stock, the price of its token on each
  issuer (Backed, Ondo, Dinari, …) from `quotes/latest`'s `tokens[]`; the
  spread (max − min across priced tokens) is the signal. Same deviation
  know-how as our Exit Radar, with the issuer — not a DEX pool — as the
  comparison base.
- **Sparkline + % change** — computed from `quotes/historical` (daily, 30
  points), because the list/quotes responses carry no percent-change fields.
  Verdicts are honest monitor states — `OK` / `WATCH` / `NO_SIGNAL` — never
  investment advice.

## Live evidence

Live snapshot, **23 Nov 2026 ~12:44 WITA** (API key valid; calls made with
the real Pro API key, never committed):

| Check | Result |
|---|---|
| `map` NVDA | `rwa_id` 2, `rwa_rank` 5, `has_tokens` true — **0 credits** |
| `assets/list` (stock, top 5) | **4,812** tokenised stocks; AAPL (r2), MSFT (r3), GOOGL (r4), NVDA (r5), AMZN (r6) — **1 credit** |
| `quotes/latest` NVDA | avg tokenised price 133.88; `tokens[]` = **9 tokens, 8 priced, Dinari (`NVDA.D`) null** — **1 credit** |
| Issuer spread (NVDA) | **~0.58%** (max 134.41 WNVDAX / min 133.64 Robinhood NVDA) — above the experimental 0.5% watch threshold, i.e. this snapshot flags `issuer_spread_watch` |
| Total credits for the run | **2** |

Notes on the numbers: the spread moves with the market (0.576% → 0.586%
across two snapshots a minute apart), so every figure is timestamped.
`average_tokenized_price` (133.88) is **not** the plain mean of `tokens[]`
(mean of priced tokens: 133.94) — the spread is therefore computed from
`tokens[]` only, with the aggregate used as an independent reference.
A first design draft quoted a 0.086% spread; that came from a truncated
(`head -c 1500`) response showing only 4 of the 9 tokens. The corrected
fixture is recorded in `DESIGN-CMC-RWA.md` §3.3.

## How to run

Python 3.10+, standard library only — no `pip install`, no build step.

```bash
# 1. Put your CMC Pro API key in .env.local (see .env.local.example).
#    The key is read at runtime and never printed, logged or committed.
CMC_API_KEY=

# 2. Quick live check through the adapter (works today):
python3 -c "
import cmc_adapter as ad
print(ad.fetch_map(symbol='NVDA')['data']['rwa_assets'][0])
print(ad.fetch_quotes_latest(rwa_id=2)['data']['rwa_assets'][0]['tokens'])
"

# 3. CLI (lands 26 Nov):
python3 cmc_run.py board          # top-100 board -> out/cmc_snapshot.json
python3 cmc_run.py monitor --once # one monitor cycle (quotes 60 s, board 5 min)
python3 cmc_run.py asset NVDA     # detail: info + quotes + historical + issuers
```

## Endpoints used

| Endpoint | Used for | Credits |
|---|---|---|
| `map` | Resolve tickers → `rwa_id` | 0 |
| `assets/list` | Screener board (`asset_type=stock`, `sort=rwa_rank`) | 1 / 250 assets |
| `quotes/latest` | Monitor refresh — aggregates + `tokens[]` + `tradfi_markets[]` | 1 / 250 assets |
| `quotes/historical` | Sparkline + % change (`interval=daily`, `count=30`) | 1 / 100 points |
| `info` | Detail pane (company fields, About, logo, website) | 1 / 250 assets |
| `issuers/list` + `issuers` | Issuer roster + tokens per issuer | 1 / request |

**`market-pairs/list` is NOT used** — it is Growth+ only and is unavailable
on the hackathon's free Startup tier. The entry is built entirely on the
seven endpoints above.

## Credit budget

| Work (Startup tier, 450,000 credits/mo) | Per month |
|---|---|
| Board top-100 every 5 min | 8,640 |
| Watchlist quotes every 60 s (≤250 assets) | 43,200 |
| Historical, 20 assets × 30 points every 15 min | 17,280 |
| `info` / `issuers` on demand | ~150 |
| **Total** | **~69,270 (~15% of 450,000)** |

Fallback if the free Startup upgrade has not landed on the dashboard yet:
slow cadence ≈ **6,840/month**, under the Basic allowance. Switch with the
`CREDIT_MODE = "startup" | "basic"` flag in `cmc_config.py`, never by
editing code. (Dashboard showed 10,000 credits/mo, billing showed 15,000 —
the exact Basic figure is re-verified before relying on either.)

## Screenshots

Coming with the dashboard milestone (27 Nov) — no screenshots are faked
before the dashboard exists.

## What's new vs pre-existing

This entry is written fresh for this hackathon. The starting point was a
clone of our Exit Radar prototype for Base tokenised stocks (v0.3.3) — but
**every Base file was deleted from this repo** (code, docs, evidence,
fixtures, outputs; see `DESIGN-CMC-RWA.md` §4.2). Zero lines of Base code
were copied. What carries over is only **method know-how, expressed as
design**: the deviation method (compare independent prices of the same asset
and report the spread), reason codes instead of a 0–100 composite score,
offline gates from fixtures, canonical snapshots + hash, stdlib-only and
fail-closed discipline. All CMC code (`cmc_adapter.py`, `cmc_pipeline.py`,
`cmc_run.py`, `serve.py`, `dashboard/index.html`, `gate_cmc.py`,
`capture_cmc_evidence.py`, `cmc_config.py`) is written from scratch on the
CMC RWA research in `CMC-RWA-ENDPOINTS.md`. A standalone
`CMC_INTEGRATION.md` statement lands with the pipeline milestone; until
then, `DESIGN-CMC-RWA.md` §4.3 is the full record. This satisfies the
hackathon rule: *pre-existing projects are eligible only if the CMC
integration is new and clearly identified.*

## Submission links

- Hackathon: [Build with CMC: API Hackathon (Plushie), Round 2 — DoraHacks](https://dorahacks.io/hackathon/coinmarketcap-api-202611/detail)
- Demo video + post on X (#BuildwithCMC): pending (video 1–2 Dec, post with submission)
- Track: **Real World Assets** (one track per submission)
- Deadline: **9 Dec 2026 23:59 UTC** (10 Dec 08:00 WITA); our target: 5 Dec

## Limitations (honest)

- **Spread thresholds are experimental.** `SPREAD_WATCH_PCT = 0.5%` and
  `SPREAD_EXTREME_PCT = 2.0%` were guessed from a single observation and the
  full-token NVDA spread (~0.58%) already exceeds the watch line. Calibration
  needs a spread distribution across dozens of assets — post-submission work,
  not a claim in this README.
- **The aggregate is not the mean of `tokens[]`.** Verified live: average
  tokenised price ≠ mean of priced tokens. The aggregate is an independent
  reference only; the spread uses `tokens[]` alone.
- **Daily bars for stocks/ETFs start at midnight New York time**, not UTC.
  Do not align them with UTC daily bars from other sources.
- **Not investment advice.** Verdicts are monitor states (`OK` / `WATCH` /
  `NO_SIGNAL`) about price consistency across issuers and trend — nothing
  more.
- **Startup-tier upgrade pending.** As of 23 Nov the CMC dashboard still
  shows Basic; the slow-cadence fallback applies until the upgrade is
  confirmed.
