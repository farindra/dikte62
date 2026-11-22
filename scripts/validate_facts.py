"""Validasi facts.json terhadap aturan inti (tanpa dependensi eksternal).

Fokus pada hal yang paling berbahaya: item tanpa bukti, timestamp ngawur,
enum salah, dan ID duplikat. Skema lengkap ada di schema/facts.schema.json.
"""

import argparse
import json
import re
import sys

TS = re.compile(r"^[0-9]{2}:[0-9]{2}:[0-9]{2}$")
PRIORITY = {"must", "should", "could", "wont"}
REQ_TYPE = {"functional", "non_functional", "business_rule"}
CONF = {"high", "medium", "low"}
OWNER_CONF = {"explicit", "inferred", "unknown"}

REQUIRED = [
    ("decisions", "D-"),
    ("requirements", "R-"),
    ("action_items", "A-"),
    ("open_questions", "Q-"),
]


def check_evidence(errors: list, where: str, item: dict, mandatory: bool = True) -> None:
    ev = item.get("evidence") or []
    if not ev:
        if mandatory:
            errors.append(f"{where}: tidak punya evidence")
        return
    for j, e in enumerate(ev):
        if not TS.match(str(e.get("t", ""))):
            errors.append(f"{where}.evidence[{j}]: timestamp tidak valid ({e.get('t')!r})")
        q = str(e.get("quote", "")).strip()
        if len(q) < 3:
            errors.append(f"{where}.evidence[{j}]: kutipan kosong/terlalu pendek")
        elif len(q.split()) > 25:
            errors.append(f"{where}.evidence[{j}]: kutipan > 25 kata")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("facts")
    a = p.parse_args()

    data = json.load(open(a.facts))
    errors: list[str] = []
    warnings: list[str] = []

    for key in ["meeting", "summary", "decisions", "requirements", "action_items", "open_questions"]:
        if key not in data:
            errors.append(f"top-level: '{key}' hilang")

    meeting = data.get("meeting", {})
    if not meeting.get("topics"):
        warnings.append("meeting.topics kosong — sulit mengelompokkan artefak")
    if not data.get("summary", {}).get("tldr"):
        errors.append("summary.tldr kosong")

    seen_ids: set[str] = set()
    for key, prefix in REQUIRED:
        for i, item in enumerate(data.get(key, []) or []):
            where = f"{key}[{i}]"
            iid = str(item.get("id", ""))
            if not iid.startswith(prefix):
                errors.append(f"{where}.id: harus berawalan '{prefix}' (dapat {iid!r})")
            if iid in seen_ids:
                errors.append(f"{where}.id: duplikat {iid}")
            seen_ids.add(iid)
            if not str(item.get("text") or item.get("task") or item.get("question") or "").strip():
                errors.append(f"{where}: isi kosong")

            if key == "decisions":
                check_evidence(errors, where, item)
                if item.get("confidence") not in CONF:
                    errors.append(f"{where}.confidence: {item.get('confidence')!r} tidak valid")
            elif key == "requirements":
                check_evidence(errors, where, item)
                if item.get("type") not in REQ_TYPE:
                    errors.append(f"{where}.type: {item.get('type')!r} tidak valid")
                if item.get("priority") not in PRIORITY:
                    errors.append(f"{where}.priority: {item.get('priority')!r} tidak valid")
                if item.get("confidence") not in CONF:
                    errors.append(f"{where}.confidence: {item.get('confidence')!r} tidak valid")
            elif key == "action_items":
                check_evidence(errors, where, item)
                if item.get("owner_confidence") not in OWNER_CONF:
                    errors.append(f"{where}.owner_confidence: {item.get('owner_confidence')!r} tidak valid")
                if item.get("status") not in {"open", "done", "blocked"}:
                    errors.append(f"{where}.status: {item.get('status')!r} tidak valid")
                if item.get("owner_confidence") == "inferred":
                    warnings.append(f"{where}: owner masih terduga — konfirmasi sebelum dikirim")
            elif key == "open_questions":
                if item.get("status") not in {"unanswered", "needs_confirmation", "answered"}:
                    errors.append(f"{where}.status: {item.get('status')!r} tidak valid")

    print(f"decisions={len(data.get('decisions') or [])} requirements={len(data.get('requirements') or [])} "
          f"actions={len(data.get('action_items') or [])} questions={len(data.get('open_questions') or [])}")

    for w in warnings:
        print("WARN :", w)
    for e in errors:
        print("ERROR:", e)

    print(f"\nhasil: {'LULUS' if not errors else 'GAGAL'} ({len(errors)} error, {len(warnings)} warning)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
