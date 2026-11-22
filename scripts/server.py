"""Server lokal untuk review hasil rapat (UI di folder ui/).

Jalankan:  .venv/bin/python scripts/server.py --port 8777
Hanya mendengarkan di 127.0.0.1 — tidak ada data yang keluar dari mesin.
"""

import argparse
import json
import os
import re
import sys
import time
import uuid
import base64
import shutil
import signal
import subprocess
import threading
import urllib.error
import urllib.request
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEETINGS = os.path.join(ROOT, ".data", "meetings")
UPLOADS = os.path.join(ROOT, ".data", "uploads")
JOBS = os.path.join(ROOT, ".data", "jobs")
UI = os.path.join(ROOT, "ui")
MAX_UPLOAD = 800 * 1024 * 1024
MAX_CONCURRENT = 1
RUNNING: dict = {}
QUEUE: list = []
JOB_LOCK = threading.Lock()


def make_job() -> tuple[str, str]:
    jid = time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    jobdir = os.path.join(JOBS, jid)
    os.makedirs(jobdir, exist_ok=True)
    with open(os.path.join(jobdir, "job.json"), "w") as f:
        json.dump({"state": "queued", "progress": 0, "step": "menunggu antrean", "log": []}, f)
    return jid, jobdir


def spawn_kwargs(log) -> dict:
    kw = dict(cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=os.environ.copy())
    if os.name == "nt":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    return kw


def pump() -> None:
    with JOB_LOCK:
        started = []
        while len(RUNNING) < MAX_CONCURRENT and QUEUE:
            jid, cmd = QUEUE.pop(0)
            jobdir = os.path.join(JOBS, jid)
            log = open(os.path.join(jobdir, "run.log"), "w")
            proc = subprocess.Popen(cmd, **spawn_kwargs(log))
            RUNNING[jid] = proc
            started.append(jid)
    for jid in started:
        print(f"[dikte] mulai job {jid}", flush=True)


def enqueue(jid: str, cmd: list) -> None:
    cfg.apply_env()
    with JOB_LOCK:
        QUEUE.append((jid, cmd))
        pos = len(QUEUE)
    print(f"[dikte] antre job {jid} (posisi {pos})", flush=True)
    pump()


def write_state(jid: str, state: str, step: str) -> None:
    path = os.path.join(JOBS, jid, "job.json")
    data = read_json(path, {}) or {}
    data.update(state=state, step=step, finished=time.time())
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def cancel_job(jid: str) -> bool:
    with JOB_LOCK:
        for i, (q, _cmd) in enumerate(QUEUE):
            if q == jid:
                QUEUE.pop(i)
                write_state(jid, "cancelled", "dibatalkan sebelum mulai")
                return True
        proc = RUNNING.get(jid)
        if proc is not None:
            RUNNING.pop(jid, None)
    if proc is not None:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                               capture_output=True)
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:  # noqa: BLE001
            proc.terminate()
        write_state(jid, "cancelled", "dibatalkan pengguna")
        pump()
        return True
    return False


def monitor_loop() -> None:
    while True:
        time.sleep(1.5)
        finished = []
        with JOB_LOCK:
            for jid, proc in list(RUNNING.items()):
                if proc.poll() is not None:
                    finished.append(jid)
            for jid in finished:
                RUNNING.pop(jid, None)
        if finished:
            pump()


def load_env() -> None:
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def safe_name(name: str) -> str:
    base = os.path.basename(name).replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9_.-]", "", base)[:120] or "rekaman"


def job_state(jobdir: str) -> dict:
    return read_json(os.path.join(jobdir, "job.json"), {"state": "unknown"}) or {"state": "unknown"}

import settings_store as cfg  # noqa: E402
from platform_support import venv_bin_dir  # noqa: E402

MIME = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".csv": "text/csv; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
}


def meeting_dirs() -> list[str]:
    if not os.path.isdir(MEETINGS):
        return []
    return sorted(
        (d for d in os.listdir(MEETINGS) if os.path.exists(os.path.join(MEETINGS, d, "meta.json"))),
        reverse=True,
    )


def read_json(path: str, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return default


class Handler(BaseHTTPRequestHandler):
    server_version = "Dikte62/0.5"
    TOKEN = ""

    def _authorized(self) -> bool:
        if not self.TOKEN:
            return True
        q = parse_qs(urlparse(self.path).query)
        if q.get("token", [""])[0] == self.TOKEN:
            return True
        return f"dikte_token={self.TOKEN}" in self.headers.get("Cookie", "")

    def _deny(self) -> None:
        body = ("<!doctype html><meta charset=utf-8><title>Dikte62</title>"
                "<body style='font:14px -apple-system;padding:40px;color:#101828'>"
                "<h3>Akses ditolak</h3><p>Buka URL lengkap dengan <code>?token=…</code> "
                "seperti yang tertulis di terminal server.</p>").encode()
        self.send_response(401)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # ringkas
        print(f"{self.address_string()} {fmt % args}", flush=True)

    # ---------- util ----------
    def send_json(self, obj, code: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return

    def send_file(self, path: str, download_name: str | None = None, ranged: bool = False) -> None:
        if not os.path.isfile(path):
            self.send_error(404, "File tidak ditemukan")
            return
        size = os.path.getsize(path)
        ext = os.path.splitext(path)[1].lower()
        ctype = MIME.get(ext, mimetypes.guess_type(path)[0] or "application/octet-stream")

        start, end = 0, size - 1
        code = 200
        rng = self.headers.get("Range")
        if ranged and rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                if m.group(2):
                    end = int(m.group(2))
                end = min(end, size - 1)
                code = 206

        length = end - start + 1
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        if not ranged:
            self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(length))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if download_name:
            self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            try:
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                return

    # ---------- routes ----------
    def do_GET(self) -> None:  # noqa: N802
        u = urlparse(self.path)

        if Handler.TOKEN and parse_qs(u.query).get("token", [""])[0] == Handler.TOKEN:
            self.send_response(302)
            self.send_header("Location", u.path)
            self.send_header("Set-Cookie",
                             f"dikte_token={Handler.TOKEN}; Path=/; HttpOnly; SameSite=Lax")
            self.end_headers()
            return

        if not self._authorized():
            self._deny()
            return

        path = u.path

        if path == "/api/settings":
            self.send_json(cfg.public_view())
            return

        if path == "/api/jobs":
            out = []
            if os.path.isdir(JOBS):
                for jid in sorted(os.listdir(JOBS), reverse=True):
                    st = job_state(os.path.join(JOBS, jid))
                    out.append({"id": jid, **st})
            self.send_json(out[:20])
            return

        m = re.match(r"^/api/job/([A-Za-z0-9_-]+)$", path)
        if m:
            jobdir = os.path.join(JOBS, m.group(1))
            if not os.path.isdir(jobdir):
                self.send_error(404)
                return
            self.send_json(job_state(jobdir))
            return

        if path == "/api/meetings":
            out = []
            for mid in meeting_dirs():
                meta_path = os.path.join(MEETINGS, mid, "meta.json")
                meta = read_json(meta_path, {}) or {}
                facts = read_json(os.path.join(MEETINGS, mid, "facts.json"), {}) or {}
                art = read_json(os.path.join(MEETINGS, mid, "artifacts.json"), {}) or {}
                appr = read_json(os.path.join(MEETINGS, mid, "approvals.json"), {}) or {}
                out.append({
                    "id": mid,
                    "title": meta.get("title", mid),
                    "date": meta.get("date", ""),
                    "duration_min": meta.get("duration_min", 0),
                    "counts": {
                        "decisions": len(facts.get("decisions", []) or []),
                        "requirements": len(facts.get("requirements", []) or []),
                        "actions": len(facts.get("action_items", []) or []),
                        "questions": len(facts.get("open_questions", []) or []),
                        "epics": len(art.get("epics", []) or []),
                        "stories": sum(len(e.get("stories", [])) for e in art.get("epics", []) or []),
                    },
                    "approved": appr,
                    "archived": bool(meta.get("archived")),
                    "created_at": float(meta.get("created_at") or os.path.getmtime(meta_path)),
                })
            self.send_json(out)
            return

        m = re.match(r"^/api/meeting/([A-Za-z0-9_.-]+)$", path)
        if m:
            mid = m.group(1)
            base = os.path.join(MEETINGS, mid)
            if not os.path.isdir(base):
                self.send_error(404)
                return
            meta = read_json(os.path.join(base, "meta.json"), {}) or {}
            self.send_json({
                "meta": meta,
                "facts": read_json(os.path.join(base, "facts.json"), {}) or {},
                "artifacts": read_json(os.path.join(base, "artifacts.json"), {}) or {},
                "transcript": read_json(os.path.join(base, "transcript.json"), {}) or {},
                "approvals": read_json(os.path.join(base, "approvals.json"), {}) or {},
                "speaker_names": read_json(os.path.join(base, "speakers.json"), {}) or {},
                "has_audio": bool(meta.get("audio")) and os.path.isfile(os.path.join(ROOT, meta.get("audio", ""))),
            })
            return

        m = re.match(r"^/media/([A-Za-z0-9_.-]+)$", path)
        if m:
            meta = read_json(os.path.join(MEETINGS, m.group(1), "meta.json"), {}) or {}
            audio = meta.get("audio")
            if not audio:
                self.send_error(404)
                return
            self.send_file(os.path.join(ROOT, audio), ranged=True)
            return

        m = re.match(r"^/doc/([A-Za-z0-9_.-]+)/([a-z_]+)$", path)
        if m:
            mid, key = m.group(1), m.group(2)
            meta = read_json(os.path.join(MEETINGS, mid, "meta.json"), {}) or {}
            name = (meta.get("docs") or {}).get(key)
            if not name:
                self.send_error(404)
                return
            self.send_file(os.path.join(MEETINGS, mid, name), download_name=name)
            return

        # static
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        if ".." in rel:
            self.send_error(400)
            return
        full = os.path.join(UI, rel)
        if os.path.isfile(full):
            self.send_file(full)
        else:
            self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if not self._authorized():
            self._deny()
            return
        u = urlparse(self.path)

        if u.path == "/api/upload":
            name = safe_name(unquote(self.headers.get("X-Filename", "rekaman")))
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0 or length > MAX_UPLOAD:
                self.send_error(413, "Ukuran file tidak didukung")
                return
            os.makedirs(UPLOADS, exist_ok=True)
            dst = os.path.join(UPLOADS, f"{time.strftime('%Y%m%d_%H%M%S')}_{name}")
            with open(dst, "wb") as f:
                remaining = length
                while remaining > 0:
                    chunk = self.rfile.read(min(1 << 20, remaining))
                    if not chunk:
                        break
                    f.write(chunk)
                    remaining -= len(chunk)
            self.send_json({"path": os.path.relpath(dst, ROOT), "name": name})
            return

        if u.path == "/api/regenerate":
            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except Exception:  # noqa: BLE001
                self.send_error(400)
                return
            mid = payload.get("id", "")
            if not re.match(r"^[A-Za-z0-9_.-]+$", mid) or not os.path.isdir(os.path.join(MEETINGS, mid)):
                self.send_error(400, "Rapat tidak ditemukan")
                return
            jid, jobdir = make_job()
            enqueue(jid, [sys.executable, "-u", "scripts/regenerate_docs.py",
                          "--id", mid, "--jobdir", jobdir])
            self.send_json({"job": jid})
            return

        if u.path == "/api/process":
            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except Exception:  # noqa: BLE001
                self.send_error(400)
                return
            audio = payload.get("path", "")
            full = os.path.abspath(os.path.join(ROOT, audio))
            if not full.startswith(os.path.join(ROOT, ".data", "uploads")) or not os.path.isfile(full):
                self.send_error(400, "Path audio tidak valid")
                return
            jid, jobdir = make_job()
            enqueue(jid, [sys.executable, "-u", "scripts/run_pipeline.py",
                          "--audio", full, "--jobdir", jobdir])
            self.send_json({"job": jid})
            return
        if u.path == "/api/archive":
            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except Exception:  # noqa: BLE001
                self.send_error(400)
                return
            mid = payload.get("id", "")
            if not re.match(r"^[A-Za-z0-9_.-]+$", mid):
                self.send_error(400)
                return
            meta_path = os.path.join(MEETINGS, mid, "meta.json")
            if not os.path.isfile(meta_path):
                self.send_error(404)
                return
            meta = read_json(meta_path, {}) or {}
            meta["archived"] = bool(payload.get("archived"))
            if meta["archived"]:
                meta["archived_at"] = int(time.time())
            with open(meta_path, "w") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            self.send_json({"ok": True, "archived": meta["archived"]})
            return

        if u.path == "/api/delete":
            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except Exception:  # noqa: BLE001
                self.send_error(400)
                return
            mid = payload.get("id", "")
            base = os.path.abspath(os.path.join(MEETINGS, mid))
            if not re.match(r"^[A-Za-z0-9_.-]+$", mid) or not base.startswith(MEETINGS + os.sep):
                self.send_error(400)
                return
            if not os.path.isdir(base):
                self.send_error(404)
                return
            meta = read_json(os.path.join(base, "meta.json"), {}) or {}
            audio = meta.get("audio", "")
            shutil.rmtree(base)
            removed_audio = False
            if audio:
                full = os.path.abspath(os.path.join(ROOT, audio))
                uploads = os.path.join(ROOT, ".data", "uploads") + os.sep
                if full.startswith(uploads) and os.path.isfile(full):
                    still_used = False
                    for other in os.listdir(MEETINGS):
                        om = read_json(os.path.join(MEETINGS, other, "meta.json"), {}) or {}
                        if om.get("audio") == audio:
                            still_used = True
                            break
                    if not still_used:
                        os.remove(full)
                        removed_audio = True
            self.send_json({"ok": True, "audio_removed": removed_audio})
            return

        if u.path == "/api/settings":
            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except Exception:  # noqa: BLE001
                self.send_error(400)
                return
            clear_keys = payload.pop("clear_keys", []) or []
            if clear_keys:
                cfg.clear(*[k for k in clear_keys if k in cfg.SECRETS])
            cfg.save(payload)
            cfg.apply_env()
            self.send_json({"ok": True, "settings": cfg.public_view()})
            return

        if u.path == "/api/settings/test/gemini":
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            data = cfg.load()
            key = payload.get("gemini_api_key") or data["gemini_api_key"]
            model = payload.get("gemini_model") or data["gemini_model"]
            if not key:
                self.send_json({"ok": False, "message": "API key belum diisi"})
                return
            body = {"contents": [{"parts": [{"text": "Balas JSON {\"ok\":true}"}]}],
                    "generationConfig": {"temperature": 0, "maxOutputTokens": 32,
                                         "responseMimeType": "application/json",
                                         "thinkingConfig": {"thinkingBudget": 0}}}
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json", "x-goog-api-key": key})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    d = json.load(r)
                text = "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
                self.send_json({"ok": True, "message": f"{model} menjawab: {text.strip()[:60]}"})
            except urllib.error.HTTPError as e:
                self.send_json({"ok": False, "message": f"HTTP {e.code}: {e.read().decode()[:200]}"})
            except Exception as e:  # noqa: BLE001
                self.send_json({"ok": False, "message": repr(e)[:200]})
            return

        if u.path == "/api/settings/test/jira":
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            data = cfg.load()
            base = payload.get("jira_base_url") or data["jira_base_url"]
            email = payload.get("jira_email") or data["jira_email"]
            token = payload.get("jira_api_token") or data["jira_api_token"]
            if not (base and email and token):
                self.send_json({"ok": False, "message": "URL, email, dan token harus lengkap"})
                return
            auth = base64.b64encode(f"{email}:{token}".encode()).decode()
            req = urllib.request.Request(base.rstrip("/") + "/rest/api/3/myself",
                                         headers={"Authorization": f"Basic {auth}",
                                                  "Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    d = json.load(r)
                who = d.get("displayName") or d.get("emailAddress") or "ok"
                self.send_json({"ok": True, "message": f"Terhubung sebagai {who}"})
            except urllib.error.HTTPError as e:
                self.send_json({"ok": False, "message": f"HTTP {e.code}: {e.read().decode()[:200]}"})
            except Exception as e:  # noqa: BLE001
                self.send_json({"ok": False, "message": repr(e)[:200]})
            return

        if u.path == "/api/jira":
            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except Exception:  # noqa: BLE001
                self.send_error(400)
                return
            mid = payload.get("id", "")
            project = str(payload.get("project", "")).strip().upper()
            dry = bool(payload.get("dry_run"))
            if not re.match(r"^[A-Za-z0-9_.-]+$", mid) or not os.path.isdir(os.path.join(MEETINGS, mid)):
                self.send_error(400, "Rapat tidak ditemukan")
                return
            if not re.match(r"^[A-Z0-9_]{2,20}$", project):
                self.send_error(400, "Kode proyek Jira tidak valid")
                return
            artifacts = os.path.join(MEETINGS, mid, "artifacts.json")
            cmd = [sys.executable, "-u", "scripts/jira_push.py", "--artifacts", artifacts,
                   "--project", project] + (["--dry-run"] if dry else [])
            try:
                cfg.apply_env()
                res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=180,
                                     env=os.environ.copy())
                out = (res.stdout or "") + (res.stderr or "")
                result = read_json(os.path.join(ROOT, ".data", "jira_result.json"), []) if res.returncode == 0 else []
                self.send_json({"ok": res.returncode == 0, "output": out[-4000:], "result": result[-40:]})
            except subprocess.TimeoutExpired:
                self.send_json({"ok": False, "output": "timeout 180s"}, 504)
            return

        if u.path == "/api/cancel":
            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except Exception:  # noqa: BLE001
                self.send_error(400)
                return
            jid = payload.get("id", "")
            if not re.match(r"^[A-Za-z0-9_-]+$", jid):
                self.send_error(400)
                return
            ok = cancel_job(jid)
            self.send_json({"ok": ok})
            return

        if u.path == "/api/speakers":
            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except Exception:  # noqa: BLE001
                self.send_error(400)
                return
            mid = payload.get("id", "")
            names = payload.get("names", {})
            if not re.match(r"^[A-Za-z0-9_.-]+$", mid) or not isinstance(names, dict):
                self.send_error(400)
                return
            path = os.path.join(MEETINGS, mid, "speakers.json")
            current = read_json(path, {}) or {}
            for k, v in names.items():
                if re.match(r"^S[0-9]+$", str(k)):
                    current[k] = str(v)[:60]
            with open(path, "w") as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
            self.send_json({"ok": True, "speaker_names": current})
            return

        if u.path == "/api/approve":
            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except Exception:  # noqa: BLE001
                self.send_error(400)
                return
            mid = payload.get("id", "")
            key = payload.get("key", "")
            if not re.match(r"^[A-Za-z0-9_.-]+$", mid) or not re.match(r"^[a-z_]+$", key):
                self.send_error(400)
                return
            path = os.path.join(MEETINGS, mid, "approvals.json")
            data = read_json(path, {}) or {}
            data[key] = bool(payload.get("approved"))
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            self.send_json({"ok": True, "approvals": data})
            return
        self.send_error(404)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8777)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--token", default=os.environ.get("DIKTE_TOKEN", ""),
                   help="wajibkan token akses (untuk mode web/LAN)")
    a = p.parse_args()
    load_env()
    if cfg.migrate_from_env():
        print("[dikte] kredensial Gemini dipindah dari .env ke Pengaturan UI", flush=True)
    cfg.apply_env()
    os.environ["PATH"] = venv_bin_dir(ROOT) + os.pathsep + os.environ.get("PATH", "")

    threading.Thread(target=monitor_loop, daemon=True).start()
    Handler.TOKEN = a.token
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    suffix = f"?token={a.token}" if a.token else ""
    print(f"[dikte] review UI: http://{a.host}:{a.port}/{suffix}", flush=True)
    print(f"[dikte] rapat terdeteksi: {len(meeting_dirs())}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
