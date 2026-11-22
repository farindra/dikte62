"""Orkestrator pipeline lengkap untuk satu file rekaman, dipanggil oleh server/UI.

Tahapan: transkrip → teks prompt → glosarium → ekstraksi fakta → validasi →
artefak (BRD/Epic/Story) → render Markdown/CSV → DOCX → bungkus untuk UI.

Progres ditulis ke <jobdir>/job.json agar bisa dipantau UI.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PY = sys.executable

def model_order(defaults: tuple) -> tuple:
    pref = os.environ.get("GEMINI_MODEL", "").strip()
    return tuple(dict.fromkeys(([pref] + list(defaults)) if pref else list(defaults)))


STEPS = [
    ("transcribe", 50),
    ("diarisasi", 10),
    ("prompt", 2),
    ("glossary", 2),
    ("extract", 12),
    ("validate", 2),
    ("artifacts", 12),
    ("render", 5),
    ("docx", 4),
    ("pack", 2),
]


def load_env() -> None:
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


class Job:
    def __init__(self, jobdir: str):
        self.path = os.path.join(jobdir, "job.json")
        self.data = {
            "state": "running",
            "progress": 0,
            "step": "mulai",
            "message": "",
            "started": time.time(),
            "finished": None,
            "meeting_id": "",
            "error": "",
            "log": [],
        }
        self._write()

    def _write(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    def done(self, step: str, progress: int, message: str = "") -> None:
        self.data.update(step=step, progress=progress, message=message)
        self.data["log"].append(f"{time.strftime('%H:%M:%S')} {progress:3d}% {step} {message}")
        self._write()
        print(f"[{progress:3d}%] {step} {message}", flush=True)

    def finish(self, meeting_id: str = "") -> None:
        self.data.update(state="done", progress=100, step="selesai", meeting_id=meeting_id,
                         finished=time.time())
        self._write()

    def partial(self, message: str, meeting_id: str = "") -> None:
        self.data.update(state="partial", progress=100, step="transkrip selesai", message=message,
                         meeting_id=meeting_id, finished=time.time())
        self._write()

    def fail(self, message: str) -> None:
        self.data.update(state="error", error=message, finished=time.time())
        self._write()


def run(cmd: list[str], job: Job | None = None, base: int = 0, span: int = 0,
        parse_windows: bool = False, timeout: int | None = None) -> str:
    """Jalankan subprocess, kembalikan stdout. Bila job+parse_windows, perbarui progres."""
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1, env=os.environ.copy())
    deadline = time.time() + timeout if timeout else None
    out = []
    assert proc.stdout is not None
    for line in proc.stdout:
        out.append(line)
        if job and parse_windows:
            m = re.search(r"\[win (\d+)/(\d+)\]", line)
            if m:
                cur, total = int(m.group(1)), int(m.group(2))
                job.done("transkrip", base + int(span * cur / max(total, 1)),
                         f"jendela {cur}/{total}")
    while proc.poll() is None:
        if deadline and time.time() > deadline:
            proc.kill()
            raise RuntimeError(f"timeout {timeout}s: {' '.join(cmd[1:3])}")
        time.sleep(0.5)
    code = proc.poll()
    if code != 0:
        tail = "".join(out)[-700:]
        raise RuntimeError(f"gagal: {' '.join(cmd[:2])}\n{tail}")
    return "".join(out)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--audio", required=True)
    p.add_argument("--jobdir", required=True)
    p.add_argument("--id", default="")
    a = p.parse_args()

    load_env()
    os.environ["PATH"] = os.path.join(ROOT, ".venv", "bin") + os.pathsep + os.environ.get("PATH", "")
    os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".cache", "huggingface"))
    os.makedirs(a.jobdir, exist_ok=True)
    job = Job(a.jobdir)

    meeting_id = a.id or re.sub(r"[^A-Za-z0-9_]", "_", os.path.splitext(os.path.basename(a.audio))[0])
    out = os.path.join(a.jobdir, "out")
    docs = os.path.join(a.jobdir, "docs")
    os.makedirs(out, exist_ok=True)
    os.makedirs(docs, exist_ok=True)

    try:
        job.done("transkrip", 3, "memulai transkripsi")
        run([PY, "-u", "scripts/transcribe_robust.py", a.audio, "--outdir", out],
            job, base=3, span=55, parse_windows=True)

        transcript = os.path.join(out, meeting_id + ".json")
        if os.environ.get("DIKTE_DIARIZE", "1") == "1":
            try:
                job.done("diarisasi", 58, "melabeli pembicara")
                run([PY, "-u", "scripts/diarize.py", a.audio, transcript,
                     "-o", os.path.join(out, meeting_id + "_speakers.json")], timeout=1800)
                transcript = os.path.join(out, meeting_id + "_speakers.json")
            except RuntimeError as e:
                job.done("diarisasi", 60, f"dilewati: {str(e)[:80]}")

        job.done("teks", 62)
        run([PY, "scripts/make_prompt_input.py", transcript,
             "-o", os.path.join(out, "prompt.txt")])

        job.done("glosarium", 62)
        gloss = os.path.join(out, "prompt_glossary.txt")
        run([PY, "scripts/apply_glossary.py", os.path.join(out, "prompt.txt"),
             "--glossary", "glossary.json", "-o", gloss])

        if not os.environ.get("GEMINI_API_KEY"):
            raise RuntimeError("GEMINI_API_KEY tidak ditemukan di .env — tahap ekstraksi dilewati")

        job.done("ekstraksi fakta", 66, "memanggil LLM")
        facts = os.path.join(a.jobdir, "facts.json")
        arts = os.path.join(a.jobdir, "artifacts.json")
        last = None
        for model in model_order(("gemini-3.6-flash", "gemini-3.1-flash-lite", "gemini-3.8-flash")):
            try:
                job.done("ekstraksi fakta", 66, f"model {model}")
                run([PY, "scripts/extract_facts.py", gloss, "--out", facts, "--model", model,
                     "--date", time.strftime("%Y-%m-%d"), "--project", "Rapat internal",
                     "--glossary", "Rempoa = kantor cabang; PKWT/PKWTT = jenis kontrak kerja"],
                    timeout=420)
                break
            except RuntimeError as e:  # noqa: PERF203
                last = e
        if not os.path.exists(facts):
            job.done("dokumen", 88, "LLM tidak tersedia — transkrip tetap disimpan")
            run([PY, "scripts/pack_meeting.py", "--id", meeting_id, "--facts", facts,
                 "--artifacts", arts, "--transcript", os.path.join(out, meeting_id + ".json"),
                 "--audio", os.path.relpath(a.audio, ROOT), "--docs", docs])
            job.partial(f"transkrip selesai, dokumen gagal dibuat: {str(last)[:200]}", meeting_id)
            return

        job.done("validasi", 78)
        try:
            run([PY, "scripts/validate_facts.py", facts])
        except RuntimeError as e:
            job.done("validasi", 78, "peringatan validasi (dilanjutkan)")

        job.done("artefak", 82, "menyusun BRD/Epic/Story")
        last_a = None
        for model in model_order(("gemini-3.6-flash", "gemini-3.1-flash-lite", "gemini-3.8-flash")):
            try:
                job.done("artefak", 82, f"model {model}")
                run([PY, "scripts/generate_artifacts.py", facts, "--out", arts, "--model", model],
                    timeout=420)
                break
            except RuntimeError as e:  # noqa: PERF203
                last_a = e
        if not os.path.exists(arts):
            job.done("dokumen", 88, "LLM tidak tersedia — transkrip tetap disimpan")
            run([PY, "scripts/pack_meeting.py", "--id", meeting_id, "--facts", facts,
                 "--artifacts", arts, "--transcript", os.path.join(out, meeting_id + ".json"),
                 "--audio", os.path.relpath(a.audio, ROOT), "--docs", docs])
            job.partial(f"transkrip selesai, dokumen gagal dibuat: {str(last_a)[:200]}", meeting_id)
            return

        job.done("render", 90)
        run([PY, "scripts/render_docs.py", facts, arts, "--outdir", docs])

        job.done("docx", 95)
        run([PY, "scripts/md_to_docx.py",
             os.path.join(docs, "BRD.md"), os.path.join(docs, "EPIC-STORY.md"),
             os.path.join(docs, "RINGKASAN.md"), "--outdir", docs])

        job.done("kemas", 98)
        run([PY, "scripts/pack_meeting.py", "--id", meeting_id, "--facts", facts,
             "--artifacts", arts, "--transcript", transcript,
             "--audio", os.path.relpath(a.audio, ROOT), "--docs", docs])

        job.finish(meeting_id)
    except Exception as e:  # noqa: BLE001
        job.fail(str(e)[:1500])


if __name__ == "__main__":
    main()
