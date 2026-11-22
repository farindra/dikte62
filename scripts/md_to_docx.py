"""Konversi Markdown sederhana (heading, bullet, tabel, bold) menjadi .docx."""

import argparse
import os
import re

from docx import Document
from docx.shared import Pt, RGBColor


def add_runs(par, text: str) -> None:
    """Tangani **bold** sederhana."""
    for i, chunk in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
        if not chunk:
            continue
        run = par.add_run(chunk)
        if i % 2 == 1:
            run.bold = True


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def convert(md: str, title: str = "") -> Document:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("|"):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            rows = [split_row(b) for b in block if not re.match(r"^\|[\s\-:|]+\|$", b)]
            if rows:
                ncol = max(len(r) for r in rows)
                table = doc.add_table(rows=0, cols=ncol)
                table.style = "Light Grid Accent 1"
                for ri, row in enumerate(rows):
                    cells = table.add_row().cells
                    for ci in range(ncol):
                        txt = row[ci] if ci < len(row) else ""
                        cells[ci].text = ""
                        par = cells[ci].paragraphs[0]
                        add_runs(par, txt)
                        if ri == 0:
                            for r in par.runs:
                                r.bold = True
                doc.add_paragraph()
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            h = doc.add_heading(level=min(level, 4))
            add_runs(h, m.group(2))
            i += 1
            continue

        if stripped.startswith(("- ", "* ")):
            par = doc.add_paragraph(style="List Bullet")
            add_runs(par, stripped[2:])
            i += 1
            continue

        if re.match(r"^\d+\.\s", stripped):
            par = doc.add_paragraph(style="List Number")
            add_runs(par, re.sub(r"^\d+\.\s", "", stripped))
            i += 1
            continue

        if stripped.startswith(">"):
            par = doc.add_paragraph()
            run = par.add_run(stripped.lstrip("> ").strip())
            run.italic = True
            run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
            i += 1
            continue

        par = doc.add_paragraph()
        add_runs(par, re.sub(r"^\*(.+)\*$", r"\1", stripped))
        i += 1

    if title:
        doc.core_properties.title = title
    return doc


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("inputs", nargs="+")
    p.add_argument("--outdir", default="docs/generated")
    a = p.parse_args()

    for src in a.inputs:
        md = open(src).read()
        name = os.path.splitext(os.path.basename(src))[0]
        doc = convert(md, title=name)
        dst = os.path.join(a.outdir, name + ".docx")
        doc.save(dst)
        print(f"[ok] {dst} ({os.path.getsize(dst)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
