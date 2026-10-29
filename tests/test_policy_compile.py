"""F1: building and signing a policy offline (the voice path needs the API)."""

import unittest

from interceptor.policy import Policy
from policy.compile import build_policy_dict, sign_policy_dict, to_yaml
from receipts import keys


class CompileTests(unittest.TestCase):
    def setUp(self):
        self.d = build_policy_dict(
            "Solo puedes pagarle a Distribuidora X, máximo ciento cincuenta mil pesos",
            [{"name": "Distribuidora X", "account": "310-XXX-4417"}],
            150000, "new_recipient")

    def test_build_shape(self):
        p = Policy(self.d)
        self.assertEqual(p.pay_only, [{"name": "Distribuidora X", "account": "310-XXX-4417"}])
        self.assertEqual(p.max_per_payment_cop, 150000)
        self.assertEqual(p.ask_before, "new_recipient")

    def test_sign_and_verify(self):
        seed = keys.generate_seed()
        signed, p = sign_policy_dict(self.d, seed)
        self.assertTrue(p.hash_matches_stored())
        self.assertTrue(p.signature_valid(keys.public_from_seed(seed)))
        self.assertFalse(p.signature_valid(keys.public_from_seed(keys.generate_seed())))

    def test_roundtrip_through_yaml(self):
        import yaml
        seed = keys.generate_seed()
        signed, _ = sign_policy_dict(self.d, seed)
        reloaded = Policy(yaml.safe_load(to_yaml(signed)))
        self.assertTrue(reloaded.hash_matches_stored())
        self.assertTrue(reloaded.signature_valid(keys.public_from_seed(seed)))

    def test_account_binding_blocks_name_only_swap(self):
        p = Policy(self.d)
        self.assertTrue(p.recipient_allowed("Distribuidora X · 310-XXX-4417"))
        self.assertFalse(p.recipient_allowed("Distribuidora X · 300-XXX-0000"))


if __name__ == "__main__":
    unittest.main()
