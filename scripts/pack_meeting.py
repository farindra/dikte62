"""Bungkus hasil satu rapat ke .data/meetings/<id>/ agar bisa dibaca UI.

Struktur yang dihasilkan:
  .data/meetings/<id>/meta.json
  .data/meetings/<id>/facts.json
  .data/meetings/<id>/artifacts.json
  .data/meetings/<id>/transcript.json
  .data/meetings/<id>/BRD.md / EPIC-STORY.md / RINGKASAN.md / *.docx / jira_import.csv
"""

import argparse
import json
import os
import shutil

DOCS = {
    "brd": "BRD.md",
    "epics": "EPIC-STORY.md",
    "summary": "RINGKASAN.md",
    "jira": "jira_import.csv",
    "brd_docx": "BRD.docx",
    "epics_docx": "EPIC-STORY.docx",
    "summary_docx": "RINGKASAN.docx",
}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--id", required=True)
    p.add_argument("--facts", required=True)
    p.add_argument("--artifacts", required=True)
    p.add_argument("--transcript", required=True)
    p.add_argument("--audio", default="")
    p.add_argument("--docs", default="docs/generated")
    p.add_argument("--root", default=".data/meetings")
    a = p.parse_args()

    dst = os.path.join(a.root, a.id)
    os.makedirs(dst, exist_ok=True)

    def same(x, y):
        return os.path.abspath(x) == os.path.abspath(y)

    facts = json.load(open(a.facts)) if os.path.exists(a.facts) else {}
    if os.path.exists(a.facts):
        if not same(a.facts, os.path.join(dst, "facts.json")):
            shutil.copy(a.facts, os.path.join(dst, "facts.json"))
    else:
        with open(os.path.join(dst, "facts.json"), "w") as f:
            json.dump({}, f)
    if os.path.exists(a.artifacts):
        if not same(a.artifacts, os.path.join(dst, "artifacts.json")):
            shutil.copy(a.artifacts, os.path.join(dst, "artifacts.json"))
    else:
        with open(os.path.join(dst, "artifacts.json"), "w") as f:
            json.dump({}, f)
    if not same(a.transcript, os.path.join(dst, "transcript.json")):
        shutil.copy(a.transcript, os.path.join(dst, "transcript.json"))

    docs = {}
    for key, name in DOCS.items():
        src = os.path.join(a.docs, name)
        if os.path.exists(src) and not same(src, os.path.join(dst, name)):
            shutil.copy(src, os.path.join(dst, name))
            docs[key] = name

    m = facts.get("meeting", {})
    prev = {}
    if os.path.exists(os.path.join(dst, "meta.json")):
        try:
            prev = json.load(open(os.path.join(dst, "meta.json")))
        except Exception:  # noqa: BLE001
            prev = {}
    meta = {
        "created_at": prev.get("created_at") or __import__("time").time(),
        "archived": prev.get("archived", False),
        "id": a.id,
        "title": m.get("title") or a.id,
        "date": m.get("date") or "",
        "duration_min": m.get("duration_min") or 0,
        "topics": m.get("topics") or [],
        "audio": a.audio,
        "docs": docs,
    }
    with open(os.path.join(dst, "meta.json"), "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"[ok] {dst}")
    print(f"     docs: {', '.join(docs.keys())}")
    if a.audio:
        print(f"     audio: {a.audio}")


if __name__ == "__main__":
    main()
