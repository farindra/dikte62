"""Render dokumen: BRD, Epic/Story, ringkasan, dan CSV Jira."""

import csv
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import fixtures  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
RENDER = ROOT / "scripts" / "render_docs.py"


class RenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = pathlib.Path(cls.tmp.name)
        facts = tmp / "facts.json"
        arts = tmp / "artifacts.json"
        facts.write_text(json.dumps(fixtures.FACTS))
        arts.write_text(json.dumps(fixtures.ARTIFACTS))
        cls.out = tmp / "docs"
        r = subprocess.run([sys.executable, str(RENDER), str(facts), str(arts),
                            "--outdir", str(cls.out)],
                           capture_output=True, text=True, timeout=120)
        cls.result = r

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_render_succeeds(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        self.assertIn("jira_import.csv", self.result.stdout)

    def test_files_created(self):
        for name in ["BRD.md", "EPIC-STORY.md", "RINGKASAN.md", "jira_import.csv"]:
            with self.subTest(name=name):
                path = self.out / name
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 50)

    def test_brd_contains_requirement_and_refs(self):
        brd = (self.out / "BRD.md").read_text()
        self.assertIn("BRD Rapat Uji CI", brd)
        self.assertIn("BR-01", brd)
        self.assertIn("R-01", brd)
        self.assertIn("Q-01", brd)

    def test_story_has_gherkin(self):
        story = (self.out / "EPIC-STORY.md").read_text()
        self.assertIn("US-01", story)
        self.assertIn("Given", story)
        self.assertIn("then", story)

    def test_csv_shape(self):
        with open(self.out / "jira_import.csv", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0][:5], ["Issue Type", "Summary", "Description", "Priority", "Epic Name"])
        types = [r[0] for r in rows[1:]]
        self.assertIn("Epic", types)
        self.assertIn("Story", types)
        self.assertEqual(len(types), 2)  # 1 epic + 1 story di fixture


if __name__ == "__main__":
    unittest.main()
