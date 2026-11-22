"""Glosarium: hanya entri 'confirmed' yang diganti; istilah tentative dilaporkan."""

import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "apply_glossary.py"
GLOSSARY = ROOT / "glossary.json"

TEXT = """[00:00:01] S1: rapat anak kelasi ke rempoha
[00:00:05] S2: hitung pakai rubus yang baku
[00:00:09] S1: selesai
"""


class GlossaryTest(unittest.TestCase):
    def test_only_confirmed_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp) / "transcript.txt"
            dst = pathlib.Path(tmp) / "out.txt"
            src.write_text(TEXT, encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(SCRIPT), str(src), "--glossary", str(GLOSSARY),
                 "-o", str(dst)],
                capture_output=True, encoding="utf-8", errors="replace", timeout=120,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            out = dst.read_text(encoding="utf-8")

        self.assertIn("Rempoa", out)
        self.assertNotIn("rempoha", out.lower())
        self.assertIn("rumus", out)
        # 'kelasi' sengaja dibiarkan (belum dikonfirmasi) tetapi dilaporkan
        self.assertIn("kelasi", out)
        self.assertIn("perlu konfirmasi", r.stdout)

    def test_missing_glossary_is_graceful(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp) / "t.txt"
            src.write_text("halo\n", encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(SCRIPT), str(src), "--glossary", str(pathlib.Path(tmp) / "nope.json"),
                 "-o", str(pathlib.Path(tmp) / "o.txt")],
                capture_output=True, encoding="utf-8", errors="replace", timeout=120,
            )
        self.assertNotEqual(r.returncode, 0)  # gagal cepat, bukan crash tak jelas


if __name__ == "__main__":
    unittest.main()
