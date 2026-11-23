#!/usr/bin/env bash
# RWA Radar — demo run end-to-end (milestone 28 Nov).
# DESIGN-CMC-RWA.md §5.1 (shot list) + §6: CLI live -> serve.py ->
# capture.py (Playwright headless screenshots + raw video v1).
#
# Order matters: cmc_run.py writes out/cmc_snapshot.json on every run,
# so the dashboard shows whatever ran LAST. Sequence:
#   board (board snapshot) -> asset NVDA (txt only) -> MERGE the asset
#   run's NVDA history into the board snapshot (demo/merge_history.py)
#   — otherwise the dashboard detail pane would say "Sparkline not
#   available" while the title card advertises a sparkline (final-gate
#   group 6). The merged snapshot keeps the BOARD run's spread/decision
#   for NVDA; only the historical part comes from the asset run (same
#   asset, fetched minutes apart — nothing invented).
#   -> capture terminal shots -> serve -> dashboard NVDA
#   -> asset FGI (NO_SIGNAL snapshot) -> dashboard NO_SIGNAL
#   -> board again (restore board snapshot) -> closing shot.
# Total live credits for this run: ~13 (board 2 + asset NVDA 3 +
# board restore 2 + asset FGI 2 + board restore 2 + asset fallbacks if any).
#
# Usage: ./demo/run_demo.sh        (exit 0 = all shots captured)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SHOTS="$ROOT/demo/shots"
mkdir -p "$SHOTS" "$SHOTS/video"

SERVE_PID=""
serve_started=0

stop_serve() {
  if [ "$serve_started" -eq 1 ] && [ -n "$SERVE_PID" ]; then
    kill "$SERVE_PID" 2>/dev/null || true
    wait "$SERVE_PID" 2>/dev/null || true
    echo "serve.py stopped."
  fi
}
trap stop_serve EXIT

echo "== RWA Radar demo run =="
echo "repo: $ROOT"

# --- Shot 1+2 sources: live CLI output, saved as text -------------------
echo "== [1/7] board live (top-10) =="
python3 cmc_run.py board --limit 10 | tee "$SHOTS/terminal-board.txt"
cp out/cmc_snapshot.json "$SHOTS/board-snapshot.json"

echo "== [2/7] asset NVDA live =="
python3 cmc_run.py asset NVDA | tee "$SHOTS/terminal-asset-nvda.txt"
cp out/cmc_snapshot.json "$SHOTS/asset-nvda-snapshot.json"

# `asset` overwrote cmc_snapshot.json with a 1-asset snapshot — merge its
# NVDA history into the board snapshot, or the dashboard detail pane
# would show "Sparkline not available" (final-gate group 6).
echo "== [2b/7] merge NVDA history into the board snapshot =="
python3 demo/merge_history.py "$SHOTS/board-snapshot.json" "$SHOTS/asset-nvda-snapshot.json"

# --- Terminal shots (1, 2, 4) -------------------------------------------
echo "== [3/7] capture terminal shots (1, 2, 4) =="
python3 demo/capture.py --phase terminal

# --- Dashboard server ----------------------------------------------------
if curl -fsS -o /dev/null "http://127.0.0.1:8000/" 2>/dev/null; then
  echo "serve.py already running on :8000 — reusing it."
else
  echo "== starting serve.py on 127.0.0.1:8000 =="
  python3 serve.py --port 8000 > "$SHOTS/serve.log" 2>&1 &
  SERVE_PID=$!
  serve_started=1
  for _ in $(seq 1 15); do
    if curl -fsS -o /dev/null "http://127.0.0.1:8000/" 2>/dev/null; then
      break
    fi
    sleep 1
  done
  curl -fsS -o /dev/null "http://127.0.0.1:8000/" \
    || { echo "error: serve.py did not come up on :8000" >&2; exit 1; }
fi

# --- Shot 3a: dashboard board + NVDA detail ------------------------------
echo "== [4/7] capture dashboard shot 3a (NVDA detail) =="
python3 demo/capture.py --phase dashboard --select NVDA

# --- Shot 3b source: a live has_tokens=false asset -----------------------
# FGI (rwa_id 4379, rank #4407) was verified NO_SIGNAL on 23 Nov 12:59 WITA.
# Fallbacks are other tail-of-list assets, still live, still has_tokens=false.
echo "== [5/7] asset without tokens (NO_SIGNAL, live) =="
nosignal_ok=0
SELECT_SYM=""
for pair in "4379:FGI" "4306:FOXX" "6194:MCRP"; do
  rid="${pair%%:*}"; sym="${pair##*:}"
  echo "-- trying rwa_id $rid ($sym) --"
  if python3 cmc_run.py asset "$rid" | tee "$SHOTS/terminal-asset-nosignal.txt"; then
    nosignal_ok=1
    SELECT_SYM="$sym"
    break
  fi
  echo "rwa_id $rid failed, trying next candidate" >&2
done
[ "$nosignal_ok" -eq 1 ] || { echo "error: no has_tokens=false asset worked" >&2; exit 1; }

echo "== [6/7] capture dashboard shot 3b (NO_SIGNAL) =="
python3 demo/capture.py --phase dashboard --select "$SELECT_SYM"

# --- Restore the board snapshot, then the closing shot -------------------
echo "== [7/7] restore board snapshot + closing shot =="
python3 cmc_run.py board --limit 10 > "$SHOTS/terminal-board-restore.txt" 2>&1
python3 demo/capture.py --phase closing

# --- Verify every shot exists and is a real PNG --------------------------
echo "== verifying shots =="
expected="shot-1-problem-nvda-tokens.png
shot-2-cli-board.png
shot-3-dashboard-board.png
shot-3-detail-nvda.png
shot-3b-detail-nosignal.png
shot-4-evidence-manifest.png
shot-5-closing.png"
missing=0
for f in $expected; do
  p="$SHOTS/$f"
  if [ ! -s "$p" ] || ! head -c 8 "$p" | grep -q "PNG"; then
    echo "MISSING/INVALID: $p" >&2
    missing=1
  else
    echo "ok: $f ($(stat -c %s "$p") bytes)"
  fi
done
[ "$missing" -eq 0 ] || { echo "error: some shots are missing" >&2; exit 1; }

echo "== demo run OK: 7 shots in $SHOTS =="
ls -la "$SHOTS"/*.png
echo "raw video v1 (unedited): $SHOTS/video/"
exit 0
