"""Kirim Epic & User Story hasil rapat ke Jira lewat REST API v3.

Kredensial dibaca dari `.data/config.json` (diatur lewat Pengaturan di UI) atau dari
environment variable untuk pemakaian CLI: JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN,
JIRA_PROJECT_KEY, JIRA_EPIC_FIELD, JIRA_SET_PRIORITY.

Pemakaian:
  python scripts/jira_push.py --artifacts .data/artifacts.final.json --project ABC
  python scripts/jira_push.py --artifacts ... --dry-run
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

PRIORITY = {"must": "Highest", "should": "High", "could": "Medium", "wont": "Lowest"}


def adf(blocks: list) -> dict:
    content = []
    for b in blocks:
        if isinstance(b, str):
            content.append({"type": "paragraph", "content": [{"type": "text", "text": b}]})
        elif isinstance(b, tuple) and b[0] == "bullets":
            content.append({
                "type": "bulletList",
                "content": [
                    {"type": "listItem", "content": [{"type": "paragraph",
                     "content": [{"type": "text", "text": str(x)}]}]}
                    for x in b[1]
                ],
            })
    return {"type": "doc", "version": 1, "content": content}


def build_issues(art: dict, project: str, epic_field: str = "", set_priority: bool = False) -> list[dict]:
    issues = []
    for ep in art.get("epics", []):
        desc = [ep.get("goal", ""), f"Nilai bisnis: {ep.get('value','')}",
                f"Metrik sukses: {ep.get('success_metric','')}"]
        if ep.get("refs"):
            desc.append("Referensi rapat: " + ", ".join(ep["refs"]))
        payload = {
            "fields": {
                "project": {"key": project},
                "summary": ep.get("title", "")[:250],
                "description": adf([d for d in desc if d]),
                "issuetype": {"name": "Epic"},
            }
        }
        issues.append({"kind": "epic", "ref": ep.get("id"), "payload": payload})

        for st in ep.get("stories", []):
            ac = [f"Given {a.get('given','')} when {a.get('when','')} then {a.get('then','')}"
                  for a in st.get("acceptance", [])]
            body = [f"Sebagai {st.get('as_a','')}, saya ingin {st.get('i_want','')}, agar {st.get('so_that','')}."]
            if ac:
                body.append(("bullets", ["Acceptance criteria:"] + ac))
            if st.get("refs"):
                body.append("Referensi rapat: " + ", ".join(st["refs"]))
            summary = (st.get("i_want") or "User story")[:250]
            fields = {
                "project": {"key": project},
                "summary": summary,
                "description": adf(body),
                "issuetype": {"name": "Story"},
            }
            if set_priority:
                fields["priority"] = {"name": PRIORITY.get(st.get("priority", "should"), "Medium")}
            if epic_field:
                fields[epic_field] = {"key": f"__EPIC__:{ep.get('id')}"}
            else:
                fields["parent"] = {"key": f"__EPIC__:{ep.get('id')}"}
            issues.append({"kind": "story", "ref": st.get("id"), "epic": ep.get("id"),
                           "payload": {"fields": fields}})
    return issues


def post_issue(base: str, auth: str, payload: dict) -> dict:
    req = urllib.request.Request(
        base.rstrip("/") + "/rest/api/3/issue",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}",
                 "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main() -> None:
    try:
        import settings_store as cfg
        cfg.apply_env()
    except Exception:  # noqa: BLE001
        pass
    p = argparse.ArgumentParser()
    p.add_argument("--artifacts", required=True)
    p.add_argument("--project", default=os.environ.get("JIRA_PROJECT_KEY", ""))
    p.add_argument("--base", default=os.environ.get("JIRA_BASE_URL", ""))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--out", default=".data/jira_result.json")
    a = p.parse_args()

    email = os.environ.get("JIRA_EMAIL", "")
    token = os.environ.get("JIRA_API_TOKEN", "")
    epic_field = os.environ.get("JIRA_EPIC_FIELD", "")
    set_priority = os.environ.get("JIRA_SET_PRIORITY", "0") == "1"

    if not a.project:
        sys.exit("project key kosong (--project atau JIRA_PROJECT_KEY)")
    if not a.dry_run and not (a.base and email and token):
        sys.exit("JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN belum lengkap")

    art = json.load(open(a.artifacts))
    issues = build_issues(art, a.project, epic_field, set_priority)
    print(f"[info] {len(issues)} issue akan dikirim ke {a.project}", flush=True)

    if a.dry_run:
        for it in issues:
            print(f"  [{it['kind']}] {it['ref']}: {it['payload']['fields']['summary'][:70]}", flush=True)
        return

    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    key_by_ref = {}
    result = []
    for it in issues:
        payload = json.loads(json.dumps(it["payload"]))
        fields = payload["fields"]
        skip = False
        for f in ("parent", epic_field):
            if f and f in fields and isinstance(fields[f], dict):
                ref = str(fields[f].get("key", "")).replace("__EPIC__:", "")
                got = key_by_ref.get(ref)
                if got:
                    fields[f] = {"key": got}
                else:
                    skip = True
        if skip:
            result.append({"ref": it["ref"], "kind": it["kind"], "error": "epic induk gagal dibuat"})
            print(f"  ! {it['ref']} dilewati (epic induk gagal)", flush=True)
            continue
        try:
            res = post_issue(a.base, auth, payload)
            key_by_ref[it["ref"]] = res.get("key", "")
            result.append({"ref": it["ref"], "kind": it["kind"], "key": res.get("key")})
            print(f"  ✓ {it['kind']} {it['ref']} → {res.get('key')}", flush=True)
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:400]
            result.append({"ref": it["ref"], "kind": it["kind"], "error": f"{e.code}: {body}"})
            print(f"  × {it['kind']} {it['ref']} gagal {e.code}: {body}", flush=True)
        except Exception as e:  # noqa: BLE001
            result.append({"ref": it["ref"], "kind": it["kind"], "error": repr(e)})
            print(f"  × {it['ref']} error {e}", flush=True)

    with open(a.out, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    ok = sum(1 for r in result if r.get("key"))
    print(f"[selesai] {ok}/{len(issues)} issue dibuat → {a.out}", flush=True)


if __name__ == "__main__":
    main()
