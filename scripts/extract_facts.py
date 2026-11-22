"""Ekstraksi fakta rapat dari transkrip memakai Gemini API.

Menghasilkan facts.json yang mengikuti schema/facts.schema.json.
Kunci API dibaca dari variabel lingkungan GEMINI_API_KEY.
"""

import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import platform_support  # noqa: E402,F401  (stdout UTF-8 + cache default)

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def call_gemini(model: str, prompt: str, key: str, temperature: float = 0.2,
                max_tokens: int = 32768, retries: int = 3, thinking: int = 0) -> tuple[str, dict]:
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
            **({"thinkingConfig": {"thinkingBudget": thinking}} if thinking >= 0 else {}),
        },
    }
    data = json.dumps(body).encode()
    last = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(
            API.format(model=model),
            data=data,
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                payload = json.load(r)
            cand = payload["candidates"][0]
            text = "".join(p.get("text", "") for p in cand["content"]["parts"])
            return text, payload.get("usageMetadata", {})
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300]
            if e.code == 429:
                raise RuntimeError(f"kuota/rate limit Gemini tercapai (429): {body}") from None
            last = f"HTTP {e.code}: {body}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        if attempt < retries:
            time.sleep(2 * attempt)
    raise RuntimeError(f"gagal memanggil Gemini: {last}")


def extract_json(text: str) -> dict:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    return json.loads(t)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("transcript")
    p.add_argument("--prompt", default="prompts/extract@v1.md")
    p.add_argument("--out", default=".data/facts.json")
    p.add_argument("--model", default="gemini-3.6-flash")
    p.add_argument("--thinking", type=int, default=0)
    p.add_argument("--project", default="Sistem HR internal")
    p.add_argument("--glossary", default="")
    p.add_argument("--participants", default="")
    p.add_argument("--date", default="")
    a = p.parse_args()

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY belum diset")

    template = open(a.prompt, encoding="utf-8").read()
    # Buang bagian meta di atas "## PERAN"
    idx = template.find("## PERAN")
    body = template[idx:] if idx >= 0 else template

    transcript = open(a.transcript, encoding="utf-8").read()
    prompt = (
        body.replace("{{PROJECT}}", a.project)
        .replace("{{GLOSSARY}}", a.glossary or "(tidak ada)")
        .replace("{{PARTICIPANTS}}", a.participants or "(tidak diketahui)")
        .replace("{{TRANSCRIPT}}", transcript)
    )

    print(f"[info] prompt {len(prompt)} karakter | model {a.model}", flush=True)
    t0 = time.time()
    text, usage = call_gemini(a.model, prompt, key, thinking=a.thinking)
    print(f"[info] respons {len(text)} karakter | {time.time()-t0:.1f}s | {usage}", flush=True)

    facts = extract_json(text)
    if isinstance(facts, list):
        facts = facts[0] if len(facts) == 1 and isinstance(facts[0], dict) else {"items": facts}
    if a.date and not facts.get("meeting", {}).get("date"):
        facts.setdefault("meeting", {})["date"] = a.date
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=2)
    print(f"[ok] {a.out}", flush=True)


if __name__ == "__main__":
    main()
