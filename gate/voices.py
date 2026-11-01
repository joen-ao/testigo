"""English voices for the clips the gate synthesizes with macOS `say`.

The scenario is in English (04): the mandate, the approval and g6's amounts are
said by an English system voice. The first of the preferred voices installed
here is used; if none is, `say` falls back to the system's default voice (the
clip is still made; its transcript is reported as it is).
"""

import shutil
import subprocess

ENGLISH_VOICES = ("Samantha", "Alex", "Daniel")


def installed_voices():
    """Names of the voices `say -v ?` lists (empty without `say`)."""
    if not shutil.which("say"):
        return set()
    listed = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    return {line.split("  ")[0].strip() for line in listed.splitlines() if line.strip()}


def english_voice(preferred=ENGLISH_VOICES):
    """The first preferred voice installed here, or None (system default)."""
    names = installed_voices()
    return next((v for v in preferred if v in names), None)


def say_args(voice):
    """["say", "-v", voice] or ["say"] when no voice is available."""
    return ["say", "-v", voice] if voice else ["say"]
