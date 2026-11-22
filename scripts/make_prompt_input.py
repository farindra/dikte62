"""Ubah hasil transkripsi (.json) menjadi teks ber-timestamp untuk prompt LLM."""

import argparse
import json
import os


def fmt(t: float) -> str:
    h, rem = divmod(float(t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("transcript_json")
    p.add_argument("-o", "--out", default="-")
    p.add_argument("--speakers", default="", help="JSON {S1: 'Nama', ...}")
    a = p.parse_args()

    data = json.load(open(a.transcript_json))
    names = json.load(open(a.speakers)) if a.speakers and os.path.exists(a.speakers) else {}
    segs = data.get("segments_data") or data.get("segments") or []
    lines = []
    for s in segs:
        spk = s.get("speaker")
        label = names.get(spk) or spk
        prefix = f"{label}: " if spk else ""
        lines.append(f"[{fmt(s['start'])}] {prefix}{s['text'].strip()}")
    text = "\n".join(lines) + "\n"

    if a.out == "-":
        print(text)
    else:
        with open(a.out, "w") as f:
            f.write(text)
        print(f"{len(segs)} segmen → {a.out}")


if __name__ == "__main__":
    main()
