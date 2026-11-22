"""Jalankan test per modul dengan batas waktu — dipakai CI di semua OS.

Kenapa per modul: satu modul yang menggantung tidak boleh menahan seluruh job.
Skrip ini juga mengeluarkan anotasi GitHub (`::error::`) sehingga penyebabnya
terlihat tanpa perlu membuka log.
"""

import subprocess
import sys
import time

MODULES = [
    "test_syntax",
    "test_platform",
    "test_validator",
    "test_glossary",
    "test_render",
    "test_server",
]
TIMEOUT = 120


def run_module(mod: str) -> tuple[int, str, float]:
    started = time.time()
    try:
        r = subprocess.run(
            [sys.executable, "-m", "unittest", "-v", mod],
            cwd="tests",
            timeout=TIMEOUT,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return r.returncode, r.stdout, time.time() - started
    except subprocess.TimeoutExpired as e:
        partial = e.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", "replace")
        return 124, f"{partial}\n!! melebihi {TIMEOUT}s", time.time() - started
    except Exception as e:  # noqa: BLE001
        return 1, f"!! gagal menjalankan: {e!r}", time.time() - started


def main() -> int:
    failed = []
    for mod in MODULES:
        code, out, elapsed = run_module(mod)
        print(f"::group::{mod} · {elapsed:.1f}s · exit {code}", flush=True)
        print(out, flush=True)
        print("::endgroup::", flush=True)
        if code:
            failed.append(mod)
            print(f"::error::{mod} gagal (exit {code}, {elapsed:.1f}s)", flush=True)
        else:
            print(f"[ok] {mod} ({elapsed:.1f}s)", flush=True)

    if failed:
        print("::error::modul gagal: " + ", ".join(failed), flush=True)
        return 1
    print("semua modul lulus", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
