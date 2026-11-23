# Desain Entry Hackathon CMC — RWA Track

- **Entry:** RWA Radar — Tokenised-Equities Screener & Issuer-Spread Monitor
- **Repo:** https://github.com/rwnliwan/cmc-rwa-radar (publik)
- **Track:** Real World Assets (satu track per submission)
- **Status dokumen:** DESAIN SAJA — belum ada kode yang ditulis dari desain ini
- **Ditulis:** 23 Nov 2026
- **Deadline submit:** 9 Des 2026 23:59 UTC (10 Des 08:00 WITA — sama dengan yang tampil di halaman DoraHacks)
- **Sumber riset:** `CMC-RWA-ENDPOINTS.md` (8 endpoint `/v5/real-world-assets/`, dibaca dari docs publik 23 Nov 2026)
- **Bukti live yang sudah ada:** tes API key 23 Nov 12:26 WITA — key valid; `map` NVDA → `rwa_id` 2; `assets/list` stock → 4.812 saham tokenisasi; `quotes/latest` NVDA → issuer spread nyata (lihat §3.3)

---

## 1. Konsep entry (satu paragraf)

**RWA Radar** adalah screener + monitor saham tokenisasi yang dibangun di atas CMC RWA API: papan peringkat 4.812 saham tokenisasi (diurutkan `rwa_rank`), monitor deviasi antar-issuer — harga token yang sama bisa berbeda di tiap issuer (Backed, Ondo, Dinari, dst.) dan selisih itu adalah sinyal yang sama dengan know-how deviasi Exit Radar, hanya saja pembandingnya bukan pool DEX melainkan issuer — plus sparkline dan % change 24j/7h yang dihitung dari `quotes/historical`, dan detail pane per aset (info perusahaan + daftar issuer + harga per token). Read-only, tanpa trading, tanpa wallet, tanpa janji return: alat ini menjawab satu pertanyaan — "token saham ini harganya konsisten antar issuer atau tidak, dan bagaimana trennya?" — dengan bukti API call nyata dari CoinMarketCap.

---

## 2. Stack + bentuk deliverable

### 2.1 Stack

| Pilihan | Keputusan | Alasan |
|---|---|---|
| Bahasa | Python 3.10+ | Sama seperti prototipe (teruji 3.10 & 3.12); stdlib saja, nol `pip install`, nol build step — juri bisa jalanin dalam 1 menit |
| Dependensi | **Stdlib saja** (`urllib`, `json`, `http.server`, `hashlib`, `argparse`) | Tidak ada kegagalan instalasi saat judging; tidak ada supply-chain risk |
| Data | CMC Pro API `/v5/real-world-assets/` (key di `.env.local`, gitignored) | Satu-satunya sumber data pasar; semua call tercatat di manifest evidence |
| Dashboard | Satu file HTML statis (`dashboard/index.html`, JS+CSS inline, tanpa CDN) | Tidak ada build, tidak ada framework, tidak ada aset eksternal yang bisa mati saat judging |
| Server dashboard | `serve.py` — `http.server` stdlib, serve `dashboard/` + `out/*.json` di `127.0.0.1:8000` | Lokal saja; dashboard membaca snapshot JSON yang ditulis CLI |
| Tes/gate | `gate_cmc.py` — pola yang sama dengan `gate.py` prototipe (tes offline dari fixture + cek repo bersih) | Pola sudah terbukti (19/19 di prototipe); fixture = respons API asli yang di-capture |
| Demo capture | Playwright headless Chromium (`demo/capture.py`, `record_video_dir` + screenshot per shot) | VM ini tidak punya X server; headless + video recording Playwright adalah jalur yang bekerja |

### 2.2 Bentuk deliverable

1. **CLI** (`cmc_run.py`) — tiga mode:
   - `board` — papan top-100 saham tokenisasi (sekali jalan, tulis `out/cmc_snapshot.json`).
   - `monitor` — refresh watchlist berkala (quotes 60 dtk, board 5 mnt, historical 15 mnt) + tulis snapshot tiap siklus; `--once` untuk demo sekali jalan.
   - `asset <ticker|rwa_id>` — detail satu aset (info + quotes + historical + issuers).
2. **Dashboard web lokal** (`serve.py` + `dashboard/index.html`) — board + klik baris → detail pane (tokens[], spread, sparkline, % change, info perusahaan, issuer).
3. **Video demo ±2–3 menit** (untuk post X + DoraHacks) — direkam dari run CLI live + dashboard (lihat §5.1).
4. **Repo GitHub publik** `cmc-rwa-radar` — hanya berisi kode + docs entry CMC (lihat §4: file prototipe Base DIHAPUS dari repo ini).

---

## 3. Arsitektur + alur data

### 3.1 Endpoint mana dipakai untuk apa

| Endpoint | Dipakai untuk | Cadence | Biaya |
|---|---|---|---|
| `map` | Resolve ticker ketikan user → `rwa_id` (sekali, saat startup/argumen); cek kewarasan universe | On demand | **0 credit** |
| `assets/list` | **Screener board**: `asset_type=stock`, `sort=rwa_rank`, `limit=250`, halaman 1 = top 100 (limit=100) | Tiap 5 mnt (monitor) / sekali (board) | 1 credit / 250 aset |
| `quotes/latest` | **Monitor refresh** watchlist (`rwa_id` top-20 + ticker user): agregat + `tokens[]` + `tradfi_markets[]` | Tiap 60 dtk | 1 credit / 250 aset |
| `quotes/historical` | **Sparkline + % change**: `interval=daily`, `count=30`, per aset watchlist | Tiap 15 mnt (monitor) / on demand (detail) | 1 credit / 100 data point |
| `info` | **Detail pane**: company fields (`employees`, `founded`, `industry`, `primary_exchange`, `cik`), About, logo, website | On demand (klik aset) | 1 credit / 250 aset |
| `issuers/list` + `issuers` | **Issuer view**: roster issuer + token apa saja yang diterbitkan satu issuer | On demand | 1 credit / request |
| `market-pairs/list` | **TIDAK DIPAKAI — DILARANG DESAIN** | — | Growth+ only, tidak ada di tier Startup hackathon |

### 3.2 Alur data

```
cmc_run.py (CLI)
  -> cmc_adapter.py: HTTP ke pro-api.coinmarketcap.com
       header X-CMC_PRO_API_KEY (dari .env.local, TIDAK PERNAH di-print/log)
       header Accept: application/json; timeout 30 dtk; retry 1x untuk 429/5xx
  -> cmc_pipeline.py: build_snapshot -> assess -> decide -> explain
       snapshot kanonis (JSON key terurut) + snapshot_id = snap-<sha256[:16]>
  -> out/cmc_snapshot.json (+ out/cmc_snapshot_<ts>.json arsip run)
  -> serve.py menyajikan dashboard/index.html + out/cmc_snapshot.json
  -> dashboard render board / detail pane dari snapshot JSON
```

### 3.3 Perhitungan inti

**Issuer spread (pembeda entry — know-how deviasi Exit Radar, diadaptasi).**
Dari `tokens[]` di `quotes/latest`, HANYA token dengan `price` non-null:

```
priced = [t.price for t in tokens if t.price is not None]
spread_abs = max(priced) - min(priced)
spread_pct = spread_abs / average_tokenized_price * 100
dev_i      = (price_i - average_tokenized_price) / average_tokenized_price * 100
```

- **Nilai fixture live (NVDA, 23 Nov 12:26 WITA):** NVDAX (Backed) 134,6063473392474 · NVDAon (Ondo) 134,56340294175905 · NVDA (Derivatives) 134,49015256705908 · NVDA.D (Dinari) **null** → `priced` = 3 token; `spread_abs` = 0,11619477218832; `spread_pct` = **0,086%** (di bawah ambang watch — contoh "sehat"); deviasi per token: NVDAX +0,129%, NVDAon +0,097%, Derivatives +0,042%.
- **KOREKSI 23 Nov 12:44 WITA (verifikasi live milestone 24 Nov):** angka fixture di atas berasal dari output tes 12:26 WITA yang TERPOTONG (`head -c 1500`) — `tokens[]` NVDA sebenarnya berisi **9 token, bukan 4**. Snapshot penuh 12:44 WITA: NVDAX (Backed) 133,947002 · NVDAon (Ondo) 134,080617 · NVDA (Derivatives) 133,750784 · NVDAB (bStocks) 133,760864 · rNVDA (Reality) 133,879918 · NVDA (Robinhood) 133,643578 · WNVDAX (Backed) 134,414346 · NVDAc (Coinbase) 133,974036 · NVDA.D (Dinari) **null** → `priced` = 8 token; `spread_abs` = 0,770767; `spread_pct` = **0,576%** — DI ATAS ambang watch 0,5% (flag `issuer_spread_watch` pada set token penuh). Pelajaran: (a) ambang 0,5% yang ditebak dari fixture terpotong terlalu rendah untuk set token penuh — kalibrasi ambang butuh distribusi lintas puluhan aset (tetap pekerjaan pasca-submit); (b) fixture untuk gate 25 Nov WAJIB diambil dari respons penuh, bukan output terpotong — kriteria gate §5.3 butir 2 memakai fixture yang dikoreksi ini, bukan 0,086%; (c) rumus spread di atas TIDAK berubah — yang salah hanya angka fixture. Harga bergerak (avg 134,43 → 133,90 dalam 18 menit), jadi setiap angka fixture selalu diberi timestamp.
- **Peringatan yang teramati dari data live:** `average_tokenized_price` (134,433335207312350663) LEBIH RENDAH dari token priced termurah (134,49015…) — agregat BUKAN mean sederhana `tokens[]` (kemungkinan tertimbang / mencakup token lain yang tidak tampil). Karena itu: **spread dihitung dari `tokens[]` saja; agregat dipakai hanya sebagai referensi independen** (untuk `dev_i`), bukan sebagai penyebut yang diasumsikan sama dengan mean.
- **Ambang awal (EKSPERIMEN, belum tervalidasi — label jelas di config & UI):** `SPREAD_WATCH_PCT = 0,5%` → flag `issuer_spread_watch`; `SPREAD_EXTREME_PCT = 2,0%` → flag `issuer_spread_extreme`. Ambang ini tebakan awal dari 1 observasi (NVDA 0,086%) — kalibrasi butuh distribusi spread lintas puluhan aset, pekerjaan pasca-submit, BUKAN klaim di README.

**% change + sparkline (dari `quotes/historical`, karena TIDAK ADA field percent-change di list/quotes — terverifikasi live).**

```
daily closes (count=30, interval=daily) -> spark = [close_0 ... close_29]
chg_24h = (close_last - close_prev) / close_prev * 100
chg_7d  = (close_last - close_7d_ago) / close_7d_ago * 100
```

- Daily bar saham/ETF dimulai tengah malam **New York**, bukan UTC — label sumbu chart ditulis "NY midnight", dan JANGAN bandingkan bar ini dengan bar UTC dari sumber lain.
- Bila `count` yang kembali < 2 → `history_short`, % change = `null` (bukan 0%).

**Reason codes (diadaptasi dari `assess_snapshot` prototipe — tiga lapis, bukan skor 0–100).**

| Code | Arti | Blocking? |
|---|---|---|
| `no_tokens` | `has_tokens=false` — aset ada di map/list tapi belum ada tokennya | Ya (tidak ada harga) |
| `all_prices_null` | semua `tokens[]` harganya null | Ya (tidak ada spread) |
| `partial_prices_null` | ≥1 token null, ≥2 priced (contoh live: Dinari null di NVDA) | Tidak — dicatat + dihitung dari priced saja |
| `thin_issuer_count` | <2 token priced → spread tidak bisa dihitung jujur | Ya untuk spread (bukan untuk board) |
| `issuer_spread_watch` / `issuer_spread_extreme` | spread > 0,5% / > 2,0% | Tidak (flag) |
| `mixed_underlying` | ≥1 priced token menyimpang >50% dari MEDIAN token priced (kemungkinan underlying berbeda dalam satu `rwa_id`; live: SPCX — 10 token ~$131 + SPACEX ~$531 + tSpaceX ~$512, spread 305%; ditambah 29–30 Nov 2026, non-blocking, token TIDAK pernah dibuang dari spread) | Tidak (flag) |
| `stale_quote` | umur `last_updated` > 5 mnt saat evaluasi (monitor) / > 15 mnt (board) | Tidak (flag; data lama tetap ditampilkan berlabel) |
| `history_short` | <2 titik historical → tanpa % change | Tidak |

**Keputusan (jujur seperti prototipe — tidak ada usulan beli/jual):** `OK` (data lengkap, spread di bawah watch) / `WATCH` (ada flag non-blocking) / `NO_SIGNAL` (blocking code — tampilkan alasannya, bukan angka kosong). Tidak ada paper portfolio di entry ini — keputusan adalah status monitor, bukan rekomendasi investasi.

### 3.4 Budget credits

**Cadence utama (tier Startup 450.000 credits/bln, 600 req/mnt — grant hackathon):**

| Pekerjaan | Per jam | Per hari | Per bulan (±30 hari) |
|---|---|---|---|
| Board `assets/list` top-100 (1 cr, tiap 5 mnt) | 12 | 288 | 8.640 |
| Watchlist `quotes/latest` ≤250 aset (1 cr, tiap 60 dtk) | 60 | 1.440 | 43.200 |
| Historical 20 aset × 30 titik (6 cr, tiap 15 mnt) | 24 | 576 | 17.280 |
| `info`/`issuers` on demand (estimasi) | — | ~5 | ~150 |
| **Total** | **~96** | **~2.309** | **~69.270** |

≈ 15% dari 450.000 — jauh di bawah batas. Rate: maks ~1 req/mnt sustained vs 600 req/mnt — bukan masalah. Sensus universe penuh (4.812 aset = 20 halaman = 20 credit) HANYA on demand, bukan terjadwal.

**Cadence fallback (bila upgrade Startup BELUM mendarat — per 23 Nov 12:25 dashboard masih Basic):** board tiap 30 mnt (48/hari) + quotes tiap 10 mnt (144/hari) + historical 10 aset tiap 2 jam (36/hari) ≈ **228/hari ≈ 6.840/bln** — muat di bawah 10.000 (angka dashboard sempat menampilkan 10.000 credits/bln, billing menampilkan 15.000 — verifikasi ulang angka pastinya sebelum mengandalkan salah satu). Fallback dipilih via flag config `CREDIT_MODE = "startup" | "basic"`, BUKAN dengan mengubah kode.

### 3.5 Handling edge case (kontrak perilaku)

- **`has_tokens=false`:** baris board tampil dengan harga "—" + code `no_tokens`; tidak masuk ranking spread; tidak dihitung sebagai 0.
- **Harga null di `tokens[]`:** dikeluarkan dari hitung spread; dihitung (`null_count`); bila semua null → `all_prices_null`.
- **Symbol tidak unik lintas tipe aset** (contoh dari riset: SPCX = saham Nasdaq dan token): SELALU resolve via `map` dengan filter `asset_type=stock`, bawa `rwa_id` ke mana-mana; tampilkan `nama · SYMBOL · rwa_id N` — jangan pernah tampilkan ticker sendirian sebagai identitas.
- **Paginasi:** loop `start`/`limit` sampai `has_more=false` atau cap halaman; cap default board = 1 halaman (top 100), sensus penuh = 20 halaman.
- **Error API (fail-closed, seperti prototipe):** envelope `error_code != "0"` → snapshot lama dipertahankan + status `stale` + alasan; TIDAK ADA data yang dikarang. `429` → backoff 5 dtk, retry 1x, lalu `stale`. `403` code `1014` (historical out-of-window) → turunkan `count`/interval, jangan ulangi request yang sama. Timeout 30 dtk.
- **Key:** dibaca dari `.env.local` saat start; bila file tidak ada → CLI gagal dengan pesan "set CMC_API_KEY di .env.local" (tanpa pernah mencetak nilai key); key TIDAK PERNAH masuk log, snapshot, fixture, atau repo.
- **Stale data:** `last_updated` selalu ditampilkan + umurnya; data > ambang ditandai `stale_quote`, bukan disembunyikan.

---

## 4. File layout di `~/workspace/cmc-rwa-entry/`

### 4.1 File BARU (ditulis untuk hackathon ini — inilah "integrasi CMC yang baru")

| File | Peran |
|---|---|
| `cmc_config.py` | Endpoint RWA, watchlist default (top-20 + ticker user), ambang spread, cadence, budget, versi `cmc-radar-schema/method/policy v0.1.0` |
| `cmc_adapter.py` | SATU-SATUNYA modul yang bicara ke CMC: `_get_json` (timeout + UA + header key), `fetch_map`, `fetch_list`, `fetch_quotes_latest`, `fetch_historical`, `fetch_info`, `fetch_issuers` |
| `cmc_pipeline.py` | `build_snapshot` → `assess_snapshot` (reason codes §3.3) → `decide` (OK/WATCH/NO_SIGNAL) → `explain` → `public_snapshot` (strip field internal `_`, canonical JSON + `snapshot_id`) |
| `cmc_run.py` | CLI: `board` / `monitor [--once]` / `asset <ticker\|rwa_id>`; tulis `out/cmc_snapshot.json` |
| `serve.py` | `http.server` stdlib di `127.0.0.1:8000`, serve `dashboard/` + `out/*.json` |
| `dashboard/index.html` | Satu file statis (JS+CSS inline, tanpa CDN): board + detail pane + sparkline (SVG inline) |
| `gate_cmc.py` | Gate offline dari fixture (lihat §5.3) + cek repo bersih (tanpa key) |
| `capture_cmc_evidence.py` | Capture respons mentah API + `evidence/cmc/manifest.json` (SHA-256 per file) — bukti API call nyata |
| `fixtures/cmc/` | Fixture dari respons live (NVDA map/list/quotes/historical, kasus `has_tokens=false`, kasus all-null) |
| `evidence/cmc/` | Respons mentah hasil capture + manifest |
| `demo/run_demo.sh` | Skrip demo end-to-end (CLI once → serve → capture) |
| `demo/capture.py` | Playwright headless: screenshot per shot + `record_video_dir` |
| `demo/shot-list.md` | Daftar shot video (lihat §5.1) |
| `out/` | Output run lokal (gitignored; snapshot + hasil gate) |
| `DESIGN-CMC-RWA.md` | Dokumen ini |
| `CMC-RWA-ENDPOINTS.md` | Riset endpoint (sudah ada) |
| `CMC_INTEGRATION.md` | Pernyataan "apa yang baru" untuk juri (lihat §4.3) |
| `README.md` | **Ditulis ulang total untuk entry CMC** (lihat §5.2) |
| `SUBMISSION.md` | Checklist submit DoraHacks + draf post X (diisi saat build) |

### 4.2 File prototipe Base — DIHAPUS dari repo ini (bukan dipakai ulang sebagai file)

Repo ini adalah clone `base-prototype/` v0.3.3. Supaya klaim "original, dibangun untuk hackathon ini" bersih, SEMUA file Base dihapus dari repo `cmc-rwa-radar` (aslinya tetap tersimpan di `~/workspace/radar-tokenized-stocks/base-prototype/` — repo Base, off limits, tidak disentuh):

- **Kode Base (tidak ada satu baris pun yang dipakai ulang sebagai file):** `config.py`, `adapter.py`, `pipeline.py`, `run.py`, `gate.py`, `capture_evidence.py`, `capture_rpc_evidence.py`, `verify_rpc_replay.py`, `package_v6.py`, `package_v7.py`, `package_v8.py`.
- **Docs Base:** `DESIGN.md`, `DECISION_MEMO.md`, `DECISION_MEMO-v0.3.2.md`, `QUOTER-RESEARCH.md`, `README-v0.3.2.md`, `MUSE-BASE-V033-AUDIT-2026-11-23.md`, `diff-v0.3.2-v0.3.3.txt`.
- **Data Base:** `evidence/`, `fixtures/`, `out/`, `audit-instinct-2026-11-22/`, `README.md` (versi Base — diganti README baru §5.2).
- **Yang dipertahankan dari clone:** `.gitignore` (ditambah `out/`, `evidence/cmc/*` bila perlu — `.env.local` sudah ada), `.git/` (riwayat clone sebagai titik awal), `CMC-RWA-ENDPOINTS.md`, dan dokumen desain ini.

### 4.3 Apa yang di-reuse vs apa yang BARU (untuk aturan hackathon)

**BARU — ditulis untuk hackathon ini (100% kode entry):** `cmc_adapter.py`, `cmc_pipeline.py`, `cmc_run.py`, `serve.py`, `dashboard/index.html`, `gate_cmc.py`, `capture_cmc_evidence.py`, `cmc_config.py`, dan semua fixture/evidence CMC. Tidak satu pun file `.py` prototipe Base yang disalin — modul CMC ditulis dari nol di atas riset endpoint.

**Di-reuse — HANYA know-how/metode sebagai desain (bukan kode):**
- Metode deviasi: bandingkan harga-harga independen dari satu aset yang sama, laporkan spread + deviasi per sumber (di Exit Radar: antar pool DEX; di sini: antar issuer). Rumus spread di §3.3 ditulis baru untuk struktur `tokens[]`.
- Disiplin reason codes + coverage (bukan skor komposit 0–100) dan keputusan jujur (OK/WATCH/NO_SIGNAL, tanpa rekomendasi investasi).
- Pola gate offline dari fixture + snapshot kanonis + `snapshot_id` hash + dedup/alert lokal.
- Disiplin stdlib-only, fail-closed, dan "label jujur" (simulasi disebut simulasi, data basi disebut basi).

**Identifikasi jelas untuk juri:** `CMC_INTEGRATION.md` + seksi "What's new" di README menyatakan eksplisit: (a) kode CMC ditulis baru untuk hackathon ini; (b) know-how yang dipakai ulang adalah metode (deviasi + reason codes), dengan sumbernya (Exit Radar Base v0.3.3, repo terpisah, bukan bagian submission); (c) daftar endpoint CMC yang dipakai + bukti API call nyata (`evidence/cmc/manifest.json` + cuplikan respons di README). Ini memenuhi aturan "pre-existing projects are eligible only if the CMC integration is new and clearly identified".

---

## 5. Rencana demo + README outline + kriteria selesai

### 5.1 Demo video (±2–3 menit) + post X

**Shot list (`demo/shot-list.md`):**
1. (0:00–0:20) Masalah: satu saham tokenisasi, banyak issuer, harga tidak sama — cuplikan `tokens[]` NVDA (3 harga + 1 null) dari respons API asli.
2. (0:20–0:50) CLI live: `python3 cmc_run.py board` → top-10 board + `asset NVDA` → spread 0,086% + flag OK; tunjukkan credit counter (0 credit untuk `map`, 1 credit per halaman).
3. (0:50–1:50) Dashboard: board di browser → klik NVDA → detail pane (harga per issuer, spread bar, sparkline 30 hari, % change 24j/7h, info perusahaan, issuer list) → klik aset `has_tokens=false` → tampilkan state `NO_SIGNAL` yang jujur.
4. (1:50–2:20) Bukti: `evidence/cmc/manifest.json` (SHA-256 respons mentah) + cuplikan `quotes/latest` JSON asli.
5. (2:20–2:40) Penutup: nama entry + repo + "Built with the CoinMarketCap RWA API" + #BuildwithCMC.

**Cara rekam:** `demo/run_demo.sh` → jalankan CLI once → nyalakan `serve.py` → `demo/capture.py` (Playwright headless, `record_video_dir` + screenshot per shot; localhost TIDAK butuh proxy relay) → video mentah `.webm` → potong/rakit (ffmpeg bila ada; bila tidak, submit rekaman mentah + kartu judul). Fallback: Septian rekam layar di mesinnya bila hasil otomatis tidak layak tayang. Narasi direkam terpisah (voice-over) atau teks overlay — putuskan saat build, bukan di desain.

**Post X (draf lengkap ditulis di `SUBMISSION.md` saat build):** video demo + 1–2 kalimat + link DoraHacks + #BuildwithCMC + sebut endpoint yang dipakai. Tidak ada klaim return/keuntungan.

### 5.2 README outline (bahasa Inggris — untuk juri)

1. Judul + satu kalimat pitch + badge (repo publik, Python stdlib, CMC RWA API).
2. **What it does** — 3 bullet: ranked board (4.812 tokenised stocks) · issuer-spread monitor · sparkline + % change dari historical.
3. **Live evidence** — angka dari tes live 23 Nov (NVDA rwa_id 2; spread 0,086%; 4.812 saham; Dinari null) + link ke `evidence/cmc/`.
4. **How to run** — `python3 cmc_run.py board` / `monitor` / `asset NVDA`; key di `.env.local` (contoh `.env.local.example` TANPA nilai); stdlib only.
5. **Endpoints used** — tabel §3.1 + pernyataan eksplisit "market-pairs/list NOT used (Growth+ only)".
6. **Credit budget** — tabel §3.4.
7. **Screenshots** — board + detail pane.
8. **What's new vs pre-existing** — ringkasan §4.3 + link `CMC_INTEGRATION.md`.
9. **Submission links** — DoraHacks + post X + demo video.
10. **Limitations (jujur)** — ambang spread eksperimental; agregat ≠ mean tokens[]; daily bar NY-midnight; bukan rekomendasi investasi.

### 5.3 Kriteria selesai (gate `gate_cmc.py` — semua harus PASS sebelum submit)

1. Semua endpoint backbone live: `map`, `assets/list`, `quotes/latest`, `quotes/historical`, `info`, `issuers/list`, `issuers` — masing-masing 200 + bentuk respons sesuai fixture.
2. Spread NVDA = 0,086% (±0,001) dari fixture live; Dinari null dikeluarkan; `priced_count` = 3.
3. % change dari fixture historical cocok dengan hitungan tangan (24j & 7h).
4. Edge case: `has_tokens=false` → `NO_SIGNAL` + code `no_tokens`; semua-null → `all_prices_null`; symbol ganda lintas tipe → resolve benar via `rwa_id`.
5. Fail-closed: respons error envelope → snapshot lama + status `stale`, tanpa data karangan.
6. Credit budget: simulasi 1 jam monitor ≤ 100 credit (sesuai tabel §3.4).
7. Dashboard render dari `out/cmc_snapshot.json` (Playwright: board > 0 baris; klik baris → detail pane terbuka + sparkline tampil).
8. Demo end-to-end: `demo/run_demo.sh` exit 0 (CLI once + serve + capture).
9. **Repo bersih:** `git status` bersih kecuali file yang diniatkan; `grep` pola key di seluruh repo = 0; `.env.local` tidak ter-track; tidak ada file Base tersisa (daftar §4.2 = 0 file).
10. README + `CMC_INTEGRATION.md` + `SUBMISSION.md` lengkap; post X + video demo siap.

---

## 6. Milestone ke deadline 9 Des 23:59 UTC

| Tanggal | Langkah | Keluar |
|---|---|---|
| **23 Nov** | Desain ini selesai → review chief | `DESIGN-CMC-RWA.md` |
| **24 Nov** | Bersihkan repo (§4.2) + kerangka README baru + `cmc_config.py` + `cmc_adapter.py` | Repo hanya berisi file CMC; fetch live pertama dari adapter |
| **25 Nov** | `cmc_pipeline.py` (spread, % change, reason codes) + fixture dari respons live + `gate_cmc.py` v1 | Gate 1–5 PASS |
| **26 Nov** | `cmc_run.py` (board/monitor/asset) end-to-end live; `out/cmc_snapshot.json` pertama | CLI jalan live |
| **27 Nov** | `serve.py` + `dashboard/index.html` render snapshot | Dashboard lokal jalan |
| **28 Nov** | Demo run penuh (CLI + dashboard + capture); perbaiki shot yang gagal | Video mentah v1 |
| 29–30 Nov | Edge case + budget credit terverifikasi + README draf lengkap | Gate 1–9 PASS |
| 1–2 Des | Rekam video final + draf post X + isi `SUBMISSION.md` | Video + post siap |
| 3–4 Des | Review (Instinct/Claude bila perlu) + perbaiki + gate final | Gate 10/10 PASS |
| **5 Des** | **Submit DoraHacks + post X** (target — buffer 4 hari) | Submission terkirim |
| 6–9 Des | Buffer: perbaikan bila ada temuan review / masalah submit; cek ulang tier Startup | — |
| **9 Des 23:59 UTC** | **Deadline keras** | — |

**Catatan kalender:** 28 Nov juga hari keputusan submit Base — pekerjaan CMC hari itu dibatasi demo run (ringan), keputusan Base tetap prioritas Septian. 30 Nov = kill-switch Base (operasional) — tidak bentrok dengan build CMC. **Risiko yang dipantau:** (1) upgrade Startup belum mendarat → pakai cadence fallback §3.4 sampai terverifikasi; (2) ambang spread butuh data distribusi → tetap eksperimental, jangan klaim kalibrasi; (3) `quotes/historical` window per plan → bila Startup belum aktif, `count=30` daily masih dalam jendela Basic (1 tahun) — aman.

---

## 7. Yang TIDAK dilakukan entry ini (batas scope)

- Tidak ada trading, order, wallet, atau private key — read-only penuh.
- Tidak ada klaim prediktif / rekomendasi investasi / janji return.
- Tidak memakai `market-pairs/list` (Growth+ only).
- Tidak memakai Trial Pro API / sandbox (data mock) — semua bukti dari Pro API dengan key asli.
- Tidak ada paper portfolio (keputusan = status monitor OK/WATCH/NO_SIGNAL).
- Tidak menyentuh repo Base (`~/workspace/radar-tokenized-stocks/`) — repo itu off limits; entry ini berdiri sendiri di `~/workspace/cmc-rwa-entry/` + repo `cmc-rwa-radar`.
