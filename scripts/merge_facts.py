"""Gabungkan beberapa hasil ekstraksi (ensemble) untuk menaikkan recall.

Ekstraksi LLM bersifat stokastik: satu kali jalan bisa melewatkan action item yang
ditangkap jalan lain. Menggabungkan dua hasil meningkatkan cakupan; duplikat
dibuang berdasarkan kemiripan teks, lalu ID dinomori ulang.
"""

import argparse
import difflib
import json
import re

FIELDS = {
    "decisions": ("D", "id", "text"),
    "requirements": ("R", "id", "text"),
    "action_items": ("A", "id", "task"),
    "open_questions": ("Q", "id", "question"),
}


def norm(s: str) -> str:
    return re.sub(r"\W+", " ", (s or "").lower()).strip()


def similar(a: str, b: str, threshold: float = 0.62) -> bool:
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio() >= threshold


def merge(primary: dict, secondary: dict) -> tuple[dict, dict]:
    out = json.loads(json.dumps(primary))
    stats = {}
    for field, (prefix, idkey, txtkey) in FIELDS.items():
        base = out.get(field, []) or []
        added = 0
        for item in secondary.get(field, []) or []:
            if not any(similar(item.get(txtkey, ""), x.get(txtkey, "")) for x in base):
                base.append(item)
                added += 1
        for i, x in enumerate(base, 1):
            x[idkey] = f"{prefix}-{i:02d}"
        out[field] = base
        stats[field] = {"total": len(base), "added": added}
    return out, stats


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("primary")
    p.add_argument("secondary")
    p.add_argument("-o", "--out", default=".data/facts.merged.json")
    a = p.parse_args()

    p1 = json.load(open(a.primary))
    p2 = json.load(open(a.secondary))
    merged, stats = merge(p1, p2)

    with open(a.out, "w") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"[ok] {a.out}")
    for k, v in stats.items():
        print(f"  {k:16s} total={v['total']:2d} (+{v['added']} dari run kedua)")


if __name__ == "__main__":
    main()
