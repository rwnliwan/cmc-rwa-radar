#!/usr/bin/env bash
# RWA Radar — final demo video assembly (milestone 1-2 Des).
# DESIGN-CMC-RWA.md §5.1 (5 shots, target ±2-3 min).
#
# Sources (all from the live demo run of 23 Nov 2026 13:14 WITA,
# commit 0c254c0 — nothing invented, nothing re-recorded):
#   - 7 screenshots in demo/shots/ (live CLI output + local dashboard)
#   - 3 raw Playwright clips in demo/shots/video/ (latest run only):
#       ccd53e4f = dashboard NVDA phase (2.48s)
#       fd149a4a = dashboard FGI phase  (2.12s)
#       f8d47ef3 = closing phase        (1.08s)
#   The other 12 .webm files in that dir are from older runs and are
#   NOT used.
#   - Title-card overlays rendered by demo/make_title_cards.py
#     (all numbers from demo/shots/terminal-*.txt, same run).
#
# Structure (160.00 s total = 2:40, 1280x800, 30 fps, H.264, silent):
#   S1  20.00s  shot-1  (zoom)   S2  30.00s  shot-2  (zoom)
#   S3a 14.00s  board   (zoom) + 2.48s clip + 22.00s detail (slow pan)
#   S3b  2.12s  clip + 19.40s NO_SIGNAL detail (slow pan)
#   S4  30.00s  shot-4  (slow pan)   S5  1.08s clip + 18.92s closing (zoom)
# Tall screenshots get a slow top-to-bottom pan so the whole content
# is visible; 800px screenshots get a gentle zoom. No audio track:
# the video is silent by design (same as the earlier make.fun videos).
#
# Usage: ./demo/build_final_video.sh
# Output: demo/video-final.mp4 (+ demo/segments/ intermediates, kept
#         so any shot can be re-built without re-running the demo).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SHOTS="$ROOT/demo/shots"
VIDEO="$SHOTS/video"
CARDS="$ROOT/demo/title-cards"
SEG="$ROOT/demo/segments"
OUT="$ROOT/demo/video-final.mp4"
mkdir -p "$SEG"

FPS=30
CRF=20

# --- 1. Title cards -------------------------------------------------------
python3 demo/make_title_cards.py

# --- 2. Segment builders --------------------------------------------------
# zoom <img> <dur_s> <card> <out>   — gentle zoom on an 800px-tall shot
zoom() {
    local img="$1" dur="$2" card="$3" out="$4"
    local frames
    frames=$(python3 -c "print(int(round($dur * $FPS)))")
    ffmpeg -v error -y -i "$img" -i "$CARDS/$card.png" -filter_complex \
        "[0:v]scale=2560:-2,zoompan=z='min(zoom+0.00008,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=$frames:s=1280x800:fps=$FPS[base];[base][1:v]overlay=0:0[v]" \
        -map "[v]" -frames:v "$frames" -c:v libx264 -crf $CRF -pix_fmt yuv420p -r $FPS "$out"
}

# pan <img> <dur_s> <card> <out>    — slow top-to-bottom pan on a tall shot
pan() {
    local img="$1" dur="$2" card="$3" out="$4"
    local frames
    frames=$(python3 -c "print(int(round($dur * $FPS)))")
    ffmpeg -v error -y -framerate $FPS -loop 1 -t "$dur" -i "$img" -i "$CARDS/$card.png" -filter_complex \
        "[0:v]scale=1280:-2,crop=1280:800:0:'(in_h-800)*n/($frames-1)',fps=$FPS[base];[base][1:v]overlay=0:0[v]" \
        -map "[v]" -frames:v "$frames" -c:v libx264 -crf $CRF -pix_fmt yuv420p -r $FPS "$out"
}

# clip <webm> <dur_s> <card> <out>  — raw Playwright recording, re-encoded
clip() {
    local src="$1" dur="$2" card="$3" out="$4"
    ffmpeg -v error -y -i "$src" -i "$CARDS/$card.png" -filter_complex \
        "[0:v]scale=1280:800,fps=$FPS,format=yuv420p[base];[base][1:v]overlay=0:0[v]" \
        -map "[v]" -t "$dur" -c:v libx264 -crf $CRF -pix_fmt yuv420p -r $FPS "$out"
}

echo "== building segments =="
zoom "$SHOTS/shot-1-problem-nvda-tokens.png" 20.00 s1 "$SEG/seg01-s1.mp4"
zoom "$SHOTS/shot-2-cli-board.png"          30.00 s2 "$SEG/seg02-s2.mp4"
zoom "$SHOTS/shot-3-dashboard-board.png"    14.00 s3a_board "$SEG/seg03-s3a-board.mp4"
clip "$VIDEO/page@ccd53e4fac5464717a12e00b99f4bf1f.webm" 2.48 s3a_clip "$SEG/seg04-s3a-clip.mp4"
pan  "$SHOTS/shot-3-detail-nvda.png"       22.00 s3a_detail "$SEG/seg05-s3a-detail.mp4"
clip "$VIDEO/page@fd149a4a46d93379a88dd22333c1a11c.webm" 2.12 s3b_clip "$SEG/seg06-s3b-clip.mp4"
pan  "$SHOTS/shot-3b-detail-nosignal.png"  19.40 s3b_detail "$SEG/seg07-s3b-detail.mp4"
pan  "$SHOTS/shot-4-evidence-manifest.png" 30.00 s4 "$SEG/seg08-s4.mp4"
clip "$VIDEO/page@f8d47ef3be9b8f8f0f445f7d0267a47b.webm" 1.08 s5 "$SEG/seg09-s5-clip.mp4"
zoom "$SHOTS/shot-5-closing.png"           18.92 s5 "$SEG/seg10-s5-hold.mp4"

# --- 3. Concatenate -------------------------------------------------------
: > "$SEG/concat.txt"
for i in 01 02 03 04 05 06 07 08 09 10; do
    f=$(ls "$SEG"/seg"$i"-*.mp4)
    echo "file '$f'" >> "$SEG/concat.txt"
done
ffmpeg -v error -y -f concat -safe 0 -i "$SEG/concat.txt" -c copy "$OUT"

# --- 4. Verify ------------------------------------------------------------
echo "== final video =="
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height,r_frame_rate -of default=noprint_wrappers=1 "$OUT"
echo "== black-frame check (any black segment > 0.5s would list here) =="
ffmpeg -v info -i "$OUT" -vf "blackdetect=d=0.5:pix_th=0.10" -an -f null - 2>&1 | grep -i blackdetect || echo "no black segments detected"
echo "== QA frames =="
mkdir -p "$ROOT/demo/qa-frames"
for t in 5 25 55 65 80 100 115 135 152 159; do
    ffmpeg -v error -y -ss "$t" -i "$OUT" -frames:v 1 "$ROOT/demo/qa-frames/t${t}.png"
done
ls -la "$OUT" "$ROOT/demo/qa-frames/"
echo "== build_final_video.sh OK =="
