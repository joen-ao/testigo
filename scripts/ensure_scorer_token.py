"""Fill SCORER_TOKEN in .env when it is empty. Never prints the token."""

import re
import secrets

from common.config import ROOT


def main():
    env = ROOT / ".env"
    if not env.is_file():
        print("no .env yet - run: cp .env.example .env  (SCORER_TOKEN is generated on the next setup)")
        return 0
    text = env.read_text(encoding="utf-8")
    m = re.search(r"^SCORER_TOKEN=(.*)$", text, flags=re.MULTILINE)
    if m and m.group(1).strip():
        print("SCORER_TOKEN already set")
        return 0
    token = secrets.token_urlsafe(32)
    if m:
        text = text[:m.start()] + "SCORER_TOKEN=" + token + text[m.end():]
    else:
        text = text.rstrip("\n") + "\nSCORER_TOKEN=" + token + "\n"
    env.write_text(text, encoding="utf-8")
    print("SCORER_TOKEN generated in .env")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
