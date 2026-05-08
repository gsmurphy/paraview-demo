#!/usr/bin/env bash
# assemble_video.sh — concatenate segment 1 → title card → segment 2 into out/demo.mp4.
#
# Each input is a directory of frame_NNNN.png at the same resolution; we
# encode each to an intermediate .mp4 with H.264 (CRF 18 for the segments,
# 22 for the title card), then concat them. A short crossfade is applied
# at each segment→title and title→segment boundary using filter_complex
# with the xfade filter.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

FPS=30
RES=1920x1080
SEG1_DIR=frames/segment1
SEG2_DIR=frames/segment2
TITLE_DIR=frames/titlecard
OUT=out/demo.mp4
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

mkdir -p out

if ! command -v ffmpeg >/dev/null; then
  echo "error: ffmpeg not on PATH (brew install ffmpeg)" >&2
  exit 1
fi

# Sanity-check inputs.
for d in "$SEG1_DIR" "$SEG2_DIR" "$TITLE_DIR"; do
  if ! ls "$d"/frame_*.png >/dev/null 2>&1; then
    echo "error: no frame_*.png files in $d — run 'make frames' first" >&2
    exit 1
  fi
done

encode_segment () {
  local src=$1 out=$2 crf=${3:-18}
  ffmpeg -y -hide_banner -loglevel warning \
    -framerate "$FPS" -pattern_type glob -i "$src/frame_*.png" \
    -c:v libx264 -pix_fmt yuv420p -crf "$crf" \
    -movflags +faststart -r "$FPS" -s "$RES" \
    "$out"
}

echo "==> Encoding segment 1"
encode_segment "$SEG1_DIR" "$TMP/seg1.mp4" 18

echo "==> Encoding title card"
encode_segment "$TITLE_DIR" "$TMP/title.mp4" 22

echo "==> Encoding segment 2"
encode_segment "$SEG2_DIR" "$TMP/seg2.mp4" 18

# Crossfade segments through the title card via xfade.
# Durations come from each input.
seg1_dur=$(ffprobe -v error -show_entries format=duration -of default=nokey=1:noprint_wrappers=1 "$TMP/seg1.mp4")
title_dur=$(ffprobe -v error -show_entries format=duration -of default=nokey=1:noprint_wrappers=1 "$TMP/title.mp4")
xfade=0.4
off1=$(awk -v a="$seg1_dur" -v x="$xfade" 'BEGIN{printf "%.4f", a - x}')
off2=$(awk -v a="$seg1_dur" -v t="$title_dur" -v x="$xfade" 'BEGIN{printf "%.4f", a + t - 2*x}')

echo "==> Stitching with crossfades (xfade=${xfade}s)"
ffmpeg -y -hide_banner -loglevel warning \
  -i "$TMP/seg1.mp4" -i "$TMP/title.mp4" -i "$TMP/seg2.mp4" \
  -filter_complex "
    [0:v][1:v]xfade=transition=fade:duration=${xfade}:offset=${off1}[v01];
    [v01][2:v]xfade=transition=fade:duration=${xfade}:offset=${off2}[v]
  " \
  -map "[v]" -c:v libx264 -pix_fmt yuv420p -crf 18 -r "$FPS" -movflags +faststart \
  "$OUT"

size=$(stat -f%z "$OUT" 2>/dev/null || stat -c%s "$OUT")
size_mb=$(awk -v s="$size" 'BEGIN{printf "%.1f", s/1048576}')
echo "==> wrote $OUT (${size_mb} MB)"
