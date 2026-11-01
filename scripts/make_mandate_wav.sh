#!/bin/sh
# Make a test WAV of the company's spoken mandate on macOS (F1), for
#   .venv/bin/python -m policy.compile mandate <wav>
#
#   sh scripts/make_mandate_wav.sh                       # → $TMPDIR/mandate.wav
#   sh scripts/make_mandate_wav.sh out.wav "Only ship to our warehouse, …"
#
# Uses the first English system voice installed (Samantha, Alex, Daniel; else
# the system default voice) and converts to 16 kHz mono 16-bit WAV, which Voice
# Transcribe accepts. Audio is never committed (check-secrets flags .wav
# files), so the default lands outside the repo.
set -eu
OUT="${1:-${TMPDIR:-/tmp}/mandate.wav}"
PHRASE="${2:-Only ship to our warehouse, at most fifteen hundred dollars per order}"
AIFF="${OUT%.wav}.aiff"
VOICE=""
for v in Samantha Alex Daniel; do
  if say -v '?' | grep -q "^$v "; then VOICE="$v"; break; fi
done
if [ -n "$VOICE" ]; then
  say -v "$VOICE" -o "$AIFF" "$PHRASE"
else
  echo "no English voice (Samantha/Alex/Daniel) installed; using the system default" >&2
  say -o "$AIFF" "$PHRASE"
fi
afconvert -f WAVE -d LEI16@16000 -c 1 "$AIFF" "$OUT"
rm -f "$AIFF"
echo "$OUT"
