#!/usr/bin/env bash
# RWA Radar — final demo video assembly (re-cut 23 Nov 2026 20:50 WITA,
# follow-up v0.3.0 — the 20:34 WITA cut showed the two-level board,
# 7 OK / 2 WATCH with WATCH/EXTREME thresholds; this cut shows the
# binary-flag board, 6 OK / 3 WATCH).
# DESIGN-CMC-RWA.md §5.1 (5 shots, target ±2-3 min).
#
# Sources (all from the live demo run of 23 Nov 2026 20:49-20:50 WITA,
# the run gate_cmc.py item 8 performed — nothing invented, nothing
# re-recorded):
#   - 7 screenshots in demo/shots/ (live CLI output + local dashboard)
#   - 3 raw Playwright clips in demo/shots/video/ (latest run only):
#       d645aaa8 = dashboard NVDA phase (2.20s; used in full)
#       ca82a571 = dashboard FGI phase  (2.16s; first 2.12s used)
#       71a618a5 = closing phase        (1.00s; used in full)
#   The other .webm files in that dir are from older runs and are
#   NOT used. (One closing clip from the previous run rendered narrow
#   throughout — a one-off Playwright recording artifact; the phase was
#   re-run and the clean 1.40s clip 07cf89a5 was kept as a spare, but
#   the gate run's own 1.04s clip e9cf95f7 is clean and is used here.)
#   - Title-card overlays rendered by demo/make_title_cards.py
#     (all numbers from demo/shots/terminal-*.txt, same run).
#
# Structure (160.00 s total = 2:40, 1280x800, 30 fps, H.264, silent):
#   S1  20.00s  shot-1  (zoom)   S2  30.00s  shot-2  (zoom)
#   S3a 14.00s  board   (zoom) + 2.20s clip + 22.00s detail (slow pan)
#   S3b  2.12s  clip + 19.40s NO_SIGNAL detail (slow pan)
#   S4  30.00s  shot-4  (slow pan)   S5  1.00s clip + 19.28s closing (zoom)
# The closing hold is 19.28s (was 18.96s) so the total stays exactly
# 160.00s: the NVDA clip is 0.28s shorter than the 2.48s used last
# cut and the closing clip 0.04s shorter than 1.04s.
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
clip "$VIDEO/page@d645aaa878c3bc410cd1f398aeb8ffe2.webm" 2.20 s3a_clip "$SEG/seg04-s3a-clip.mp4"
pan  "$SHOTS/shot-3-detail-nvda.png"       22.00 s3a_detail "$SEG/seg05-s3a-detail.mp4"
clip "$VIDEO/page@ca82a571f9816f36d8309137deb7ff66.webm" 2.12 s3b_clip "$SEG/seg06-s3b-clip.mp4"
pan  "$SHOTS/shot-3b-detail-nosignal.png"  19.40 s3b_detail "$SEG/seg07-s3b-detail.mp4"
pan  "$SHOTS/shot-4-evidence-manifest.png" 30.00 s4 "$SEG/seg08-s4.mp4"
clip "$VIDEO/page@71a618a53203002446fa949271a41b10.webm" 1.00 s5 "$SEG/seg09-s5-clip.mp4"
zoom "$SHOTS/shot-5-closing.png"           19.28 s5 "$SEG/seg10-s5-hold.mp4"

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
