# Demo shot list — RWA Radar (milestone 28 Nov, rehearsal)

Video target: ±2–3 menit, 5 shot (DESIGN-CMC-RWA.md §5.1).
Semua angka dari snapshot live — tidak ada data karangan. Keputusan
memakai robust spread (IQR/median): WATCH > 0,5%, EXTREME > 1,0%,
terkalibrasi dari distribusi board live 23 Nov 2026 (v0.2.0) — bukan
lagi ambang eksperimental 0,5% / 2,0% pada spread max-min.

**Koreksi atas teks desain §5.1:** shot 1 di desain menulis "3 harga +
1 null" dari fixture 12:26 WITA yang TERPOTONG. Angka benar (terverifikasi
live 12:44–12:47 WITA): `tokens[]` NVDA = **9 token, 8 priced, 1 null
(Dinari)**; spread bergerak 0,576% → 0,430% → 0,707% dalam hitungan menit.
Shot 1 menampilkan angka live saat demo jalan, bukan angka desain.

## Shot 1 — Masalah: satu saham, banyak issuer, harga tidak sama (0:00–0:20)

- Tampilkan: output terminal `python3 cmc_run.py asset NVDA` — tabel
  `tokens[]` (simbol, issuer, harga, deviasi vs agregat), token null
  (Dinari) yang dikeluarkan dari spread, spread live + reason codes.
- Perintah: `python3 cmc_run.py asset NVDA`
- File: `demo/shots/shot-1-problem-nvda-tokens.png`
  (sumber teks: `demo/shots/terminal-asset-nvda.txt`)
- Durasi target: ±20 detik.

## Shot 2 — CLI live: board (0:20–0:50)

- Tampilkan: output terminal `python3 cmc_run.py board --limit 10` —
  tabel top-10 saham (rank, symbol, avg USD, spread, keputusan,
  reason codes) + baris "credits this run".
- Perintah: `python3 cmc_run.py board --limit 10`
- File: `demo/shots/shot-2-cli-board.png`
  (sumber teks: `demo/shots/terminal-board.txt`)
- Durasi target: ±30 detik.

## Shot 3 — Dashboard: detail NVDA + NO_SIGNAL yang jujur (0:50–1:50)

- Tampilkan (a): dashboard `http://127.0.0.1:8000/` — board, lalu klik
  baris NVDA → detail pane (harga per issuer, spread, info perusahaan).
  Catatan jujur: snapshot board tidak membawa data historical, jadi
  detail pane menampilkan "Sparkline not available — this snapshot has
  no historical data" (bukan grafik palsu); sparkline 30 hari + % change
  24j/7h sudah tampil di shot 1 (output `asset NVDA`).
- Tampilkan (b): aset tanpa token — FGI Industries Ltd. (`rwa_id` 4379,
  rank #4407, ditemukan di ekor `assets/list`, `has_tokens=false`) →
  detail pane menampilkan "No tokens for this asset (no_tokens) — there
  is no price and no spread to show." + badge NO_SIGNAL. Tidak ada angka
  yang dikarang untuk aset ini.
- Perintah: `python3 serve.py` (latar) → klik NVDA → 
  `python3 cmc_run.py asset 4379` → refresh dashboard → klik FGI.
  Bila `asset 4379` gagal, coba kandidat ekor lain (4306, 6194) — tetap
  live, tetap `has_tokens=false`.
- File: `demo/shots/shot-3-dashboard-board.png`,
  `demo/shots/shot-3-detail-nvda.png`,
  `demo/shots/shot-3b-detail-nosignal.png`
- Durasi target: ±60 detik.

## Shot 4 — Bukti: manifest evidence (1:50–2:20)

- Tampilkan: isi `fixtures/cmc/MANIFEST.json` — daftar respons mentah
  API yang di-capture (endpoint + timestamp + credit + ukuran) + catatan
  spread fixture 0,707% (8 priced, Dinari null, capture 12:47 WITA).
- Perintah: (tidak ada — render file manifest apa adanya)
- File: `demo/shots/shot-4-evidence-manifest.png`
- Durasi target: ±30 detik.

## Shot 5 — Penutup (2:20–2:40)

- Tampilkan: dashboard (halaman penuh) — header "RWA Radar", footer
  "entry for Build with CMC: API Hackathon, Round 2", baris
  "Repo: github.com/rwnliwan/cmc-rwa-radar · #BuildwithCMC".
- Perintah: (tidak ada — screenshot dashboard apa adanya)
- File: `demo/shots/shot-5-closing.png`
- Durasi target: ±20 detik.

## Catatan rekam

- `demo/run_demo.sh` menjalankan urutan penuh end-to-end (CLI → serve →
  capture) dan harus exit 0.
- `demo/capture.py` (Playwright headless Chromium, sudah tersedia di VM
  ini) mengambil screenshot per shot + merekam video mentah
  (`record_video_dir`, `demo/shots/video/`) — video mentah v1, belum
  diedit; perakitan video final + voice-over/teks overlay adalah
  milestone 1–2 Des.
- Total kredit demo penuh: ±13 credit (board 2 + asset NVDA 3 + board
  restore 2 + asset FGI 2 + board restore 2 + list ekor sudah dilakukan
  sekali saat persiapan, 1 credit).
