#!/usr/bin/env bash
# Re-encode the Track C scene audio from sounds/source/ → docs/scene/audio/
# Output: mono, 96 kbps mp3, with fade in/out for clean cut points.
set -euo pipefail
cd "$(dirname "$0")/.."

SRC=sounds/source
OUT=docs/scene/audio
mkdir -p "$OUT"

encode() {
  local in="$1" out="$2" start="$3" dur="$4" fi="${5:-0.05}" fo="${6:-0.15}"
  local fos
  fos=$(python3 -c "print($dur - $fo)")
  ffmpeg -hide_banner -loglevel error -y \
    -ss "$start" -t "$dur" -i "$in" \
    -af "afade=t=in:st=0:d=$fi,afade=t=out:st=$fos:d=$fo" \
    -ac 1 -ar 44100 -b:a 96k -codec:a libmp3lame "$out"
  echo "  wrote $out"
}

encode "$SRC/harddrive.mp3"            "$OUT/hdd-spinup.mp3"       2.0  6.0 0.10 0.30
encode "$SRC/crton.mp3"                "$OUT/crt-on.mp3"           0.0  1.8 0.02 0.20
encode "$SRC/keyboardtyping-short.mp3" "$OUT/keytype.mp3"          4.0  3.0 0.05 0.15
encode "$SRC/modemsound.mp3"           "$OUT/modem-handshake.mp3"  0.0 19.3 0.05 0.30

echo
echo "Done. Total: $(du -sh "$OUT" | awk '{print $1}')"
