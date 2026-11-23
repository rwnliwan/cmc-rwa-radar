# RWA Radar — Tokenised-Equities Screener & Issuer-Spread Monitor

> One stock, many issuers, different prices. RWA Radar screens 4,812 tokenised
> equities on the CoinMarketCap RWA API and flags when the same stock costs
> different amounts depending on who issued the token.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Stdlib only](https://img.shields.io/badge/deps-stdlib%20only-green)](https://docs.python.org/3/library/)
[![Data](https://img.shields.io/badge/data-CoinMarketCap%20RWA%20API-orange)](https://coinmarketcap.com/api/real-world-assets-api/)

**Status: feature-complete.** Milestones 24–30 Nov done — repo cleaned of the
Base prototype, adapter + pipeline + gate, CLI (board/monitor/asset),
dashboard, demo run, edge cases, measured credit budget, evidence manifest.
Gate `gate_cmc.py` **9/9 PASS** (23 Nov 2026, live). Next: final video +
`SUBMISSION.md` (1–2 Dec), submission target **5 Dec 2026** (hard deadline
9 Dec 23:59 UTC). Built for the **Build with CMC: API Hackathon, Round 2 —
Real World Assets track**. Read-only: no trading, no wallet, no private keys.

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

Real API calls, captured **23 Nov 2026 13:06 WITA / 05:06 UTC** by
`capture_cmc_evidence.py` (raw envelopes + SHA-256 manifest in
[`evidence/cmc/manifest.json`](evidence/cmc/manifest.json)):

| Check | Result |
|---|---|
| `map` NVDA | `rwa_id` 2, `rwa_rank` 5, `has_tokens` true — **0 credits** |
| `assets/list` (stock, top 5) | **4,812** tokenised stocks; AAPL (r2), MSFT (r3), GOOGL (r4), NVDA (r5), AMZN (r6) — **1 credit** |
| `quotes/latest` NVDA | avg tokenised price 134.37; `tokens[]` = **9 tokens, 8 priced, Dinari (`NVDA.D`) null** — **1 credit** |
| Issuer spread (NVDA) | **0.652%** at capture (max 134.41 WNVDAX / min 133.64 Robinhood NVDA) — above the experimental 0.5% watch threshold |
| `quotes/historical` NVDA | 30 daily closes — **1 credit** |
| `info` NVDA | company fields — **1 credit** |
| `issuers/list` | roster — **1 credit** |
| **Total for the capture** | **5 credits** |

Notes on the numbers: the spread moves with the market (0.576% at 12:44 →
0.707% at 12:47 → 0.652% at 13:06 WITA the same day), so every figure is
timestamped and the gate checks the pipeline against a stored fixture,
never against a live number. `average_tokenized_price` (134.37) is **not**
the plain mean of `tokens[]` — the spread is therefore computed from
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

# 2. Board (top-25 by rwa_rank) -> out/cmc_snapshot.json
python3 cmc_run.py board
python3 cmc_run.py board --limit 100

# 3. Monitor the watchlist (top-20 + optional ticker), 3 cycles
python3 cmc_run.py monitor --cycles 3
python3 cmc_run.py monitor --ticker AAPL

# 4. One asset in detail: info + tokens[] + spread + % change + sparkline
python3 cmc_run.py asset NVDA
python3 cmc_run.py asset 9        # SPCX by rwa_id

# 5. Dashboard (local only, serves the latest snapshot)
python3 serve.py                  # http://127.0.0.1:8000/

# 6. Capture raw API evidence (5 credits) + SHA-256 manifest
python3 capture_cmc_evidence.py   # -> evidence/cmc/manifest.json

# 7. Gate (9 items; live items cost ~38 credits per full run)
python3 gate_cmc.py
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

## Credit budget — measured live, not assumed

Per-call costs measured by `gate_cmc.py` item 6 (23 Nov 2026, live):
`assets/list` top-100 = **1** credit; `quotes/latest` 20 ids = **1**;
`quotes/historical` 20 ids × 30 points = **6** (600 points / 100);
10 ids × 30 = **3**. Projected from those measured numbers and the
configured Startup cadence (board 5 min, quotes 60 s, historical 15 min):

| Work (Startup tier, 450,000 credits/mo) | Per hour | Per month |
|---|---|---|
| Board top-100 every 5 min | 12 | 8,640 |
| Watchlist quotes every 60 s (≤250 assets) | 60 | 43,200 |
| Historical, 20 assets × 30 points every 15 min | 24 | 17,280 |
| `info` / `issuers` on demand | — | ~150 |
| **Total** | **96 (≤ 100)** | **~69,270 (~15.4% of 450,000)** |

Fallback if the free Startup upgrade has not landed on the dashboard yet:
slow cadence ≈ **6,840/month**, under the Basic allowance. Switch with the
`CREDIT_MODE = "startup" | "basic"` flag in `cmc_config.py`, never by
editing code. (Dashboard showed 10,000 credits/mo, billing showed 15,000 —
the fallback is sized against the conservative 10,000 figure.)

## Screenshots

Real captures from the demo run (`demo/run_demo.sh`, 23 Nov 2026 — live
CLI output and the local dashboard, no mock data):

![Dashboard board](demo/shots/shot-3-dashboard-board.png)

*Board — top-10 stocks by `rwa_rank`, spread and decision per asset.*

![Dashboard detail — NVDA](demo/shots/shot-3-detail-nvda.png)

*Detail pane — NVDA: price per issuer, spread, % change and sparkline.*

![Dashboard detail — NO_SIGNAL](demo/shots/shot-3b-detail-nosignal.png)

*Detail pane — an asset with no tokens: an honest `NO_SIGNAL`, no invented
numbers. Terminal captures of the CLI (shots 1–2) and the evidence
manifest (shot 4) are in `demo/shots/`.*

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
CMC RWA research in `CMC-RWA-ENDPOINTS.md`. See `CMC_INTEGRATION.md` for
the full statement. This satisfies the hackathon rule: *pre-existing
projects are eligible only if the CMC integration is new and clearly
identified.*

## Submission links

- Hackathon: [Build with CMC: API Hackathon (Plushie), Round 2 — DoraHacks](https://dorahacks.io/hackathon/coinmarketcap-api-202611/detail)
- Demo video + post on X (#BuildwithCMC): pending (video 1–2 Dec, post with submission)
- Track: **Real World Assets** (one track per submission)
- Deadline: **9 Dec 2026 23:59 UTC** (10 Dec 08:00 WITA); our target: 5 Dec

## Limitations (honest)

- **Spread thresholds are experimental.** `SPREAD_WATCH_PCT = 0.5%` and
  `SPREAD_EXTREME_PCT = 2.0%` were guessed from a single observation and the
  full-token NVDA spread (~0.65%) already exceeds the watch line. Calibration
  needs a spread distribution across dozens of assets — post-submission work,
  not a claim in this README.
- **The max–min spread is dominated by single-token outliers.** On a live
  board run (23 assets covered), 22 flag WATCH, almost always because of one
  token: AMZN 20.6% and TSLA 43.8% (Hyperliquid token far from the cluster),
  MU 28% and SKHY 10% (Backed "w…" tokens). A robust-outlier metric
  (median/deviation) is post-submission work; until then the spread is
  reported as-is and the outlier is visible in the tokens table.
- **Mixed underlying (SPCX).** `tokens[]` for SPCX mixes two different
  instruments: 10 tokens ~$131 plus SPACEX (PreStocks) ~$531 and tSpaceX
  (Tessera) ~$512 — spread 305%. The pipeline flags this with reason code
  `mixed_underlying` (any priced token >50% from the median priced token)
  and lists the outlier tokens; the spread is NOT silently trimmed, so the
  305% is shown and explained, not hidden.
- **`assets/list` returns rows with `rwa_id: null`.** In the live top-20,
  GOOG and a duplicate BRK.B row carry no `rwa_id` and cannot be quoted by
  id — the CLI drops them with an explicit stderr warning and counts only
  the covered assets (re-verified live by gate item 4, 23 Nov 2026).
- **The aggregate is not the mean of `tokens[]`.** Verified live: average
  tokenised price ≠ mean of priced tokens. The aggregate is an independent
  reference only; the spread uses `tokens[]` alone.
- **Daily bars for stocks/ETFs start at midnight New York time**, not UTC.
  Do not align them with UTC daily bars from other sources.
- **Sparkline only when historical data exists.** Board snapshots carry no
  historical closes, so the dashboard says so honestly instead of drawing
  a chart from missing data; run `cmc_run.py asset <symbol>` (or
  `monitor`, which refreshes historical every 15 min) for a snapshot with
  a sparkline.
- **Startup-tier upgrade pending.** As of 23 Nov the CMC dashboard still
  shows Basic; the slow-cadence fallback applies until the upgrade is
  confirmed.
- **Not investment advice.** Verdicts are monitor states (`OK` / `WATCH` /
  `NO_SIGNAL`) about price consistency across issuers and trend — nothing
  more.
