# CMC Integration — What Is New in This Entry

**Entry:** RWA Radar — Tokenised-Equities Screener & Issuer-Spread Monitor
**Track:** Real World Assets (Build with CMC: API Hackathon, Round 2)
**Repo:** https://github.com/rwnliwan/cmc-rwa-radar

## What is new — built for this hackathon

Every line of code in this repo was written for this hackathon, on top of
the CoinMarketCap RWA API. No `.py` file from any earlier project was
copied into this repo — the modules were written from scratch against the
RWA endpoint research in `CMC-RWA-ENDPOINTS.md`:

| File | What it does |
|---|---|
| `cmc_config.py` | RWA endpoints, watchlist, spread thresholds, credit cadence |
| `cmc_adapter.py` | The only module that talks to CMC (`/v5/real-world-assets/`) |
| `cmc_pipeline.py` | Issuer spread from `tokens[]`, % change from `quotes/historical`, reason codes, canonical snapshot + `snapshot_id` |
| `cmc_run.py` | CLI: `board` / `monitor` / `asset` (23 Nov 2026) |
| `serve.py` + `dashboard/index.html` | Local static dashboard (23 Nov 2026) |
| `gate_cmc.py` | Offline gate from stored fixtures + live checks 1–9 (all pass, 23 Nov 2026) |
| `capture_cmc_evidence.py` | Captures raw API responses + SHA-256 manifest (23 Nov 2026) |
| `fixtures/cmc/` | Full live API responses captured 23 Nov 2026 (map, list, quotes, historical, issuers) |
| `evidence/cmc/` | Raw API responses + SHA-256 manifest (proof of real API calls — captured 23 Nov 2026 13:06 WITA, 5 credits) |

## Endpoints used (all on the free Startup tier granted for the event)

- `map` (0 credits) — resolve tickers to `rwa_id`
- `assets/list` — ranked board of 4,812 tokenised stocks
- `quotes/latest` — aggregates + per-issuer `tokens[]` (the spread source)
- `quotes/historical` — daily-period observations (each the first value
  in its period, not a close) for sparkline + % change between the
  available daily-period observations, labelled with their actual dates
- `info` — company fields for the detail pane
- `issuers/list` + `issuers` — issuer roster and per-issuer tokens

`market-pairs/list` is deliberately NOT used — it is Growth+ only and is
unavailable on the hackathon's Startup tier.

## What is reused — method only, not code

The author previously built an unrelated read-only monitor ("Exit Radar"
for tokenised stocks on Base, repo separate, not part of this submission).
What carries over is **know-how as design, not code**:

- The deviation method: compare independent prices of the same asset and
  report the spread + per-source deviation. There the sources were DEX
  pools; here they are issuers (`tokens[]` in `quotes/latest`). The spread
  formula in `cmc_pipeline.py` was written new for the `tokens[]` shape.
- The discipline of reason codes instead of a composite 0–100 score, and
  honest monitor states (OK / WATCH / NO_SIGNAL) with no investment
  advice.
- The offline gate from stored fixtures, canonical snapshots with a
  `snapshot_id` hash, and fail-closed behaviour on API errors.

None of that project's files, code, or data are in this repo. The full
history, stated plainly: development began from a copy of our earlier
Base prototype repo; its inherited files were removed before this CMC
implementation was written; we subsequently rebuilt the published
history (23 Nov 2026, rebase --root) to exclude that initial imported
tree. The current history is therefore not an untouched record of the
starting repository — it starts from the CMC implementation (the
equivalent of the old cleanup commit is now `b29cde0` in the rebuilt
history). This is a history statement, not an eligibility claim: what
makes this entry eligible is that the CMC integration is new and
clearly identified — every module above was written fresh for the CMC
RWA API. The originals of the Base prototype remain in their own
separate repo, untouched.

## Live evidence (captured 23 Nov 2026)

- `map` NVDA → `rwa_id` 2 (0 credits).
- `assets/list` stock → **4,812** tokenised stocks in total.
- `quotes/latest` NVDA → 9 tokens, 8 priced, Dinari price null;
  issuer spread **0.652%** at the evidence capture (13:06 WITA) — the
  spread moves with the market (0.576% at 12:44, 0.707% at the 12:47
  fixture capture, 0.652% at 13:06), so the gate checks the pipeline
  against the stored fixture, never against a live number.
- `quotes/historical` NVDA daily × 30 → change vs previous
  daily-period observation (2026-11-21 to 2026-11-22) +1.23%, change
  vs 7 periods back (2026-11-15 to 2026-11-22) −19.58%, from the
  stored daily-period observations.
- Full responses + SHA-256 manifest: `evidence/cmc/manifest.json`
  (6 files, 5 credits, captured 2026-11-23T05:06:43Z by
  `capture_cmc_evidence.py`).
- Credit budget, measured live by gate item 6: `assets/list` 1 credit,
  `quotes/latest` (20 ids) 1 credit, `quotes/historical` (20 ids × 30)
  6 credits, (10 ids × 30) 3 credits → **96 credits/hour** projected
  for the Startup cadence, **~69,270/month (~15.4% of 450,000)**;
  Basic fallback **~6,840/month** (under the 10,000 dashboard figure).

## Honest limitations

- The spread flag (robust spread > 0.5%) is an exploratory heuristic
  from one live snapshot (n = 23 assets, 23 Nov 2026 — median 0.265%,
  p75 0.440%, p90 0.924%, reproduced in
  `calibration/recompute_calibration.py`). It is not a statistically
  validated anomaly threshold, risk score or trading signal.
- `average_tokenized_price` is an independent aggregate, not the mean of
  `tokens[]` — it is used only as the reference for per-token deviation,
  never as the spread denominator's assumed mean.
- **The max–min spread is dominated by single-token outliers** (AMZN
  20.6%, TSLA 43.8% from a Hyperliquid token; MU 28%, SKHY 10% from
  Backed "w…" tokens) — on a live 23-asset board the old max-min method
  flagged 22/23 WATCH; the robust flag reads 15 OK / 8 WATCH.
- **Mixed underlying (SPCX):** `tokens[]` mixes what looks like two
  different instruments (10 tokens ~$131 plus SPACEX ~$531 and tSpaceX
  ~$512, spread 305%). The pipeline flags this with reason code
  `mixed_underlying` and lists the outlier tokens; the spread is never
  silently trimmed. The flag means suspected comparability issue, not
  proof of a different underlying: price alone does not establish a
  different instrument — mapping, unit, freshness or instrument
  differences are all possible.
- **`assets/list` returns rows with `rwa_id: null`** (GOOG + a duplicate
  BRK.B row in the live top-20) — dropped with an explicit warning,
  never counted as covered.
- Daily bars for stocks/ETFs start at midnight New York, not UTC.
- Read-only: no trading, no wallet, no investment recommendation.
