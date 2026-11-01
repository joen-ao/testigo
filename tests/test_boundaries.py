"""F0 §8 and §10: two boundaries enforced as tests.

1. Only app/adapters/meta/client.py creates an API client, and only it and
   app/common/config.py touch META_API_KEY (scripts/check_secrets.py names it to
   look for leaks).
2. No product module imports test data from tests/.
3. Nothing in app/core imports app/adapters, app/runtime or app/sim (spec 10). Unit tests (test_*.py)
   next to the code may, product code may not.
"""

import re
import unittest

from app.common.config import ROOT

PRODUCT_DIRS = ("app", "bench", "gate", "scripts")
KEY_ALLOWED = {"app/common/config.py", "app/adapters/meta/client.py", "scripts/check_secrets.py"}
CLIENT_ALLOWED = {"app/adapters/meta/client.py"}


def product_files():
    for d in PRODUCT_DIRS:
        for p in sorted((ROOT / d).rglob("*.py")):
            if p.name.startswith("test_"):
                continue
            yield p.relative_to(ROOT).as_posix(), p.read_text(encoding="utf-8")


# The core never reaches out (spec 10 P1). One allowed exception: the mandate
# compiler's command line builds the Meta client it then hands to the core.
CORE_OUTWARD_ALLOWED = {"app/core/policy/compile.py"}


class BoundaryTests(unittest.TestCase):
    def test_core_imports_no_outer_layer(self):
        pat = re.compile(r"^\s*(from|import)\s+app\.(adapters|runtime|sim)\b", re.MULTILINE)
        bad = [rel for rel, text in product_files()
               if rel.startswith("app/core/") and rel not in CORE_OUTWARD_ALLOWED and pat.search(text)]
        self.assertEqual(bad, [])

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
