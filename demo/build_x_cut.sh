#!/usr/bin/env bash
# RWA Radar — X cut of the demo video (<=140s for free X accounts).
# Septian's decision 23 Nov 2026 14:04 WITA: cut, don't use Premium.
# This is a SEPARATE build from demo/build_final_video.sh: the 2:40
# demo/video-final.mp4 (for DoraHacks) is untouched. Same sources
# (live demo run 23 Nov 2026 20:49-20:50 WITA, re-cut for v0.3.0), same
# title cards, only the holds are shorter.
#
# Structure (137.63 s total, 1280x800, 30 fps, H.264, silent):
#   S1  14.00s  shot-1  (zoom)   S2  26.00s  shot-2  (zoom)
#   S3a 12.00s  board   (zoom) + 2.20s clip + 19.00s detail (slow pan)
#   S3b  2.12s  clip + 17.00s NO_SIGNAL detail (slow pan)
#   S4  28.00s  shot-4  (slow pan)   S5  1.00s clip + 16.32s closing (zoom)
# Timeline: S1 0-14 | S2 14-40 | S3a board 40-52 | S3a clip 52-54.20 |
#   S3a detail 54.20-73.20 | S3b clip 73.20-75.32 | S3b detail 75.32-92.32 |
#   S4 92.32-120.32 | S5 clip 120.32-121.32 | S5 closing 121.32-137.63
# The closing hold is 16.32s (was 16.00s) so the total stays 137.63s:
# the two clips are 0.32s shorter than last cut, same as the full video.
#
# Usage: ./demo/build_x_cut.sh
# Output: demo/video-final-x.mp4 (+ demo/segments-x/ intermediates).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SHOTS="$ROOT/demo/shots"
VIDEO="$SHOTS/video"
CARDS="$ROOT/demo/title-cards"
SEG="$ROOT/demo/segments-x"
OUT="$ROOT/demo/video-final-x.mp4"
mkdir -p "$SEG"

FPS=30
CRF=20

# --- Segment builders (same as build_final_video.sh) ----------------------
zoom() {
    local img="$1" dur="$2" card="$3" out="$4"
    local frames
    frames=$(python3 -c "print(int(round($dur * $FPS)))")
    ffmpeg -v error -y -i "$img" -i "$CARDS/$card.png" -filter_complex \
        "[0:v]scale=2560:-2,zoompan=z='min(zoom+0.00008,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=$frames:s=1280x800:fps=$FPS[base];[base][1:v]overlay=0:0[v]" \
        -map "[v]" -frames:v "$frames" -c:v libx264 -crf $CRF -pix_fmt yuv420p -r $FPS "$out"
}

pan() {
    local img="$1" dur="$2" card="$3" out="$4"
    local frames
    frames=$(python3 -c "print(int(round($dur * $FPS)))")
    ffmpeg -v error -y -framerate $FPS -loop 1 -t "$dur" -i "$img" -i "$CARDS/$card.png" -filter_complex \
        "[0:v]scale=1280:-2,crop=1280:800:0:'(in_h-800)*n/($frames-1)',fps=$FPS[base];[base][1:v]overlay=0:0[v]" \
        -map "[v]" -frames:v "$frames" -c:v libx264 -crf $CRF -pix_fmt yuv420p -r $FPS "$out"
}

clip() {
    local src="$1" dur="$2" card="$3" out="$4"
    ffmpeg -v error -y -i "$src" -i "$CARDS/$card.png" -filter_complex \
        "[0:v]scale=1280:800,fps=$FPS,format=yuv420p[base];[base][1:v]overlay=0:0[v]" \
        -map "[v]" -t "$dur" -c:v libx264 -crf $CRF -pix_fmt yuv420p -r $FPS "$out"
}

echo "== building X-cut segments =="
zoom "$SHOTS/shot-1-problem-nvda-tokens.png" 14.00 s1 "$SEG/seg01-s1.mp4"
zoom "$SHOTS/shot-2-cli-board.png"          26.00 s2 "$SEG/seg02-s2.mp4"
zoom "$SHOTS/shot-3-dashboard-board.png"    12.00 s3a_board "$SEG/seg03-s3a-board.mp4"
clip "$VIDEO/page@d645aaa878c3bc410cd1f398aeb8ffe2.webm" 2.20 s3a_clip "$SEG/seg04-s3a-clip.mp4"
pan  "$SHOTS/shot-3-detail-nvda.png"       19.00 s3a_detail "$SEG/seg05-s3a-detail.mp4"
clip "$VIDEO/page@ca82a571f9816f36d8309137deb7ff66.webm" 2.12 s3b_clip "$SEG/seg06-s3b-clip.mp4"
pan  "$SHOTS/shot-3b-detail-nosignal.png"  17.00 s3b_detail "$SEG/seg07-s3b-detail.mp4"
pan  "$SHOTS/shot-4-evidence-manifest.png" 28.00 s4 "$SEG/seg08-s4.mp4"
clip "$VIDEO/page@71a618a53203002446fa949271a41b10.webm" 1.00 s5 "$SEG/seg09-s5-clip.mp4"
zoom "$SHOTS/shot-5-closing.png"           16.32 s5 "$SEG/seg10-s5-hold.mp4"

# --- Concatenate ----------------------------------------------------------
: > "$SEG/concat.txt"
for i in 01 02 03 04 05 06 07 08 09 10; do
    f=$(ls "$SEG"/seg"$i"-*.mp4)
    echo "file '$f'" >> "$SEG/concat.txt"
done
ffmpeg -v error -y -f concat -safe 0 -i "$SEG/concat.txt" -c copy "$OUT"

# --- Verify ---------------------------------------------------------------
echo "== X-cut video =="
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height,r_frame_rate -of default=noprint_wrappers=1 "$OUT"
echo "== black-frame check (any black segment > 0.5s would list here) =="
ffmpeg -v info -i "$OUT" -vf "blackdetect=d=0.5:pix_th=0.10" -an -f null - 2>&1 | grep -i blackdetect || echo "no black segments detected"
echo "== QA frames =="
mkdir -p "$ROOT/demo/qa-frames-x"
for t in 25 60 85 130; do
    ffmpeg -v error -y -ss "$t" -i "$OUT" -frames:v 1 "$ROOT/demo/qa-frames-x/t${t}.png"
done
ls -la "$OUT" "$ROOT/demo/qa-frames-x/"
echo "== build_x_cut.sh OK =="
