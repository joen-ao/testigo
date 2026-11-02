"""Spec 12 O2: the preflight names what is not ready and what to do."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.common import preflight


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_with(self, **env):
        base = {"RUNS_DIR": str(self.tmp / "runs"), "SIGNING_KEY_PATH": str(self.tmp / "none.key"),
                "PORTAL_PORT": "18081", "INTERCEPTOR_PORT": "18091"}
        base.update(env)
        with mock.patch.dict(os.environ, base):
            return {name: (st, detail) for st, name, detail in preflight.checks(env_path=self.tmp / ".env")}

    def test_missing_pieces_are_named_with_what_to_do(self):
        got = self.run_with()
        self.assertEqual(got[".env"][0], preflight.FAIL)
        self.assertIn(".env.example", got[".env"][1])
        self.assertEqual(got["owner key"][0], preflight.WARN)
        self.assertIn("testigo keygen", got["owner key"][1])
        self.assertEqual(got["runs folder"][0], preflight.OK)
        self.assertEqual(got["rules in force"][0], preflight.OK)

    def test_same_port_twice_fails(self):
        got = self.run_with(PORTAL_PORT="18095", INTERCEPTOR_PORT="18095")
        self.assertEqual(got["ports"][0], preflight.FAIL)

    def test_untrusted_rules_fail_with_the_way_out(self):
        active = self.tmp / "runs" / "policy" / "active.policy.yaml"
        active.parent.mkdir(parents=True)
        active.write_text("version: 1\nowner: someone\n")
        got = self.run_with()
        self.assertEqual(got["rules in force"][0], preflight.FAIL)
        self.assertIn("Restore the demo's rules", got["rules in force"][1])

    def test_report_never_prints_a_secret(self):
        with mock.patch.dict(os.environ, {"META_API_KEY": "sk-should-never-show", "RUNS_DIR": str(self.tmp)}):
            lines, _ = preflight.report(preflight.checks(env_path=self.tmp / ".env"))
        self.assertNotIn("sk-should-never-show", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
