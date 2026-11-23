# Narration script — RWA Radar demo video (voiced)

Voice: Helio (`avocado_v2:MAI_03`, masculine, American, "Crisp, Clean,
Clear timbre") — production default. Speed 100. One voice, both cuts.
Note: `~/user/voice.json` holds a saved designed voice ("Wry Noodle",
`avocado_v2:vdc_31875`) — not used here; the brief asks for a
professional, clear English narration voice, and Helio is the
recommended production default for that. Septian can ask for another
voice if he prefers.

Spelling rules for TTS: acronyms spelled letter by letter (R W A,
A P I, S P C X, F G I, C M C); "Nvidia" spoken, not "NVDA"; numbers
written as words. All figures are the live demo-run numbers from
23 Nov 2026 21:41–21:42 WITA (see shot-list.md / SUBMISSION.md) —
nothing invented.

Pace check (measured): Helio at speed 100 runs ≈153 wpm (full S1: 53
words in 20.76 s — 0.76 s over its 20 s window, so S1/S2/S4/S5 were
trimmed to fit). Each shot's text is budgeted to its shot window with
~1–4 s of breathing room; actual durations are measured per shot at
render time (see build notes below).

## FULL version — 160.00 s (demo/video-final.mp4)

### S1 — 0:00–0:20 (20 s, 47 words)
One stock. Many issuers. Different prices. This is RWA Radar. Take
Nvidia — the same stock, tokenised by nine issuers, and they do not
agree on the price. Eight carry a live price. One, Dinari's, carries
none. The spread is just under one percent — and moves within minutes.

### S2 — 0:20–0:50 (30 s, 75 words)
Now the full board. Four thousand eight hundred and twelve tokenised
stocks, ranked — and this is the top ten, live from the CoinMarketCap
R W A A P I. Six are OK, three are on watch, and one is flagged —
S P C X, three hundred and four percent, a suspected mixed underlying:
its tokens look like two different instruments. Amazon's tokens span
twenty point four percent. The board costs about five credits per run.

### S3a — 0:50–1:28 (38.5 s, 96 words)
Let's open Nvidia. Every issuer's price, side by side, with its
deviation from the median. The reported spread is just under one
percent. But decisions use the robust spread — the gap between the
middle fifty percent of prices. Here it is about a tenth of a percent,
so Nvidia is OK. Below, the sparkline: thirty daily observations, with
the real percent change between them — up three point four six percent
since the previous observation, and down seventeen percent over the
last seven. Nothing smoothed. Nothing hidden. Just the data, as the
A P I returned it.

### S3b — 1:28–1:50 (21.6 s, 61 words)
And here is the honest part. F G I Industries has no tokens at all.
No price. No spread. Nothing to monitor. So the dashboard says so,
plainly: no signal. We would rather show a gap than invent a number.
That honesty is the whole point of a monitor. A monitor that hides
its gaps is not a monitor at all.

### S4 — 1:50–2:20 (30 s, 81 words)
Every number you have seen is checkable. This is the evidence
manifest: the raw A P I responses behind the demo, each one hashed,
with its endpoint, its timestamp, and its credit cost. Five credits
for the capture. The data comes from seven R W A endpoints — the
list, the quotes, the history, and the issuers. One endpoint we skip:
market pairs. It sits behind a tier this hackathon does not include.
Every figure traces back to the exact response that produced it.

### S5 — 2:20–2:40 (20 s, 56 words)
RWA Radar. A screener and issuer-spread monitor, built on the
CoinMarketCap R W A A P I for the Build with C M C Hackathon. The code
is public, the data is live, the verdicts honest. Find it on GitHub —
and follow it, hashtag Build with C M C. Built for traders who check.

Full total: 416 words.

## X CUT version — 138.03 s (demo/video-final-x.mp4)

Same content, tightened. Must stay ≤140 s (X free-account cap).

### S1 — 0:00–0:14 (14 s, 32 words)
One stock. Many issuers. Different prices. This is RWA Radar. Take
Nvidia — nine issuers, one stock, and they do not agree on the price.
Eight priced — one with no price at all.

### S2 — 0:14–0:40 (26 s, 65 words)
The full board: four thousand eight hundred and twelve tokenised
stocks, ranked, live from the CoinMarketCap R W A A P I. Six of the
top ten are OK, three are on watch, and one is flagged — S P C X,
three hundred and four percent, a suspected mixed underlying.
Amazon's tokens span twenty point four percent. The board costs about
five credits per run.

### S3a — 0:40–1:13 (33.5 s, 81 words)
Open Nvidia. Every issuer's price, side by side, with its deviation
from the median. The reported spread is just under one percent — but
decisions use the robust spread, the gap between the middle fifty
percent of prices: about a tenth of a percent, so Nvidia is OK. Below,
the sparkline: thirty daily observations, up three point four six
percent since the last one, down seventeen percent over seven. Nothing
smoothed. Nothing hidden. Just the data, as the A P I returned it.

### S3b — 1:13–1:33 (19.2 s, 56 words)
And the honest part. F G I Industries has no tokens at all — no
price, no spread. So the dashboard says so, plainly: no signal. We
would rather show a gap than invent a number. That honesty is the
whole point of a monitor. A monitor that hides its gaps is not a
monitor at all.

### S4 — 1:33–2:01 (28 s, 75 words)
Every number is checkable. The evidence manifest: the raw A P I
responses behind this demo, each one hashed, with its endpoint,
timestamp, and credit cost. Five credits for the capture. Seven
R W A endpoints in total — the list, the quotes, the history, and the
issuers. Market pairs is the one we skip: it sits behind a tier this
hackathon does not include. Every figure traces back to the exact
response that produced it.

### S5 — 2:01–2:18 (17.4 s, 49 words)
RWA Radar. A screener and issuer-spread monitor, built on the
CoinMarketCap R W A A P I for the Build with C M C Hackathon. The code
is public, the data is live, and the verdicts are honest. Find it on
GitHub. Built for traders who check their sources.

X-cut total: 359 words.

## Build notes

- Per-shot synthesis: `tts speak --voice avocado_v2:MAI_03 --language
  en --speed 100`, one MP3 per shot under `demo/narration/`
  (`full-s1.mp3` … `full-s5.mp3`, `x-s1.mp3` … `x-s5.mp3`).
  Pace measured on first render: ≈153 wpm — S1 (both versions) ran
  0.8 s over its window and was trimmed; S3b/S4/S5 (both) were
  lengthened with one closing line each to avoid long dead gaps.
- Measured per-shot durations (final, seconds) — every shot fits its
  window:
  - Full: S1 19.85/20.0, S2 28.63/30.0, S3a 34.37/38.47,
    S3b 19.87/21.6, S4 28.01/30.0, S5 18.60/19.93.
    Total narration 149.32 s of 160.00 s.
  - X cut: S1 13.32/14.0, S2 24.91/26.0, S3a 29.47/33.47,
    S3b 17.83/19.2, S4 27.43/28.0, S5 17.04/17.33.
    Total narration 130.01 s of 138.03 s.
  - S2 re-cut 24 Nov 2026 (narration-accuracy fix only): "Six are OK,
    three are on watch, and one is flagged — SPCX" (6+3+1=10) +
    credits quantified ("about five credits per run"). No other shot
    re-recorded; only full-s2.mp3 / x-s2.mp3 + the two voiced mp4s
    changed. S2 full 28.61 → 28.63 s, S2 X 24.12 → 24.91 s.
- Assembly: ffmpeg `adelay` per shot to its timeline offset, `amix`
  (normalize=0), `apad` to the video duration; mux with `-c:v copy
  -c:a aac -b:a 192k` (video stream untouched — MD5 of the video
  stream is identical to the silent originals for both files).
  Then a uniform `volume=4dB` gain pass (no clipping: peaks stay
  below 0 dBFS).
- Outputs (measured with ffprobe, 24 Nov 2026, after S2 re-cut):
  - `demo/video-final-voiced.mp4` — 160.00 s, 28,534,337 bytes,
    h264 1280x800 + AAC 192k. volumedetect: mean −24.7 dB,
    max −0.7 dB (no clipping).
  - `demo/video-final-x-voiced.mp4` — 138.07 s, 24,911,756 bytes,
    h264 1280x800 + AAC 192k. volumedetect: mean −24.4 dB,
    max −1.4 dB (no clipping). ≤140 s X free-account cap ✓
    (1.93 s margin).
  - Video-stream MD5 identical to the silent originals after the
    re-cut (full `99657fe0da8f566a4620225b3eb178db`,
    X `b069706446df145fa82e515a3846524a`).
- Alignment check: `silencedetect` (−40 dB) shows speech in every
  shot window; silences are only the natural 0.5–0.75 s sentence
  pauses plus the designed inter-shot gaps (longest: X 69.0–73.2 s,
  the 4.2 s gap between S3a narration end and S3b start). After the
  S2 re-cut: full S2 speech 20.1–48.3 s (gap 48.3–50.1 s into S3a),
  X S2 speech 14.2–38.5 s (gap 38.5–40.2 s into S3a).
- Transcription spot-check: NOT done — no local whisper model is
  installed (`~/workspace/models/whisper-small` absent) and the
  transcribe helper does not download models. Content is verified by
  construction (TTS inputs are the scripts above) + silence
  alignment. Residual risk: TTS pronunciation of spelled acronyms
  (S P C X, R W A) — Septian's listen is the final check before
  commit, as instructed.
- S2 re-cut 24 Nov 2026: narration fix only — no music, no changes
  to the video frames, no SUBMISSION.md change, no Drive upload, no
  change to the already-posted X post (only the Build-linked
  raw-GitHub video changes). Committed + pushed the same session.
