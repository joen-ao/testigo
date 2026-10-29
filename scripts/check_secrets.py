"""Find secrets or evidence in files that would be committed.

Uses `git ls-files` when the folder is a git repo; otherwise walks the tree and
applies this repo's .gitignore patterns. Exit 1 on any finding.

Flags: a value for META_API_KEY, a PEM private key, *.key files, .env files
(other than .env.example), anything under .secrets/, and images under runs/ or
evidence/ — whenever they are not ignored.
"""

import fnmatch
import re
import subprocess
import sys
from pathlib import Path

from common.config import ROOT

# Built from pieces so this file does not flag itself.
PEM = re.compile("-----BEGIN [A-Z ]*" + "PRIVATE KEY-----")
API_KEY_VALUE = re.compile(r"^\s*META_API_KEY\s*=\s*([^\s#]+)", re.MULTILINE)
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".mov", ".wav", ".webm"}
REQUIRED_IGNORES = [".env", ".secrets/", "*.key", "runs/", "evidence/"]
ALWAYS_SKIP = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules"}


def _gitignore_patterns(root):
    gi = root / ".gitignore"
    if not gi.is_file():
        return [], []
    ignore, keep = [], []
    for line in gi.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        (keep if line.startswith("!") else ignore).append(line.lstrip("!"))
    return ignore, keep


def _ignored(rel, ignore, keep):
    parts = rel.split("/")
    name = parts[-1]
    if any(fnmatch.fnmatch(name, k) or rel == k for k in keep):
        return False
    for pat in ignore:
        if pat.endswith("/"):
            if pat.rstrip("/") in parts[:-1] or pat.rstrip("/") == parts[0]:
                return True
        elif fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(rel, pat):
            return True
    return False


def candidate_files(root=ROOT):
    root = Path(root)
    if (root / ".git").exists():
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"],
                             cwd=root, capture_output=True, text=True, check=True).stdout
        return [p for p in out.splitlines() if p]
    ignore, keep = _gitignore_patterns(root)
    files = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if set(rel.split("/")) & ALWAYS_SKIP:
            continue
        if not _ignored(rel, ignore, keep):
            files.append(rel)
    return sorted(files)


def scan(root=ROOT):
    root = Path(root)
    findings = []
    ignore, _ = _gitignore_patterns(root)
    for req in REQUIRED_IGNORES:
        if req not in ignore:
            findings.append((".gitignore", "missing required pattern %r" % req))
    for rel in candidate_files(root):
        name = rel.split("/")[-1]
        top = rel.split("/")[0]
        if name.endswith(".key"):
            findings.append((rel, "signing key file would be committed"))
        if name.startswith(".env") and name != ".env.example":
            findings.append((rel, ".env file would be committed"))
        if top == ".secrets":
            findings.append((rel, "file under .secrets/ would be committed"))
        if top in ("runs", "evidence") and Path(rel).suffix.lower() in IMAGE_EXT:
            findings.append((rel, "evidence image would be committed"))
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if PEM.search(text):
            findings.append((rel, "PEM private key"))
        if API_KEY_VALUE.search(text):
            findings.append((rel, "META_API_KEY has a value"))
    return findings


def main():
    findings = scan()
    if not findings:
        print("check-secrets: OK (%d files checked)" % len(candidate_files()))
        return 0
    print("check-secrets: %d finding(s)" % len(findings))
    for rel, why in findings:
        print("  %s: %s" % (rel, why))
    return 1


if __name__ == "__main__":
    sys.exit(main())
