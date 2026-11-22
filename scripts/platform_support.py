"""Deteksi platform: ffmpeg, device inferensi, dan path venv.

Dipakai bersama oleh pipeline agar jalan di macOS (Metal), Windows/Linux (CUDA),
dan CPU murni tanpa mengubah kode.
"""

import os
import platform
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _ensure_cache() -> None:
    """Default cache di dalam folder proyek agar tidak menulis ke ~/.cache."""
    base = os.environ.get("DIKTE_CACHE") or os.path.join(ROOT, ".cache")
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        return
    os.environ.setdefault("HF_HOME", os.path.join(base, "huggingface"))
    os.environ.setdefault("XDG_CACHE_HOME", base)


_ensure_cache()


def ffmpeg_bin() -> str:
    """Lokasi binary ffmpeg: env -> imageio-ffmpeg -> PATH."""
    env = os.environ.get("DIKTE_FFMPEG")
    if env and os.path.exists(env):
        return env
    try:
        import imageio_ffmpeg

        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.exists(path):
            return path
    except Exception:  # noqa: BLE001
        pass
    found = shutil.which("ffmpeg")
    return found or "ffmpeg"


def venv_bin_dir(root: str | None = None) -> str:
    root = root or ROOT
    return os.path.join(root, ".venv", "Scripts" if os.name == "nt" else "bin")


def detect_device(prefer: str = "auto", compute: str = "") -> tuple[str, str]:
    """Pilih device + compute type terbaik yang tersedia.

    Urutan: mps (macOS Apple Silicon) -> cuda -> cpu.
    """
    if prefer and prefer != "auto":
        if compute:
            return prefer, compute
        return prefer, ("float16" if prefer in ("mps", "cuda") else "int8")

    try:
        import torch
    except Exception:  # noqa: BLE001
        return "cpu", compute or "int8"

    if (
        platform.system() == "Darwin"
        and platform.machine() in ("arm64", "aarch64")
        and getattr(torch.backends, "mps", None)
        and torch.backends.mps.is_available()
    ):
        return "mps", compute or "float16"

    if torch.cuda.is_available():
        return "cuda", compute or "float16"

    return "cpu", compute or "int8"


def describe() -> str:
    device, compute = detect_device()
    return (
        f"{platform.system()} {platform.machine()} · python {sys.version.split()[0]} · "
        f"device {device}/{compute} · ffmpeg {ffmpeg_bin()}"
    )


if __name__ == "__main__":
    print(describe())
