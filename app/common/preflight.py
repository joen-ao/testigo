"""Is this machine ready to run TESTIGO+? (spec 12 O2; `make doctor`)

`checks()` returns one (status, name, detail) per item, status "ok", "warn" or
"fail", each with what to do when it is not ok. No network, no models: only
files, settings and local ports. Never prints a secret value.
"""

import os
import socket
import tempfile

from app.common import config

OK, WARN, FAIL = "ok", "warn", "fail"


def _port_free(host, port):
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def checks(env_path=None):
    s = config.settings()
    out = []

    env = env_path or (config.ROOT / ".env")
    out.append((OK, ".env", "found") if env.is_file() else
               (FAIL, ".env", "missing: copy .env.example to .env and fill in the Meta settings"))

    missing = [n for n, ok in config.configured(config.MODEL_VARS).items()
               if not ok and not n.startswith("GLIMMER")]
    out.append((OK, "Meta models", "all set") if not missing else
               (FAIL, "Meta models", "empty in .env: %s (real runs, the benchmark and the gates need them)"
                % ", ".join(missing)))

    out.append((OK, "scorer token", "set") if s.scorer_token else
               (WARN, "scorer token", "SCORER_TOKEN is empty: run `make setup` (the portal's order log needs it)"))

    out.append((OK, "owner key", "found") if s.signing_key_path.is_file() else
               (WARN, "owner key", "no key at SIGNING_KEY_PATH: run `.venv/bin/testigo keygen`; "
                "without it receipts are not signed and rules cannot be signed in the interface"))

    try:
        s.runs_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=s.runs_dir, prefix=".doctor-"):
            pass
        out.append((OK, "runs folder", "writable"))
    except OSError as e:
        out.append((FAIL, "runs folder", "%s is not writable (%s): set RUNS_DIR in .env" % (s.runs_dir, e.strerror)))

    try:
        path = config.policy_path()
        out.append((OK, "rules in force", "trusted (%s)" % config.runs_label(path)))
    except config.PolicyNotTrusted as e:
        out.append((FAIL, "rules in force", "%s. Restore the demo's rules (step 1 in the app, or delete "
                    "runs/policy/active.policy.yaml) or sign new ones" % e))

    if s.portal_port == s.interceptor_port:
        out.append((FAIL, "ports", "PORTAL_PORT and INTERCEPTOR_PORT are both %d: give them different values"
                    % s.portal_port))
    else:
        busy = [("portal", s.portal_host, s.portal_port), ("interface", s.interceptor_host, s.interceptor_port)]
        busy = ["%s %d" % (name, port) for name, host, port in busy if not _port_free(host, port)]
        out.append((OK, "ports", "%d and %d free" % (s.portal_port, s.interceptor_port)) if not busy else
                   (WARN, "ports", "in use: %s (already running? stop it, or set another port in .env)"
                    % ", ".join(busy)))

    out.append((OK, "spend caps", "USD %.0f total, USD %.0f per run" % (s.max_spend_usd, s.max_run_spend_usd)))
    return out


def report(items):
    """The lines `make doctor` prints, and whether nothing failed."""
    mark = {OK: "ok  ", WARN: "warn", FAIL: "FAIL"}
    lines = ["  [%s] %-15s %s" % (mark[st], name, detail) for st, name, detail in items]
    return lines, all(st != FAIL for st, _, _ in items)
