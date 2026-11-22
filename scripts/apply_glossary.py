"""Terapkan glosarium ke transkrip (hanya entri 'confirmed') + laporkan istilah tentative."""

import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import platform_support  # noqa: E402,F401  (stdout UTF-8 + cache default)

import argparse
import json
import re
import sys


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("transcript")
    p.add_argument("--glossary", default="glossary.json")
    p.add_argument("-o", "--out", default="")
    a = p.parse_args()

    g = json.load(open(a.glossary, encoding="utf-8"))
    text = open(a.transcript, encoding="utf-8").read()
    original = text

    print("[glosarium] penggantian yang diterapkan:")
    for item in g.get("confirmed", []):
        src, dst = item["from"], item["to"]
        if src.lower() == dst.lower():
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(src)}(?!\w)", re.IGNORECASE)
        text, n = pattern.subn(dst, text)
        if n:
            print(f"  {src!r} → {dst!r}: {n}x  ({item.get('note','')})")

    tentative = g.get("tentative", [])
    if tentative:
        print("\n[perlu konfirmasi] istilah belum pasti (tidak diubah otomatis):")
        low = original.lower()
        for item in tentative:
            n = len(re.findall(rf"(?<!\w){re.escape(item['from'])}(?!\w)", low, re.IGNORECASE))
            if n:
                print(f"  {item['from']!r} ({n}x) — {item.get('note','')}")

    out = a.out or a.transcript.replace(".txt", "") + "_glossary.txt"
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\n[ok] {out}")


if __name__ == "__main__":
    sys.exit(main())
