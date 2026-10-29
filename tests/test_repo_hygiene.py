"""F0 §7: nothing secret or evidential in the files that would be committed."""

import tempfile
import unittest
from pathlib import Path

from common.config import ROOT
from scripts.check_secrets import scan


class RepoHygieneTests(unittest.TestCase):
    def test_working_tree_is_clean(self):
        findings = scan(ROOT)
        self.assertEqual(findings, [], "\n".join("%s: %s" % f for f in findings))

    def test_scan_catches_planted_secrets(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".gitignore").write_text((ROOT / ".gitignore").read_text())
            (root / "leak.txt").write_text("META_API_KEY=abc123\n")
            (root / "id.pem").write_text("-----BEGIN PRIVATE" + " KEY-----\nxx\n")
            (root / "notes.md").write_text("META_API_KEY=   # empty is fine\n")
            names = {rel for rel, _ in scan(root)}
            self.assertIn("leak.txt", names)
            self.assertIn("id.pem", names)
            self.assertNotIn("notes.md", names)

    def test_ignored_secret_locations_are_not_findings(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".gitignore").write_text((ROOT / ".gitignore").read_text())
            (root / ".secrets").mkdir()
            (root / ".secrets" / "receipts.key").write_text("00" * 32)
            (root / ".env").write_text("META_API_KEY=abc123\n")
            (root / "runs" / "evidence").mkdir(parents=True)
            (root / "runs" / "evidence" / "crop.png").write_bytes(b"x")
            self.assertEqual(scan(root), [])

    def test_gitignore_has_required_patterns(self):
        text = (ROOT / ".gitignore").read_text()
        for pat in (".env", ".secrets/", "*.key", "runs/", "evidence/", "!.env.example"):
            self.assertIn(pat, text.splitlines())


if __name__ == "__main__":
    unittest.main()
