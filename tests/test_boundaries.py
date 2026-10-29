"""F0 §8 and §10: two boundaries enforced as tests.

1. Only common/meta_client.py creates an API client, and only it and
   common/config.py touch META_API_KEY (scripts/check_secrets.py names it to
   look for leaks).
2. No product module imports test data from tests/. Unit tests (test_*.py)
   next to the code may, product code may not.
"""

import re
import unittest

from common.config import ROOT

PRODUCT_DIRS = ("common", "portal", "agent", "interceptor", "receipts", "policy",
                "approval", "gate", "scripts")
KEY_ALLOWED = {"common/config.py", "common/meta_client.py", "scripts/check_secrets.py"}
CLIENT_ALLOWED = {"common/meta_client.py"}


def product_files():
    for d in PRODUCT_DIRS:
        for p in sorted((ROOT / d).rglob("*.py")):
            if p.name.startswith("test_"):
                continue
            yield p.relative_to(ROOT).as_posix(), p.read_text(encoding="utf-8")


class BoundaryTests(unittest.TestCase):
    def test_single_api_client(self):
        bad = [rel for rel, text in product_files()
               if re.search(r"\bOpenAI\s*\(", text) and rel not in CLIENT_ALLOWED]
        self.assertEqual(bad, [])

    def test_api_key_only_in_config_and_client(self):
        bad = [rel for rel, text in product_files()
               if ("META_API_KEY" in text or "meta_api_key" in text) and rel not in KEY_ALLOWED]
        self.assertEqual(bad, [])

    def test_no_test_data_in_product(self):
        pat = re.compile(r"^\s*(from|import)\s+tests(\.|\s|$)", re.MULTILINE)
        bad = [rel for rel, text in product_files() if pat.search(text)]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
