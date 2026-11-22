"""Generate BRD + Epic + User Story dari facts.json memakai Gemini."""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_facts import call_gemini, extract_json  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("facts")
    p.add_argument("--prompt", default="prompts/artifacts@v1.md")
    p.add_argument("--out", default=".data/artifacts.json")
    p.add_argument("--model", default="gemini-3.6-flash")
    p.add_argument("--thinking", type=int, default=0)
    a = p.parse_args()

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY belum diset")

    template = open(a.prompt).read()
    idx = template.find("## PERAN")
    body = template[idx:] if idx >= 0 else template
    facts = json.load(open(a.facts))
    prompt = body.replace("{{FACTS}}", json.dumps(facts, ensure_ascii=False, indent=1))

    print(f"[info] prompt {len(prompt)} karakter | model {a.model}", flush=True)
    text, usage = call_gemini(a.model, prompt, key, temperature=0.3, thinking=a.thinking)
    print(f"[info] respons {len(text)} karakter | {usage.get('promptTokenCount')}→{usage.get('candidatesTokenCount')} token", flush=True)

    data = extract_json(text)
    if isinstance(data, list):
        data = data[0] if len(data) == 1 and isinstance(data[0], dict) else {"epics": data}
    if "brd" not in data and "epics" not in data:
        data = {"brd": data}
    with open(a.out, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[ok] {a.out} | epics={len(data.get('epics', []))} "
          f"stories={sum(len(e.get('stories', [])) for e in data.get('epics', []))}", flush=True)


if __name__ == "__main__":
    main()
