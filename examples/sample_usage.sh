#!/usr/bin/env bash
set -euo pipefail

# Smoke-test: generate a 10s test tone, render all 4 styles with different palettes.

cd "$(dirname "$0")/.."

if [ ! -f examples/test.wav ]; then
  ffmpeg -y -f lavfi -i "sine=frequency=440:duration=10,afade=t=in:d=0.5" \
    -ar 44100 -ac 1 examples/test.wav
fi

for combo in "radial:sunset" "bars:neon" "waveform:ocean" "particles:ember"; do
  style="${combo%%:*}"
  palette="${combo##*:}"
  .venv/bin/visualize \
    --input examples/test.wav \
    --output "examples/test_${style}_${palette}.mp4" \
    --style "$style" \
    --palette "$palette" \
    --artist "Riley Edward" \
    --title "Smoke Test | ${style} ${palette}"
done

echo "Rendered:"
ls -lh examples/*.mp4
