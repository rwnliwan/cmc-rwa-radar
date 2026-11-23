# SUBMISSION — RWA Radar (Build with CMC: API Hackathon, Round 2)

- **Entry:** RWA Radar — Tokenised-Equities Screener & Issuer-Spread Monitor
- **Repo (public):** https://github.com/rwnliwan/cmc-rwa-radar
- **Track:** Real World Assets (one track per submission)
- **Hackathon page:** https://dorahacks.io/hackathon/coinmarketcap-api-202611/detail
- **Hard deadline:** 9 Dec 2026 23:59 UTC (10 Dec 08:00 WITA)
- **Our target:** submit 5 Dec 2026 (4-day buffer)
- **Status:** ready to submit after the 3–4 Dec review + final gate (10/10).
  NOT submitted yet — submission and the X post need Septian's separate ACC.

## Submission checklist (DoraHacks)

| Item | Status |
|---|---|
| Public GitHub repo | ✅ https://github.com/rwnliwan/cmc-rwa-radar |
| Track selected | ✅ Real World Assets |
| Demo video | ✅ `demo/video-final.mp4` — 2:40 (160.00 s), 1280×800, H.264, silent, 20.7 MB |
| Post on X (with video + link + #BuildwithCMC) | Draft ready below — post with the submission, after Septian's ACC |
| Endpoints used, named explicitly | ✅ See below |
| Proof of real API calls | ✅ `evidence/cmc/manifest.json` — raw responses + SHA-256 per file (5 credits, captured 23 Nov 2026 13:06 WITA) |
| Short project note | ✅ See "What it does" below |
| Originality | ✅ All CMC code written fresh for this hackathon; only method know-how (deviation + reason codes) carries over from our separate Exit Radar prototype — see `CMC_INTEGRATION.md` |

## What it does (short note for the form)

RWA Radar screens 4,812 tokenised equities on the CoinMarketCap RWA API
and flags when the same stock costs different amounts depending on who
issued the token. Three things: a ranked board (by `rwa_rank`); an
issuer-spread monitor (price per token from `quotes/latest`'s `tokens[]`,
spread = max − min across priced tokens); and sparkline + % change 24h/7d
computed from `quotes/historical`, because the list/quotes responses carry
no percent-change fields. Read-only: no trading, no wallet, no private
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
endpoints above. Credit budget (measured live by gate item 6): ~96/hour,
~69,270/month on the Startup cadence (~15.4% of 450,000); ~6,840/month on
the Basic fallback cadence.

## Live evidence (numbers, all timestamped)

Captured 23 Nov 2026 13:06 WITA / 05:06 UTC by `capture_cmc_evidence.py`
(5 credits; see `evidence/cmc/manifest.json` for the SHA-256 of each raw
response):

- `map` NVDA → `rwa_id` 2, `rwa_rank` 5, `has_tokens` true — 0 credits.
- `assets/list` (stock) → **4,812** tokenised stocks.
- `quotes/latest` NVDA → `tokens[]` = 9 tokens, 8 priced, Dinari
  (`NVDA.D`) null; avg tokenised price 134.37; spread 0.652% at capture.
- Demo run (23 Nov 13:14 WITA): NVDA spread 0.391% (8 priced, 1 null),
  24h +3.46%, 7d −17.07%; board top-10: 9 assets covered, 0 OK / 9 WATCH;
  AMZN 20.6%, SPCX 304.9% (mixed underlying); FGI (rwa_id 4379) honest
  `NO_SIGNAL` (`no_tokens`).
- The spread moves with the market (0.576% → 0.707% → 0.652% on 23 Nov),
  so every figure in the repo and video is timestamped.

## Honest limitations (stated in the README, not hidden)

- Spread thresholds (0.5% WATCH / 2.0% EXTREME) are **experimental** —
  guessed from a single observation, uncalibrated.
- The max–min spread is dominated by single-token outliers (AMZN 20.6%
  and TSLA 43.8% via a Hyperliquid token far from the cluster; MU 28%
  and SKHY 10% via Backed "w…" tokens).
- SPCX mixes two underlyings in one `rwa_id` (10 tokens ~$131 plus
  SPACEX ~$531 and tSpaceX ~$512) — flagged `mixed_underlying`, never
  silently trimmed.
- `assets/list` returns rows with `rwa_id: null` (GOOG + a duplicate
  BRK.B) — dropped with an explicit warning, counted only when covered.
- Startup-tier upgrade still pending on the CMC dashboard (Basic as of
  23 Nov); the slow-cadence fallback applies until confirmed.

## Draft post on X (ready to post with the submission)

> RWA Radar: one stock, many issuers, different prices. Our CMC hackathon
> entry screens 4,812 tokenised stocks and flags issuer spreads — NVDA
> 0.39%, SPCX 305% (mixed underlying). Built on the CMC RWA API.
> #BuildwithCMC https://dorahacks.io/hackathon/coinmarketcap-api-202611/detail

- Attach `demo/video-final.mp4` to the post.
- Length: 241 characters by X's count (the URL counts as 23) — fits the
  280-character limit. No return/profit claims anywhere.
- ⚠️ **Video length vs X free accounts:** the video is 2:40 (160 s),
  per the design target of ±2–3 min. X free accounts cap video uploads
  at 2:20 (140 s); Premium allows longer. If posting from a free
  account, either post from Premium or ask for a trimmed ≤140 s cut
  (easy to make: shorten the shot-3 holds in `demo/build_final_video.sh`).
  DoraHacks itself takes the file as-is — this only affects the X post.

## Demo video — how it was built

- File: `demo/video-final.mp4` — 2:40 (160.00 s exactly), 1280×800,
  30 fps, H.264 (yuv420p), silent, 20,653,964 bytes.
- Sources: 7 screenshots from the live demo run (`demo/run_demo.sh`,
  23 Nov 2026 13:14 WITA) + the 3 raw Playwright clips from that same
  run (`demo/shots/video/page@ccd53e4f…` dashboard NVDA,
  `page@fd149a4a…` dashboard FGI, `page@f8d47ef3…` closing). The other
  12 `.webm` files in that directory are from older runs and were NOT
  used.
- Assembly: `demo/build_final_video.sh` (ffmpeg 8.1.2) — gentle zoom on
  800px shots, slow top-to-bottom pan on tall screenshots, title-card
  overlays rendered by `demo/make_title_cards.py` (PIL + DejaVu).
  Intermediates in `demo/segments/`; QA frames in `demo/qa-frames/`.
- Verified: duration 160.00 s, no black segments (blackdetect), QA
  frames read at t=5/25/55/65/80/100/115/135/152/159 — correct shot
  order, overlays readable, no empty frames. No voice-over (text
  overlays only, by design — no TTS/recording path was set up for this
  entry).

## Remaining before submit (3–4 Dec)

1. Review (Instinct/Claude if needed) + fix anything it finds.
2. Final gate: `gate_cmc.py` 10/10 PASS (items 1–9 already 9/9; item 10
   is this file + README + video + post — complete with this milestone).
3. Confirm the Startup-tier upgrade on the CMC dashboard (or keep the
   Basic fallback cadence).
4. Submit on DoraHacks (target 5 Dec) + post on X with the video —
   both need Septian's explicit ACC at that point.
