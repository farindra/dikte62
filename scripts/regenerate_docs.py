"""Bangun ulang dokumen (BRD/Epic/Story/DOCX) untuk rapat yang sudah ada.

Dipakai setelah pengguna memberi nama speaker di UI: transkrip tidak diulang,
hanya tahap LLM yang dijalankan kembali sehingga owner action item memakai nama.

Jalankan: python scripts/regenerate_docs.py --id <meeting-id> --jobdir <dir>
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_pipeline import PY, Job, ROOT, load_env, model_order, run  # noqa: E402

MODELS_EXTRACT = model_order(("gemini-3.6-flash", "gemini-3.1-flash-lite", "gemini-3.8-flash"))
MODELS_ARTIFACTS = MODELS_EXTRACT


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--id", required=True)
    p.add_argument("--jobdir", required=True)
    a = p.parse_args()

    load_env()
    try:
        import settings_store as cfg
        cfg.apply_env()
    except Exception:
        pass
    os.environ["PATH"] = os.path.join(ROOT, ".venv", "bin") + os.pathsep + os.environ.get("PATH", "")
    os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".cache", "huggingface"))

    base = os.path.join(ROOT, ".data", "meetings", a.id)
    os.makedirs(a.jobdir, exist_ok=True)
    job = Job(a.jobdir)

    if not os.path.exists(os.path.join(base, "meta.json")):
        job.fail(f"rapat {a.id} tidak ditemukan")
        return

    meta = json.load(open(os.path.join(base, "meta.json")))
    transcript = os.path.join(base, "transcript.json")
    speakers = os.path.join(base, "speakers.json")
    tmp = os.path.join(a.jobdir, "out")
    docs = os.path.join(a.jobdir, "docs")
    os.makedirs(tmp, exist_ok=True)
    os.makedirs(docs, exist_ok=True)

    try:
        job.done("menyiapkan prompt", 10)
        prompt = os.path.join(tmp, "prompt.txt")
        cmd = [PY, "scripts/make_prompt_input.py", transcript, "-o", prompt]
        if os.path.exists(speakers):
            cmd += ["--speakers", speakers]
        run(cmd)

        job.done("glosarium", 15)
        gloss = os.path.join(tmp, "prompt_glossary.txt")
        run([PY, "scripts/apply_glossary.py", prompt, "--glossary", "glossary.json", "-o", gloss])

        facts = os.path.join(a.jobdir, "facts.json")
        last = None
        for model in MODELS_EXTRACT:
            try:
                job.done("ekstraksi fakta", 25, f"model {model}")
                run([PY, "scripts/extract_facts.py", gloss, "--out", facts, "--model", model,
                     "--date", meta.get("date") or time.strftime("%Y-%m-%d"),
                     "--project", "Rapat internal",
                     "--glossary", "Rempoa = kantor cabang; PKWT/PKWTT = jenis kontrak kerja"],
                    timeout=420)
                break
            except RuntimeError as e:  # noqa: PERF203
                last = e
        if not os.path.exists(facts):
            job.fail(f"ekstraksi gagal: {str(last)[:300]}")
            return

        job.done("validasi", 60)
        try:
            run([PY, "scripts/validate_facts.py", facts])
        except RuntimeError:
            pass

        arts = os.path.join(a.jobdir, "artifacts.json")
        last_a = None
        for model in MODELS_ARTIFACTS:
            try:
                job.done("artefak", 70, f"model {model}")
                run([PY, "scripts/generate_artifacts.py", facts, "--out", arts, "--model", model],
                    timeout=420)
                break
            except RuntimeError as e:  # noqa: PERF203
                last_a = e
        if not os.path.exists(arts):
            job.fail(f"generasi artefak gagal: {str(last_a)[:300]}")
            return

        job.done("render", 88)
        run([PY, "scripts/render_docs.py", facts, arts, "--outdir", docs])

        job.done("docx", 93)
        run([PY, "scripts/md_to_docx.py", os.path.join(docs, "BRD.md"),
             os.path.join(docs, "EPIC-STORY.md"), os.path.join(docs, "RINGKASAN.md"),
             "--outdir", docs])

        job.done("menyimpan", 97)
        run([PY, "scripts/pack_meeting.py", "--id", a.id, "--facts", facts,
             "--artifacts", arts, "--transcript", transcript,
             "--audio", meta.get("audio", ""), "--docs", docs])

        job.finish(a.id)
    except Exception as e:  # noqa: BLE001
        job.fail(str(e)[:1500])


if __name__ == "__main__":
    main()
