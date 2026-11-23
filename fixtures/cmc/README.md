# Fixtures — live CMC RWA responses (23 Nov 2026)

Full, untruncated API responses captured with the real Pro API key via
`cmc_adapter.py` (capture script kept out of the repo). Each file is one
raw CMC envelope (`data` + `status`). No API key value appears in any
fixture — responses never echo the key.

## Files

| File | Endpoint | Captured (UTC) | Credits |
|---|---|---|---|
| `map-nvda.json` | `map?symbol=NVDA&asset_type=stock` | 2026-11-23T04:47:01Z | 0 |
| `list-stock-limit5.json` | `assets/list?asset_type=stock&sort=rwa_rank&limit=5` | 2026-11-23T04:47:01Z | 1 |
| `quotes-latest-nvda.json` | `quotes/latest?rwa_id=2` | 2026-11-23T04:47:01Z | 1 |
| `historical-nvda-daily30.json` | `quotes/historical?rwa_id=2&interval=daily&count=30` | 2026-11-23T04:47:03Z | 1 |
| `issuers-list.json` | `issuers/list?limit=10` | 2026-11-23T04:47:03Z | 1 |

Provenance per file (endpoint + timestamp + credit count) is also in
`MANIFEST.json`.

## Key facts from the quotes fixture (NVDA, rwa_id 2)

- `tokens[]`: **9 tokens, 8 priced, 1 null** — NVDA.D (Dinari Assets)
  has `price: null`. Priced: NVDAX (Backed), NVDAon (Ondo), NVDA
  (Derivatives), NVDAB (bStocks), rNVDA (Reality), NVDA (Robinhood),
  WNVDAX (Backed), NVDAc (Coinbase).
- `average_tokenized_price`: 134.016057984008 (independent aggregate —
  NOT the mean of `tokens[]`).
- Issuer spread: max 134.51060298881225 (WNVDAX) − min 133.56285444645067
  (rNVDA) = **0.9477485423615803** → **0.7071902849691895%** — above the
  0.5% experimental watch threshold.
- `assets/list` stock `total_size`: **4,812**.

## Why the fixture spread (0.707%) differs from the design's 0.576%

The design's 0.576% came from a live snapshot at **12:44 WITA** the same
day; this fixture was captured at **12:47 WITA** and the spread had
already moved to 0.707%. The spread is a live market quantity — it moves
minute to minute. The gate (`gate_cmc.py` item 2) therefore checks the
pipeline against THIS stored fixture (recomputed independently from its
own `tokens[]`), never against the 12:44 number and never against a new
live call with a tight tolerance.

## Historical fixture (NVDA daily × 30)

- 30 daily-period observations, first 2026-10-24T04:00:00Z, last
  2026-11-22T05:00:00Z (daily bars start at midnight New York). Each
  observation is the first value in its period, not a close.
- Change vs previous daily-period observation (2026-11-21 to
  2026-11-22): **+1.2315275663880885%**; change vs 7 periods back
  (2026-11-15 to 2026-11-22): **−19.581406622751192%** (computed from
  the stored observations; the gate re-derives both).
