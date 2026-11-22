"""Semua file Python harus bisa dikompilasi di OS mana pun; JSON harus valid."""

import compileall
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class SyntaxTest(unittest.TestCase):
    def test_scripts_compile(self):
        ok = compileall.compile_dir(str(ROOT / "scripts"), quiet=2, force=True)
        self.assertTrue(ok, "ada file Python yang gagal dikompilasi")

    def test_json_files_parse(self):
        for path in [ROOT / "schema/facts.schema.json", ROOT / "glossary.json"]:
            with self.subTest(path=path.name):
                json.loads(path.read_text())

    def test_required_files_exist(self):
        for name in ["README.md", "LICENSE", "requirements.txt", ".gitignore",
                     "scripts/setup.py", "scripts/server.py", "scripts/platform_support.py",
                     "ui/index.html", "ui/app.js", "ui/style.css"]:
            with self.subTest(name=name):
                self.assertTrue((ROOT / name).exists(), f"{name} hilang")


if __name__ == "__main__":
    unittest.main()
