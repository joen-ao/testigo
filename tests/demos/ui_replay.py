"""Replay fixture runs into the interface, to check that the views paint.

  python -m tests.demos.ui_replay a1           # one supervised run
  python -m tests.demos.ui_replay a3 --both    # unsupervised first, then supervised
  python -m tests.demos.ui_replay clean --delay 0.8

TEST DATA ONLY. Every event is tagged `test_data: true` and the interface shows
a warning banner while any such event is on screen. Never record this for the
video or count it in WitnessBench: those come from real runs (F3, F10).
"""

import argparse
import json
import time
import urllib.request

from interceptor.sink import service_url
from tests.fixtures.fake_agent import run_fixture


def post(path, event=None):
    data = json.dumps(event or {}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(service_url(path), data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=2) as r:
        return r.status


def replay(scenario, supervised, delay):
    out = run_fixture(scenario, supervised=supervised)
    for e in out.events:
        post("/events", dict(e, test_data=True))
        time.sleep(delay)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("scenario", choices=["clean", "a1", "a2", "a3"])
    ap.add_argument("--both", action="store_true", help="unsupervised run first, then supervised")
    ap.add_argument("--delay", type=float, default=0.6, help="seconds between events")
    ap.add_argument("--keep", action="store_true", help="do not reset the stored events first")
    args = ap.parse_args(argv)

    if not args.keep:
        post("/events/reset")
    if args.both:
        replay(args.scenario, False, args.delay)
        time.sleep(args.delay * 3)
    out = replay(args.scenario, True, args.delay)
    print("replayed %s (test data): blocked=%s flagged=%s" % (
        args.scenario, out.blocked, out.receipt_flagged))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
