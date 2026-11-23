# SUBMISSION — RWA Radar (Build with CMC: API Hackathon, Round 2)

- **Entry:** RWA Radar — Tokenised-Equities Screener & Issuer-Spread Monitor
- **Repo (public):** https://github.com/rwnliwan/cmc-rwa-radar
- **Track:** Real World Assets (one track per submission)
- **Hackathon page:** https://dorahacks.io/hackathon/coinmarketcap-api-202611/detail
- **Hard deadline:** 9 Dec 2026 23:59 UTC (10 Dec 08:00 WITA)
- **Our target:** submit 5 Dec 2026 (4-day buffer)
- **Status:** ready after DeepSeek review (23 Nov, READY AFTER FIXES,
  71/100) + the same-day recalibration and fix round, gate 10/10 PASS
  (23 Nov, live). Remaining: final review (Instinct) + submit 5 Dec.
  NOT submitted yet — submission and the X post need Septian's separate ACC.

## Submission checklist (DoraHacks)

| Item | Status |
|---|---|
| Public GitHub repo | ✅ https://github.com/rwnliwan/cmc-rwa-radar |
| Track selected | ✅ Real World Assets |
| Demo video | ✅ `demo/video-final.mp4` — 2:40 (160.00 s), 1280×800, H.264, silent, 20.3 MB (re-cut 23 Nov 20:34 WITA for the v0.2.0 recalibration) |
| Post on X (with video + link + #BuildwithCMC) | Draft ready below — post with the submission, after Septian's ACC |
| Endpoints used, named explicitly | ✅ See below |
| Proof of real API calls | ✅ `evidence/cmc/manifest.json` — raw responses + SHA-256 per file (5 credits, captured 23 Nov 2026 13:06 WITA) |
| Short project note | ✅ See "What it does" below |
| Originality | ✅ All CMC code written fresh for this hackathon; only method know-how (deviation + reason codes) carries over from our separate Exit Radar prototype — see `CMC_INTEGRATION.md` |

## What it does (short note for the form)

RWA Radar covers a universe of 4,812 tokenised equities on the
CoinMarketCap RWA API and flags when the same stock costs different
amounts depending on who issued the token. Three things: a ranked board
(by `rwa_rank`, top-N of the universe); an issuer-spread monitor (price
per token from `quotes/latest`'s `tokens[]` — the reported spread is
max − min across priced tokens, while decisions use a robust
(IQR/median) spread calibrated on the live board, so one stray token
cannot flag a whole asset); and sparkline + % change 24h/7d computed
from `quotes/historical`, because the list/quotes responses carry no
percent-change fields. Read-only: no trading, no wallet, no private
keys. Verdicts are honest monitor states — `OK` / `WATCH` / `NO_SIGNAL` —
never investment advice.

## Endpoints used (explicit, as required)

| Endpoint | Used for |
|---|---|
| `GET /v5/real-world-assets/map` | Resolve tickers → `rwa_id` (0 credits) |
| `GET /v5/real-world-assets/assets/list` | Screener board (`asset_type=stock`, `sort=rwa_rank`) |
| `GET /v5/real-world-assets/quotes/latest` | Monitor refresh — aggregates + `tokens[]` + `tradfi_markets[]` |
| `GET /v5/real-world-assets/quotes/historical` | Sparkline + % change (`interval=daily`, `count=30`) |
| `GET /v5/real-world-assets/info` | Detail pane (company fields) |
| `GET /v5/real-world-assets/issuers/list` + `issuers` | Issuer roster + tokens per issuer |

**`market-pairs/list` is NOT used** — it is Growth+ only and unavailable on
the hackathon's free Startup tier. The entry is built entirely on the seven
endpoints above. Credit budget (measured live by gate item 6): ~96/hour
scheduled + ~150/month on demand, ~69,270/month on the Startup cadence
(~15.4% of 450,000); ~6,840/month on the Basic fallback cadence.

## What the CMC API made possible — and where it got in the way

The RWA endpoints made this entry possible in a day: one `assets/list`
call returns the whole 4,812-stock universe with ranks, and `tokens[]`
inside `quotes/latest` exposes per-issuer prices that no other public API
we found publishes — the entire issuer-spread idea is just reading that
array honestly. Where it got in the way: `quotes/historical` is new
(18 Nov 2026) and returns no percent-change fields, so % change and
sparklines are computed client-side; `assets/list` returns rows with
`rwa_id: null` that cannot be quoted by id; and `market-pairs/list` —
the natural source for issuer-level liquidity — sits behind the Growth+
tier the hackathon grant does not include, so depth per issuer is out of
scope.

## Live evidence (numbers, all timestamped)

Captured 23 Nov 2026 13:06 WITA / 05:06 UTC by `capture_cmc_evidence.py`
(5 credits; see `evidence/cmc/manifest.json` for the SHA-256 of each raw
response):

- `map` NVDA → `rwa_id` 2, `rwa_rank` 5, `has_tokens` true — 0 credits.
- `assets/list` (stock) → **4,812** tokenised stocks.
- `quotes/latest` NVDA → `tokens[]` = 9 tokens, 8 priced, Dinari
  (`NVDA.D`) null; avg tokenised price 134.37; spread 0.652% at capture.
- Demo run (23 Nov 20:34 WITA): NVDA spread 0.312% (8 priced, 1 null),
  robust spread 0.150%, 24h +3.46%, 7d −17.07%; board top-10: 9 assets
  covered, 7 OK / 2 WATCH; AMZN 20.2%, SPCX 311.9% (mixed underlying);
  FGI (rwa_id 4379) honest `NO_SIGNAL` (`no_tokens`).
- The spread moves with the market (0.576% → 0.707% → 0.652% on 23 Nov),
  so every figure in the repo and video is timestamped.

## Honest limitations (stated in the README, not hidden)

- Spread decisions use a robust (IQR/median) spread with thresholds
  calibrated on the live board (WATCH > 0.5%, EXTREME > 1.0% — see
  README "How the spread is measured"); the reported max–min spread is
  still shown as-is.
- The max–min spread is dominated by single-token outliers (AMZN 20.6%
  and TSLA 43.8% via a Hyperliquid token far from the cluster; MU 28%
  and SKHY 10% via Backed "w…" tokens) — that is why it no longer
  decides; the robust spread does.
- SPCX mixes two underlyings in one `rwa_id` (10 tokens ~$131 plus
  SPACEX ~$531 and tSpaceX ~$512) — flagged `mixed_underlying` (any
  priced token >100% from the median), never silently trimmed.
- `assets/list` returns rows with `rwa_id: null` (GOOG + a duplicate
  BRK.B) — dropped with an explicit warning, counted only when covered.
- Startup-tier upgrade still pending on the CMC dashboard (Basic as of
  23 Nov); the slow-cadence fallback applies until confirmed.

## Draft post on X (ready to post with the submission)

> RWA Radar: one stock, many issuers, different prices. Our CMC hackathon
> entry covers a universe of 4,812 tokenised stocks and flags issuer
> spreads — NVDA 0.31%, SPCX 312% (mixed underlying). Built on the CMC
> RWA API. #BuildwithCMC https://dorahacks.io/hackathon/coinmarketcap-api-202611/detail

- Attach `demo/video-final-x.mp4` to the post (the X cut — same
  content, shorter holds; 2:18 / 137.63 s, under the 2:20 free-account
  cap, so no Premium is needed).
- Length: 254 characters by X's count (the URL counts as 23) — fits the
  280-character limit. No return/profit claims anywhere.
- **Video length:** the full video is 2:40 (160 s), per the design
  target of ±2–3 min. X free accounts cap video uploads at 2:20
  (140 s); the X cut below solves that. DoraHacks itself takes the
  2:40 file as-is — the cut only affects the X post.

## Demo video — how it was built

- File: `demo/video-final.mp4` — 2:40 (160.00 s exactly), 1280×800,
  30 fps, H.264 (yuv420p), silent, 20,304,196 bytes.
- Sources: 7 screenshots from the live demo run (`demo/run_demo.sh`,
  23 Nov 2026 20:34 WITA — the run `gate_cmc.py` item 8 performed
  during the recalibration fix round) + the 3 raw Playwright clips
  from that same run (`demo/shots/video/page@40c86f3c…` dashboard NVDA,
  `page@ecfcc4ae…` dashboard FGI, `page@e9cf95f7…` closing). The other
  19 `.webm` files in that directory are from older runs and were NOT
  used. **Re-cut note:** the first cut (13:14 WITA) showed the
  pre-recalibration board (0 OK / 9 WATCH); this cut shows the
  calibrated board (7 OK / 2 WATCH) and the new Robust column.
- Assembly: `demo/build_final_video.sh` (ffmpeg 8.1.2) — gentle zoom on
  800px shots, slow top-to-bottom pan on tall screenshots, title-card
  overlays rendered by `demo/make_title_cards.py` (PIL + DejaVu).
  Intermediates in `demo/segments/`; QA frames in `demo/qa-frames/`.
- Verified: duration 160.00 s, no black segments (blackdetect), QA
  frames read at t=5/25/55/65/80/100/115/135/152/159 — correct shot
  order, overlays readable, no empty frames. No voice-over (text
  overlays only, by design — no TTS/recording path was set up for this
  entry).
- X cut for the post: `demo/video-final-x.mp4` — 2:18 (137.63 s),
  1280×800, 30 fps, H.264 (yuv420p), silent, 17,419,776 bytes. Same
  sources and title cards, holds shortened (S1 14 s, S2 26 s, S3a
  board 12 s / detail 19 s, S3b detail 17 s, S4 28 s, S5 hold 16 s);
  built by `demo/build_x_cut.sh` (intermediates in `demo/segments-x/`,
  QA frames in `demo/qa-frames-x/`). Verified: no black segments, QA
  frames read at t=25 (CLI board), t=60 (NVDA detail), t=85 (FGI
  NO_SIGNAL), t=130 (closing + repo footer) — all correct, overlays
  readable, no token-like strings in the file. Made 23 Nov 2026 per
  Septian's decision to cut rather than use Premium.

## Remaining before submit

1. Final review (Instinct) + fix anything it finds.
2. Final gate: `gate_cmc.py` 10/10 PASS — done 23 Nov 2026 (live).
3. Confirm the Startup-tier upgrade on the CMC dashboard (or keep the
   Basic fallback cadence).
4. Submit on DoraHacks (target 5 Dec) + post on X with the video —
   both need Septian's explicit ACC at that point.
