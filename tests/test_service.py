"""F0 §14.1: the interceptor service answers with its status page (now at /status;
/ is the F11 interface)."""

import unittest

from fastapi.testclient import TestClient

from interceptor.service import app


class ServiceTests(unittest.TestCase):
    def test_status_page_and_health(self):
        c = TestClient(app)
        r = c.get("/status")
        self.assertEqual(r.status_code, 200)
        self.assertIn("TESTIGO+ interceptor", r.text)
        h = c.get("/health").json()
        self.assertEqual(h["service"], "interceptor")
        self.assertTrue(h["policy_hash_ok"])
        # reports whether variables are set, never their values
        self.assertTrue(all(isinstance(v, bool) for v in h["models_configured"].values()))


if __name__ == "__main__":
    unittest.main()
