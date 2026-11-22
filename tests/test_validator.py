"""Validator fakta: menolak item tanpa bukti, menerima data yang benar."""

import copy
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import fixtures  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_facts.py"


def run(facts: dict) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(facts, f)
        path = f.name
    r = subprocess.run([sys.executable, str(VALIDATOR), path],
                       capture_output=True, text=True, timeout=120)
    pathlib.Path(path).unlink(missing_ok=True)
    return r.returncode, r.stdout + r.stderr


class ValidatorTest(unittest.TestCase):
    def test_valid_facts_pass(self):
        code, out = run(fixtures.FACTS)
        self.assertEqual(code, 0, out)
        self.assertIn("LULUS", out)

    def test_missing_evidence_fails(self):
        bad = copy.deepcopy(fixtures.FACTS)
        bad["decisions"][0]["evidence"] = []
        code, out = run(bad)
        self.assertEqual(code, 1, out)
        self.assertIn("punya evidence", out)

    def test_bad_timestamp_fails(self):
        bad = copy.deepcopy(fixtures.FACTS)
        bad["requirements"][0]["evidence"] = [{"t": "4 detik", "quote": "limit 20%"}]
        code, out = run(bad)
        self.assertEqual(code, 1, out)
        self.assertIn("timestamp", out)

    def test_bad_priority_fails(self):
        bad = copy.deepcopy(fixtures.FACTS)
        bad["requirements"][0]["priority"] = "urgent"
        code, out = run(bad)
        self.assertEqual(code, 1, out)
        self.assertIn("priority", out)

    def test_duplicate_ids_fail(self):
        bad = copy.deepcopy(fixtures.FACTS)
        bad["decisions"].append(copy.deepcopy(bad["decisions"][0]))
        code, out = run(bad)
        self.assertEqual(code, 1, out)
        self.assertIn("duplikat", out)

    def test_inferred_owner_is_warning_only(self):
        facts = copy.deepcopy(fixtures.FACTS)
        facts["action_items"][0]["owner_confidence"] = "inferred"
        code, out = run(facts)
        self.assertEqual(code, 0, out)
        self.assertIn("WARN", out)


if __name__ == "__main__":
    unittest.main()
