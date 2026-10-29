"""F0 §6: the variables the code reads are exactly those in .env.example."""

import re
import unittest

from common import clock, config


def example_vars():
    out = {}
    for line in (config.ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Z0-9_]+)=(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


class EnvExampleTests(unittest.TestCase):
    def test_same_variables(self):
        self.assertEqual(set(example_vars()), set(config.ENV_VARS))

    def test_no_secret_values_in_example(self):
        ex = example_vars()
        for name in ("META_API_KEY", "META_API_BASE_URL", "SCORER_TOKEN"):
            self.assertEqual(ex[name], "", name)

    def test_defaults_match_example(self):
        ex = example_vars()
        for name, default in config.ENV_VARS.items():
            self.assertEqual(ex[name], default, name)

    def test_undeclared_variable_is_refused(self):
        with self.assertRaises(KeyError):
            config.get("NOT_A_REAL_VARIABLE")


class PathAndClockTests(unittest.TestCase):
    def test_paths_resolve_from_repo_root(self):
        s = config.settings()
        self.assertTrue(config.POLICY_PATH.is_file())
        self.assertTrue(str(s.signing_key_path).startswith(str(config.ROOT)))
        self.assertTrue(str(s.runs_dir).startswith(str(config.ROOT)))

    def test_bogota_offset(self):
        self.assertTrue(clock.iso().endswith("-05:00"))


if __name__ == "__main__":
    unittest.main()
