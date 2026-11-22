"""Deteksi platform: target build, device inferensi, lokasi ffmpeg."""

import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import platform_support  # noqa: E402

TRIPLES = {
    "aarch64-apple-darwin",
    "x86_64-apple-darwin",
    "x86_64-pc-windows-msvc",
    "aarch64-pc-windows-msvc",
    "x86_64-unknown-linux-gnu",
    "aarch64-unknown-linux-gnu",
}


def load_setup():
    spec = importlib.util.spec_from_file_location("dikte_setup", ROOT / "scripts/setup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PlatformTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.setup = load_setup()

    def test_target_is_known(self):
        triple = self.setup.target()
        self.assertIn(triple, TRIPLES, f"target tidak dikenal: {triple}")

    def test_asset_url(self):
        url = self.setup.asset_url("x86_64-pc-windows-msvc")
        self.assertIn("cpython-3.12.16", url)
        self.assertIn("x86_64-pc-windows-msvc", url)
        self.assertTrue(url.startswith("https://github.com/astral-sh/python-build-standalone"))

    def test_device_is_valid(self):
        device, compute = platform_support.detect_device()
        self.assertIn(device, {"mps", "cuda", "cpu"})
        self.assertIn(compute, {"float16", "int8"})
        if device == "cpu":
            self.assertEqual(compute, "int8")

    def test_device_override(self):
        self.assertEqual(platform_support.detect_device("cpu", ""), ("cpu", "int8"))
        self.assertEqual(platform_support.detect_device("cuda", "int8"), ("cuda", "int8"))

    def test_ffmpeg_bin_returns_string(self):
        self.assertIsInstance(platform_support.ffmpeg_bin(), str)
        self.assertTrue(platform_support.ffmpeg_bin())

    def test_venv_bin_dir(self):
        path = platform_support.venv_bin_dir(str(ROOT))
        expected = "Scripts" if sys.platform.startswith("win") else "bin"
        self.assertTrue(path.endswith(expected), path)


if __name__ == "__main__":
    unittest.main()
