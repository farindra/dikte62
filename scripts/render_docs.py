"""Render facts.json + artifacts.json menjadi dokumen Markdown dan CSV Jira."""

import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import platform_support  # noqa: E402,F401  (stdout UTF-8 + cache default)

import argparse
import csv
import json
import os

PRIO = {"must": "Highest", "should": "High", "could": "Medium", "wont": "Lowest"}


def md_table(headers, rows) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |")
    return "\n".join(out)


def render_brd(brd: dict, facts: dict) -> str:
    L = [f"# BRD — {brd.get('title', 'Tanpa Judul')}", "",
         f"*Sumber: transkrip rapat {facts['meeting'].get('date', '')} · "
         f"{facts['meeting'].get('duration_min', 0)} menit*", ""]
    L += ["## 1. Latar belakang", "", brd.get("background", "-"), ""]
    L += ["## 2. Tujuan", ""] + [f"- {x}" for x in brd.get("objectives", [])] + [""]
    L += ["## 3. Metrik sukses", ""] + [f"- {x}" for x in brd.get("success_metrics", [])] + [""]
    L += ["## 4. Ruang lingkup", "", "**Termasuk:**", ""] + [f"- {x}" for x in brd.get("in_scope", [])] + [""]
    L += ["**Tidak termasuk:**", ""] + [f"- {x}" for x in brd.get("out_of_scope", [])] + [""]
    L += ["## 5. Stakeholder", ""]
    L += [md_table(["Peran", "Kepentingan"], [[s.get("role", ""), s.get("interest", "")] for s in brd.get("stakeholders", [])]), ""]
    L += ["## 6. Kebutuhan bisnis", "",
          md_table(["ID", "Kebutuhan", "Prioritas", "Sumber"],
                   [[r.get("id"), r.get("text"), r.get("priority"), ", ".join(r.get("refs", []))]
                    for r in brd.get("business_requirements", [])]), ""]
    L += ["## 7. Asumsi", ""] + [f"- {x}" for x in brd.get("assumptions", [])] + [""]
    L += ["## 8. Risiko", "",
          md_table(["Risiko", "Dampak", "Mitigasi"],
                   [[r.get("risk"), r.get("impact"), r.get("mitigation")] for r in brd.get("risks", [])]), ""]
    L += ["## 9. Ketergantungan", ""] + [f"- {x}" for x in brd.get("dependencies", [])] + [""]
    L += ["## 10. Pertanyaan terbuka", ""]
    qs = {q["id"]: q for q in facts.get("open_questions", [])}
    for qid in brd.get("open_questions", []):
        q = qs.get(qid)
        L.append(f"- **{qid}** — {q['question'] if q else '(tidak ditemukan)'}")
    L.append("")
    L += ["## 11. Lampiran — keputusan rapat", "",
          md_table(["ID", "Keputusan", "Bukti"],
                   [[d.get("id"), d.get("text"),
                     "; ".join(f"{e['t']} \"{e['quote']}\"" for e in d.get("evidence", [])[:1])]
                    for d in facts.get("decisions", [])]), ""]
    return "\n".join(L)


def render_stories(art: dict) -> str:
    L = ["# Epic & User Story", ""]
    for ep in art.get("epics", []):
        L += [f"## {ep.get('id')} — {ep.get('title')}", "",
              f"**Tujuan:** {ep.get('goal', '-')}", "",
              f"**Nilai bisnis:** {ep.get('value', '-')}", "",
              f"**Metrik sukses:** {ep.get('success_metric', '-')}", "",
              f"**Referensi fakta:** {', '.join(ep.get('refs', []))}", ""]
        if ep.get("in_scope"):
            L += ["**Termasuk:** " + "; ".join(ep["in_scope"]), ""]
        if ep.get("out_of_scope"):
            L += ["**Tidak termasuk:** " + "; ".join(ep["out_of_scope"]), ""]
        for st in ep.get("stories", []):
            L += [f"### {st.get('id')} — {st.get('i_want', '')[:70]}", "",
                  f"**Sebagai** {st.get('as_a', '-')}, **saya ingin** {st.get('i_want', '-')}, "
                  f"**agar** {st.get('so_that', '-')}.", "",
                  f"*Prioritas:* {st.get('priority', '-')} · *Ref:* {', '.join(st.get('refs', []))}", "",
                  "**Acceptance criteria:**", ""]
            for ac in st.get("acceptance", []):
                L += [f"- **Given** {ac.get('given', '')} **when** {ac.get('when', '')} "
                      f"**then** {ac.get('then', '')}"]
            L.append("")
    return "\n".join(L)


def render_summary(facts: dict) -> str:
    L = [f"# Ringkasan Rapat — {facts['meeting'].get('date', '')}", "",
         f"*Durasi {facts['meeting'].get('duration_min', 0)} menit · "
         f"Topik: {', '.join(facts['meeting'].get('topics', []))}*", "", "## TL;DR", ""]
    L += [f"- {x}" for x in facts["summary"].get("tldr", [])]
    L += ["", "## Ringkasan", "", facts["summary"].get("narrative", ""), ""]
    L += ["## Keputusan", ""]
    for d in facts.get("decisions", []):
        ev = d.get("evidence", [{}])[0]
        L.append(f"- **{d['id']}** {d['text']}  \n  ↳ bukti {ev.get('t','')} \"{ev.get('quote','')}\"")
    L += ["", "## Action item", ""]
    for a in facts.get("action_items", []):
        own = a.get("owner", "?")
        tag = "" if a.get("owner_confidence") == "explicit" else " _(terduga, perlu konfirmasi)_"
        L.append(f"- **{a['id']}** {a['task']} — owner: {own}{tag}")
    L += ["", "## Pertanyaan terbuka", ""]
    for q in facts.get("open_questions", []):
        L.append(f"- **{q['id']}** {q['question']}")
    L.append("")
    return "\n".join(L)


def write_jira(art: dict, facts: dict, path: str) -> int:
    n = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Issue Type", "Summary", "Description", "Priority", "Epic Name", "Labels", "Refs"])
        for ep in art.get("epics", []):
            desc = f"{ep.get('goal', '')}\n\nNilai: {ep.get('value', '')}\nMetrik: {ep.get('success_metric', '')}"
            w.writerow(["Epic", ep.get("title", ""), desc, "High", ep.get("title", ""),
                        "meeting-generated", ",".join(ep.get("refs", []))])
            n += 1
            for st in ep.get("stories", []):
                ac = "\n".join(
                    f"- Given {a.get('given','')} when {a.get('when','')} then {a.get('then','')}"
                    for a in st.get("acceptance", []))
                desc = (f"Sebagai {st.get('as_a','')}, saya ingin {st.get('i_want','')}, "
                        f"agar {st.get('so_that','')}.\n\nAcceptance criteria:\n{ac}")
                w.writerow(["Story", st.get("i_want", "")[:120], desc,
                            PRIO.get(st.get("priority", "should"), "High"),
                            ep.get("title", ""), "meeting-generated", ",".join(st.get("refs", []))])
                n += 1
    return n


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("facts")
    p.add_argument("artifacts")
    p.add_argument("--outdir", default="docs/generated")
    a = p.parse_args()

    facts = json.load(open(a.facts, encoding="utf-8"))
    art = json.load(open(a.artifacts, encoding="utf-8"))
    os.makedirs(a.outdir, exist_ok=True)

    files = {
        "RINGKASAN.md": render_summary(facts),
        "BRD.md": render_brd(art.get("brd", {}), facts),
        "EPIC-STORY.md": render_stories(art),
    }
    for name, content in files.items():
        with open(os.path.join(a.outdir, name), "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[ok] {a.outdir}/{name} ({len(content)} karakter)")

    n = write_jira(art, facts, os.path.join(a.outdir, "jira_import.csv"))
    print(f"[ok] {a.outdir}/jira_import.csv ({n} baris issue)")


if __name__ == "__main__":
    main()
