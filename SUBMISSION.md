# SUBMISSION — RWA Radar (Build with CMC: API Hackathon, Round 2)

- **Entry:** RWA Radar — Tokenised-Equities Screener & Issuer-Spread Monitor
- **Repo (public):** https://github.com/rwnliwan/cmc-rwa-radar
- **Track:** Real World Assets (one track per submission)
- **Hackathon page:** https://dorahacks.io/hackathon/coinmarketcap-api-202611/detail
- **Hard deadline:** 9 Dec 2026 23:59 UTC (10 Dec 07:59 WITA)
- **Our target:** submit 5 Dec 2026 (4-day buffer)
- **Status:** DeepSeek review (23 Nov, READY AFTER FIXES, 71/100) +
  the same-day recalibration and fix round + the same-evening v0.3.0
  follow-up round (binary flag, per-token breakdown), gate 10/10 PASS
  (23 Nov, live) + final pre-submit gate (Instinct, 23 Nov, 77/100,
  HOLD) + the v0.4.0 fix round (six must-fix groups, gate 10/10 PASS
  again — see README and `CMC_INTEGRATION.md`). Remaining: submit
  5 Dec. NOT submitted yet — submission and the X post need Septian's
  separate ACC.

## Submission checklist (DoraHacks)

| Item | Status |
|---|---|
| Public GitHub repo | ✅ https://github.com/rwnliwan/cmc-rwa-radar |
| Track selected | ✅ Real World Assets |
| Demo video | ✅ `demo/video-final.mp4` — 2:40 (160.00 s), 1280×800, H.264, silent, 25.4 MB (re-cut 23 Nov 21:42 WITA for the v0.4.0 final-gate fix round) |
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
(IQR/median) spread with a single flag threshold, an exploratory
heuristic derived from one live snapshot, so the central-dispersion
flag is less sensitive to a single extreme quote — not immune,
especially with small token sets); and sparkline + % change computed
from `quotes/historical` (30 daily-period observations; each is the
first value in its period, not a close — changes are between the
available daily-period observations, labelled with their actual
dates), because the list/quotes responses carry no percent-change
fields. Read-only: no trading, no wallet, no private keys. Verdicts
are honest monitor states — `OK` / `WATCH` / `NO_SIGNAL` — never
investment advice.

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
- Demo run (23 Nov 21:41 WITA): NVDA spread 0.985% (8 priced, 1 null),
  robust spread 0.107%, change vs previous daily-period observation
  (2026-11-22 to 2026-11-23) +3.46%, change vs 7 periods back
  (2026-11-16 to 2026-11-23) −17.07%; board top-10: 9 assets
  covered, 6 OK / 3 WATCH; AMZN 20.4%, SPCX 304.1% (suspected mixed
  underlying); FGI (rwa_id 4379) honest `NO_SIGNAL` (`no_tokens`).
- The spread moves with the market (0.576% → 0.707% → 0.652% on 23 Nov),
  so every figure in the repo and video is timestamped.

## Honest limitations (stated in the README, not hidden)

- Spread decisions use a robust (IQR/median) spread with a single flag
  threshold (robust spread > 0.5% — see README "How the spread is
  measured"). Thresholds are empirically derived from a single live
  snapshot (n = 23 assets) and will be refined as more snapshots
  accumulate; the reported max–min spread is still shown as-is. Next to
  every flagged asset, each token's deviation from the asset's median
  priced token is shown, largest first — token deviations are sorted to
  aid inspection; that order is not a causal attribution of the IQR flag.
- The max–min spread is dominated by single-token outliers (AMZN 20.6%
  and TSLA 43.8% via a Hyperliquid token far from the cluster; MU 28%
  and SKHY 10% via Backed "w…" tokens) — that is why it no longer
  decides; the robust spread does.
- SPCX's `tokens[]` mixes what looks like two underlyings in one
  `rwa_id` (10 tokens ~$131 plus SPACEX ~$531 and tSpaceX ~$512) —
  flagged `mixed_underlying` (any priced token >100% from the median),
  never silently trimmed. The flag means suspected comparability
  issue, not proof of a different underlying: price alone does not
  establish a different instrument — mapping, unit, freshness or
  instrument differences are all possible.
- `assets/list` returns rows with `rwa_id: null` (GOOG + a duplicate
  BRK.B) — dropped with an explicit warning, counted only when covered.
- Startup-tier upgrade still pending on the CMC dashboard (Basic as of
  23 Nov); the slow-cadence fallback applies until confirmed.

## Draft post on X (ready to post with the submission)

> RWA Radar: one stock, many issuers, different prices. Our CMC entry
> covers 4,812 tokenised stocks — raw issuer ranges (NVDA 0.99%, SPCX
> 304% — suspected mixed underlying), plus flags for dispersion & data
> quality. Built on the CMC RWA API. #BuildwithCMC
> [DORAHACKS-PROJECT-URL]

- Replace `[DORAHACKS-PROJECT-URL]` at submission time with the real
  DoraHacks **project submission page** URL (not the hackathon landing
  page — the landing page is not the submission).

- Attach `demo/video-final-x.mp4` to the post (the X cut — same
  content, shorter holds; 2:18 / 138.03 s, under the 2:20 free-account
  cap, so no Premium is needed).
- Length: check again after replacing the placeholder — the placeholder
  counts as one URL (23 characters by X's count); the text without the
  URL is 254 characters, so the post fits the 280-character limit with
  the real project URL. No return/profit claims anywhere.
- **Video length:** the full video is 2:40 (160 s), per the design
  target of ±2–3 min. X free accounts cap video uploads at 2:20
  (140 s); the X cut below solves that. DoraHacks itself takes the
  2:40 file as-is — the cut only affects the X post.

## Demo video — how it was built

- File: `demo/video-final.mp4` — 2:40 (160.00 s nominal; ffprobe
  measures 159.97 s, the usual frame-quantisation rounding), 1280×800,
  30 fps, H.264 (yuv420p), silent, 26,632,797 bytes.
- Sources: 7 screenshots from the live demo run (`demo/run_demo.sh`,
  23 Nov 2026 21:41–21:42 WITA — the run `gate_cmc.py` item 8 performed
  during the v0.4.0 final-gate fix round) + the 3 raw Playwright clips
  from that same run (`demo/shots/video/page@11a3914a…` dashboard NVDA
  2.48 s, `page@f18686fb…` dashboard FGI 2.20 s, `page@39105f6a…`
  closing 1.04 s). The other `.webm` files in that directory are from
  older runs and were NOT used. **Re-cut note:** the previous cut
  (20:50 WITA, v0.3.0) showed NVDA spread 0.600% / robust 0.217% and
  the detail pane said "Sparkline not available"; this cut shows the
  new run (NVDA spread 0.985% / robust 0.107%, AMZN 20.4%, SPCX 304.1%)
  with a real sparkline — the board snapshot's NVDA row now carries
  the asset run's 30 daily-period observations, merged by
  `demo/merge_history.py` (same asset, fetched minutes apart).
- Assembly: `demo/build_final_video.sh` (ffmpeg 8.1.2) — gentle zoom on
  800px shots, slow top-to-bottom pan on tall screenshots, title-card
  overlays rendered by `demo/make_title_cards.py` (PIL + DejaVu).
  Intermediates in `demo/segments/`; QA frames in `demo/qa-frames/`.
- Verified: duration 160.00 s nominal (ffprobe 159.97 s), no black
  segments (blackdetect), QA frames read at t=5/25/55/65/80/100/115/135/152/159 — correct shot
  order, overlays readable, no empty frames. No voice-over (text
  overlays only, by design — no TTS/recording path was set up for this
  entry).
- X cut for the post: `demo/video-final-x.mp4` — 2:18 (138.03 s),
  1280×800, 30 fps, H.264 (yuv420p), silent, 23,258,872 bytes. Same
  sources and title cards, holds shortened (S1 14 s, S2 26 s, S3a
  board 12 s / detail 19 s, S3b detail 17 s, S4 28 s, S5 hold 16.32 s);
  built by `demo/build_x_cut.sh` (intermediates in `demo/segments-x/`,
  QA frames in `demo/qa-frames-x/`). Verified: no black segments, QA
  frames read at t=25 (CLI board), t=60 (NVDA detail), t=85 (FGI
  NO_SIGNAL), t=130 (closing + repo footer) — all correct, overlays
  readable, no token-like strings in the file. Made 23 Nov 2026 per
  Septian's decision to cut rather than use Premium.

## Remaining before submit

1. Final review (Instinct) — done 23 Nov 2026 (77/100, HOLD) + the
   v0.4.0 fix round below; final gate: `gate_cmc.py` 10/10 PASS.
2. Confirm the Startup-tier upgrade on the CMC dashboard (or keep the
   Basic fallback cadence).
3. Submit on DoraHacks (target 5 Dec) + post on X with the video —
   both need Septian's explicit ACC at that point. At submission time,
   replace `[DORAHACKS-PROJECT-URL]` in the X draft with the real
   project submission page URL.
