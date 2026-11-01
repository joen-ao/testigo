"""Gate g6: English spoken amounts, transcribed and parsed exactly and fast (F0 §13, D8).

  .venv/bin/python -m gate.g6_voice_numeric [--n 20] [--voices Samantha Alex Daniel]

Synthesizes --n phrases "<amount in words> dollars, ship to Larkspur Market" with
macOS `say` (the requested voices that exist here, alternating) as 16 kHz WAV,
transcribes each with Voice Transcribe and parses the amount with
approval.voice_match (the F7 code). "Exact" means the parsed amount equals the
amount said. Amounts are whole dollars, said in both English forms ("one
thousand two hundred forty" and "twelve hundred forty"). Latency is measured
in the client, from sending the finished audio to receiving the text. Passes
with >= 95% exact and a median < 1.5 s.

Without `say`/`afconvert`, or with none of the voices, the item is omitted
(pass null). Audio stays in runs/gate/<date>/g6/ (never committed).
"""

import argparse
import json
import random
import shutil
import statistics
import subprocess

from approval import voice_match
from common import meta_client
from gate.report import report, run_dir
from gate.voices import ENGLISH_VOICES, installed_voices

DESTINATION = "Larkspur Market"
EXACT_MIN = 0.95
MEDIAN_MAX_MS = 1500
DEFAULT_VOICES = list(ENGLISH_VOICES)

_UNITS = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
          "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
          "eighteen", "nineteen"]
_TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty", 6: "sixty", 7: "seventy",
         8: "eighty", 9: "ninety"}


def _below_100(n):
    if n < 20:
        return _UNITS[n]
    t, u = divmod(n, 10)
    return _TENS[t] + ("-" + _UNITS[u] if u else "")


def _below_1000(n):
    h, rest = divmod(n, 100)
    parts = [_UNITS[h] + " hundred"] if h else []
    if rest:
        parts.append(_below_100(rest))
    return " ".join(parts)


def to_words(n, hundreds=False):
    """1 <= n <= 999,999,999 in English words, as a person says an amount.
    hundreds=True says 1,100-9,999 (not a whole thousand) the short way:
    1240 -> "twelve hundred forty" instead of "one thousand two hundred forty"."""
    if not 1 <= n <= 999_999_999:
        raise ValueError(n)
    if hundreds and 1100 <= n <= 9999 and n % 1000 >= 100:
        h, rest = divmod(n, 100)
        return _below_100(h) + " hundred" + (" " + _below_100(rest) if rest else "")
    millions, rest = divmod(n, 1_000_000)
    thousands, units = divmod(rest, 1000)
    parts = []
    if millions:
        parts.append(_below_1000(millions) + " million")
    if thousands:
        parts.append(_below_1000(thousands) + " thousand")
    if units:
        parts.append(_below_1000(units))
    return " ".join(parts)


def amounts(n, seed=31):
    """n whole-dollar amounts like the portal's orders: USD 10 to 50,000."""
    rng = random.Random(seed)
    fixed = [1240, 1500, 12_500, 855, 9_999]
    out = fixed[:n]
    while len(out) < n:
        out.append(rng.randrange(10, 50_000))
    return out


def available_voices(wanted):
    if not (shutil.which("say") and shutil.which("afconvert")):
        return []
    names = installed_voices()
    return [v for v in wanted if v in names]


def synth(text, voice, wav):
    aiff = wav.with_suffix(".aiff")
    subprocess.run(["say", "-v", voice, "-o", str(aiff), text], check=True)
    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(aiff), str(wav)],
                   check=True)
    aiff.unlink(missing_ok=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, default=20, help="phrases to synthesize (default 20)")
    ap.add_argument("--voices", nargs="+", default=DEFAULT_VOICES)
    args = ap.parse_args(argv)

    voices = available_voices(args.voices)
    if not voices:
        return report("g6", None, "omitted: no macOS `say`/`afconvert` or none of %s" % args.voices,
                      "%d%% exact, median < %.1f s" % (EXACT_MIN * 100, MEDIAN_MAX_MS / 1000), 0,
                      {"omitted": True})

    out_dir = run_dir("g6")
    meta = meta_client.MetaClient()
    rows = []
    for i, amount in enumerate(amounts(args.n)):
        voice = voices[i % len(voices)]
        said = "%s dollars, ship to %s" % (to_words(amount, hundreds=i % 2 == 1), DESTINATION)
        wav = out_dir / ("clip_%02d.wav" % i)
        synth(said, voice, wav)
        try:
            text, ms, secs = meta.transcribe(wav)
        except Exception as e:  # noqa: BLE001 - a failed call is a miss, reported
            rows.append({"amount": amount, "said": said, "voice": voice, "error": str(e)[:200],
                         "exact": False, "latency_ms": None})
            continue
        heard, why = voice_match.heard_amount(text, DESTINATION)     # cents
        heard = None if heard is None else (heard // 100 if heard % 100 == 0 else heard / 100)
        rows.append({"amount": amount, "said": said, "voice": voice, "transcript": text,
                     "heard": heard, "why": why, "exact": heard == amount,
                     "latency_ms": ms, "audio_s": secs})
        print("g6: %s %r -> %s %s %d ms" % (voice, said, heard, "ok" if heard == amount else "MISS", ms),
              flush=True)

    (out_dir / "clips.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    exact = sum(1 for r in rows if r["exact"])
    lat = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
    median = statistics.median(lat) if lat else None
    share = exact / len(rows) if rows else 0.0
    passed = share >= EXACT_MIN and median is not None and median < MEDIAN_MAX_MS
    details = {"voices": voices, "missing_voices": [v for v in args.voices if v not in voices],
               "median_ms": median, "max_ms": max(lat) if lat else None,
               "misses": [{k: r.get(k) for k in ("said", "transcript", "heard", "why", "error")}
                          for r in rows if not r["exact"]],
               "spent_usd_total": round(meta.spent_usd(), 4)}
    return report("g6", passed,
                  "%d/%d exact (%.0f%%), median %s ms" % (exact, len(rows), 100 * share, median),
                  "%d%% exact, median < %.1f s" % (EXACT_MIN * 100, MEDIAN_MAX_MS / 1000),
                  len(rows), details)


if __name__ == "__main__":
    raise SystemExit(main())
