"""Penyimpanan pengaturan + kredensial Dikte (bukan .env).

Lokasi: .data/config.json (permission 600, sudah tercakup .gitignore karena .data/).
Secret tidak pernah dikirim balik ke browser — hanya status "terisi" dan 4 karakter terakhir.
"""

import json
import os
import stat

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG = os.path.join(ROOT, ".data", "config.json")

DEFAULTS = {
    "gemini_api_key": "",
    "gemini_model": "gemini-3.6-flash",
    "jira_base_url": "",
    "jira_email": "",
    "jira_api_token": "",
    "jira_project_key": "",
    "jira_epic_field": "",
    "jira_set_priority": False,
}

SECRETS = ("gemini_api_key", "jira_api_token")

ENV_MAP = {
    "gemini_api_key": "GEMINI_API_KEY",
    "gemini_model": "GEMINI_MODEL",
    "jira_base_url": "JIRA_BASE_URL",
    "jira_email": "JIRA_EMAIL",
    "jira_api_token": "JIRA_API_TOKEN",
    "jira_project_key": "JIRA_PROJECT_KEY",
    "jira_epic_field": "JIRA_EPIC_FIELD",
}


def load() -> dict:
    data = dict(DEFAULTS)
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG) as f:
                data.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
        except Exception:  # noqa: BLE001
            pass
    return data


def save(patch: dict) -> dict:
    data = load()
    for k, v in patch.items():
        if k not in DEFAULTS:
            continue
        if k in SECRETS and (v is None or v == ""):
            continue  # string kosong = jangan ubah
        if k == "jira_set_priority":
            v = bool(v)
        if k == "jira_project_key" and v:
            v = str(v).upper()
        data[k] = v
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    tmp = CONFIG + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG)
    os.chmod(CONFIG, stat.S_IRUSR | stat.S_IWUSR)
    return data


def clear(*keys: str) -> dict:
    data = load()
    for k in keys:
        if k in DEFAULTS:
            data[k] = "" if k not in ("jira_set_priority",) else False
    with open(CONFIG, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.chmod(CONFIG, stat.S_IRUSR | stat.S_IWUSR)
    return data


def apply_env() -> dict:
    """Terapkan kredensial dari config ke environment proses (config menang atas .env)."""
    data = load()
    for key, env in ENV_MAP.items():
        if data.get(key):
            os.environ[env] = str(data[key])
        else:
            os.environ.pop(env, None)
    os.environ["JIRA_SET_PRIORITY"] = "1" if data.get("jira_set_priority") else "0"
    return data


def public_view() -> dict:
    data = load()
    view = {}
    for k, v in data.items():
        if k in SECRETS:
            view[k] = {"configured": bool(v), "tail": (str(v)[-4:] if v else "")}
        else:
            view[k] = v
    return view


def migrate_from_env() -> bool:
    """Pindahkan GEMINI_API_KEY dari .env ke config.json sekali, lalu rapikan .env."""
    env_path = os.path.join(ROOT, ".env")
    if not os.path.exists(env_path):
        return False
    lines = open(env_path).read().splitlines()
    found = None
    keep = []
    for line in lines:
        s = line.strip()
        if s.startswith("GEMINI_API_KEY="):
            found = s.split("=", 1)[1].strip()
        else:
            keep.append(line)
    if not found:
        return False
    data = load()
    if not data.get("gemini_api_key"):
        save({"gemini_api_key": found})
    keep.append("# Kredensial kini diatur dari UI (Pengaturan) → .data/config.json")
    with open(env_path + ".bak", "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(env_path, "w") as f:
        f.write("\n".join(keep) + "\n")
    os.chmod(env_path, stat.S_IRUSR | stat.S_IWUSR)
    return True
