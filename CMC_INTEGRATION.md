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
| `cmc_run.py` | CLI: `board` / `monitor` / `asset` (milestone 26 Nov) |
| `serve.py` + `dashboard/index.html` | Local static dashboard (milestone 27 Nov) |
| `gate_cmc.py` | Offline gate from stored fixtures (checks 1–5 pass, 25 Nov) |
| `fixtures/cmc/` | Full live API responses captured 23 Nov 2026 (map, list, quotes, historical, issuers) |
| `evidence/cmc/` | Raw API responses + SHA-256 manifest (proof of real API calls) |

## Endpoints used (all on the free Startup tier granted for the event)

- `map` (0 credits) — resolve tickers to `rwa_id`
- `assets/list` — ranked board of 4,812 tokenised stocks
- `quotes/latest` — aggregates + per-issuer `tokens[]` (the spread source)
- `quotes/historical` — daily closes for sparkline + 24h/7d % change
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

None of that project's files, code, or data are in this repo. The Base
prototype files were deleted from this repo on 24 Nov 2026 (commit
`3d66aa5`); the originals remain in their own separate repo, untouched.

## Live evidence (captured 23 Nov 2026)

- `map` NVDA → `rwa_id` 2 (0 credits).
- `assets/list` stock → **4,812** tokenised stocks in total.
- `quotes/latest` NVDA → 9 tokens, 8 priced, Dinari price null;
  issuer spread **0.707%** at capture time (12:47 WITA), above the
  0.5% experimental watch threshold — the spread moves with the market
  (it was 0.576% at 12:44 WITA the same day), so the gate checks the
  pipeline against the stored fixture, never against a live number.
- `quotes/historical` NVDA daily × 30 → 24h change +1.23%, 7d change
  −19.58% from the stored closes.
- Full responses + SHA-256 manifest: `evidence/cmc/manifest.json`.

## Honest limitations

- The spread thresholds (0.5% watch / 2.0% extreme) are experimental
  guesses from a single observation — calibration needs a spread
  distribution across dozens of assets and is post-submission work.
- `average_tokenized_price` is an independent aggregate, not the mean of
  `tokens[]` — it is used only as the reference for per-token deviation,
  never as the spread denominator's assumed mean.
- Daily bars for stocks/ETFs start at midnight New York, not UTC.
- Read-only: no trading, no wallet, no investment recommendation.
