#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sonar Local: panel para escanear tus proyectos en tu SonarQube local (Docker) con un clic.

Uso:
    python3 sonar_dashboard.py            # abre http://127.0.0.1:8787
    python3 sonar_dashboard.py --no-browser

Sin dependencias: solo Python 3.8+ (viene con macOS / Xcode Command Line Tools).
La primera vez crea projects.json detectando las carpetas de tu workspace.
"""
from __future__ import annotations

import base64
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

HOME = Path.home()
APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "projects.json"
STATE_FILE = APP_DIR / ".scan_state.json"
HOST = "127.0.0.1"
PORT = int(os.environ.get("SONAR_DASH_PORT", "8787"))

DEFAULT_CONFIG = {
    "workspace": "/Users/claud/work/creditos",
    "sonar_url": "http://localhost:9000",
    "token_file": "~/.sonar/token",
    "java_home": "",          # vacío = autodetectar en ~/.sonar/cache
    "sonar_scanner_bin": "",  # vacío = autodetectar ~/tools/sonar-scanner-*/bin
    "js_exclusions": "**/node_modules/**,**/__test__/**,**/.next/**,**/public/**,**/*.test.*,**/*.spec.*",
    "js_node_maxspace": 4096,
    "projects": [],
}

NAME_PREFIXES = ["bsol-business-api-", "bsol-business-", "bsol-back-", "bsol-bff-", "bsol-"]
LAYER_ORDER = ["Frontend", "Backend BFF", "Backend Business", "Backend", "Otro"]
STEP_LABELS = {"dotnet": ["Preparar", "Compilar", "Publicar"], "js": ["Analizar"]}
METRICS_WANTED = [
    "alert_status", "bugs", "vulnerabilities", "code_smells", "security_hotspots", "coverage",
    "software_quality_reliability_issues", "software_quality_security_issues",
    "software_quality_maintainability_issues",
]

CFG_LOCK = threading.Lock()
STATE_LOCK = threading.Lock()


# --------------------------------------------------------------------------- config

def expand(p):
    return Path(os.path.expanduser(str(p))) if p else None


def load_config():
    with CFG_LOCK:
        if not CONFIG_FILE.exists():
            cfg = json.loads(json.dumps(DEFAULT_CONFIG))
            _write_json(CONFIG_FILE, cfg)
            return cfg
        with open(CONFIG_FILE, encoding="utf-8") as f:
            cfg = json.load(f)
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg


def save_config(cfg):
    with CFG_LOCK:
        _write_json(CONFIG_FILE, cfg)


def _write_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def load_state():
    with STATE_LOCK:
        if STATE_FILE.exists():
            try:
                return json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}


def record_state(pid, data):
    with STATE_LOCK:
        st = {}
        if STATE_FILE.exists():
            try:
                st = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                st = {}
        st[pid] = data
        _write_json(STATE_FILE, st)


# ------------------------------------------------------------------------ discovery

def pretty_name(folder):
    n = folder
    for pre in NAME_PREFIXES:
        if n.startswith(pre):
            n = n[len(pre):]
            break
    parts = re.split(r"[-_.\s]+", n)
    return "".join(p[:1].upper() + p[1:] for p in parts if p) or folder


def guess_layer(folder, ptype):
    f = folder.lower()
    if "bff" in f:
        return "Backend BFF"
    if "business" in f:
        return "Backend Business"
    if ptype == "js" or "web-client" in f or "front" in f:
        return "Frontend"
    return "Backend"


def detect(path):
    slns = sorted(path.glob("*.sln")) + sorted(path.glob("*.slnx"))
    if slns:
        return "dotnet", slns[0].name
    if any(path.glob("*.csproj")):
        return "dotnet", None
    if (path / "package.json").exists():
        return "js", None
    return None, None


def discover(cfg, existing):
    ws = expand(cfg["workspace"])
    known = {p["folder"] for p in existing}
    found = []
    if not ws or not ws.is_dir():
        return found
    for d in sorted(ws.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name in known:
            continue
        ptype, sln = detect(d)
        if not ptype:
            continue
        proj = {
            "name": pretty_name(d.name),
            "layer": guess_layer(d.name, ptype),
            "folder": d.name,
            "type": ptype,
            "key": d.name,
        }
        if ptype == "dotnet":
            proj["solution"] = sln
        else:
            proj["sources"] = "src" if (d / "src").is_dir() else "."
        found.append(proj)
    return found


def find_project(cfg, pid):
    return next((p for p in cfg["projects"] if p["folder"] == pid), None)


# --------------------------------------------------------------------------- tools

def read_token(cfg):
    tf = expand(cfg.get("token_file"))
    if tf and tf.is_file():
        t = tf.read_text(encoding="utf-8").strip()
        if t:
            return t
    return os.environ.get("SONAR_TOKEN", "").strip()


def find_java_home(cfg):
    jh = expand(cfg.get("java_home"))
    if jh and (jh / "bin" / "java").exists():
        return jh
    for pat in (HOME / ".sonar/cache/*/*_extracted/*/Contents/Home", HOME / ".sonar/cache/*/*_extracted/*"):
        for c in sorted(glob.glob(str(pat)), reverse=True):
            if (Path(c) / "bin" / "java").exists():
                return Path(c)
    env = os.environ.get("JAVA_HOME")
    if env and (Path(env) / "bin" / "java").exists():
        return Path(env)
    return None


def find_scanner_bin(cfg):
    b = expand(cfg.get("sonar_scanner_bin"))
    if b and (b / "sonar-scanner").exists():
        return b
    for c in sorted(glob.glob(str(HOME / "tools/sonar-scanner-*/bin")), reverse=True):
        if (Path(c) / "sonar-scanner").exists():
            return Path(c)
    w = shutil.which("sonar-scanner")
    return Path(w).parent if w else None


def make_env(front=()):
    env = os.environ.copy()
    extra = [HOME / ".dotnet/tools", Path("/usr/local/share/dotnet"), Path("/opt/homebrew/bin"), Path("/usr/local/bin")]
    parts = [str(p) for p in front] + [str(p) for p in extra] + env.get("PATH", "").split(os.pathsep)
    seen, clean = set(), []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            clean.append(p)
    env["PATH"] = os.pathsep.join(clean)
    return env


def tool_status(cfg):
    path = make_env()["PATH"]
    jh = find_java_home(cfg)
    sb = find_scanner_bin(cfg)
    ws = expand(cfg["workspace"])
    dn = shutil.which("dotnet", path=path)
    dss = shutil.which("dotnet-sonarscanner", path=path)
    return [
        {"name": "Workspace", "ok": bool(ws and ws.is_dir()), "detail": str(ws)},
        {"name": "Token", "ok": bool(read_token(cfg)), "detail": str(expand(cfg.get("token_file")))},
        {"name": "Java", "ok": bool(jh), "detail": str(jh) if jh else "No encontrado: define java_home en projects.json"},
        {"name": "dotnet", "ok": bool(dn), "detail": dn or "No encontrado"},
        {"name": "dotnet-sonarscanner", "ok": bool(dss), "detail": dss or "dotnet tool install --global dotnet-sonarscanner"},
        {"name": "sonar-scanner", "ok": bool(sb), "detail": str(sb) if sb else "No encontrado en ~/tools/sonar-scanner-*/bin"},
    ]


# ---------------------------------------------------------------------------- scans

class ScanError(Exception):
    pass


def build_plan(p, cfg):
    ws = expand(cfg["workspace"])
    path = ws / p["folder"]
    if not path.is_dir():
        raise ScanError(f"No existe la carpeta {path}")
    token = read_token(cfg)
    if not token:
        raise ScanError(f"No hay token: crea {cfg.get('token_file')} o exporta SONAR_TOKEN")
    jh = find_java_home(cfg)
    if not jh:
        raise ScanError("No encontré Java: define java_home en projects.json")
    url = cfg["sonar_url"].rstrip("/")
    key = p.get("key") or p["folder"]
    extra = p.get("extra_args") or {}
    ptype = p.get("type")

    if ptype == "dotnet":
        env = make_env([HOME / ".dotnet/tools"])
        begin = [
            "dotnet-sonarscanner", "begin",
            f"/k:{key}",
            f"/d:sonar.host.url={url}",
            f"/d:sonar.token={token}",
            f"/d:sonar.scanner.javaExePath={jh / 'bin' / 'java'}",
        ] + [f"/d:{k}={v}" for k, v in extra.items()]
        build = ["dotnet", "build"] + ([p["solution"]] if p.get("solution") else []) + ["--no-incremental", "-p:WarningLevel=0"]
        end = ["dotnet-sonarscanner", "end", f"/d:sonar.token={token}"]
        labels = STEP_LABELS["dotnet"]
        steps = list(zip(labels, [begin, build, end]))
        cleanup = [".sonarqube"]
    elif ptype == "js":
        sb = find_scanner_bin(cfg)
        if not sb:
            raise ScanError("No encontré sonar-scanner: define sonar_scanner_bin en projects.json")
        env = make_env([jh / "bin", sb])
        env["JAVA_HOME"] = str(jh)
        args = [
            "sonar-scanner",
            f"-Dsonar.projectKey={key}",
            f"-Dsonar.sources={p.get('sources') or 'src'}",
            f"-Dsonar.host.url={url}",
            f"-Dsonar.token={token}",
            f"-Dsonar.exclusions={p.get('exclusions') or cfg['js_exclusions']}",
            f"-Dsonar.javascript.node.maxspace={cfg.get('js_node_maxspace', 4096)}",
        ] + [f"-D{k}={v}" for k, v in extra.items()]
        steps = [(STEP_LABELS["js"][0], args)]
        cleanup = [".scannerwork"]
    else:
        raise ScanError(f"Tipo de proyecto desconocido: {ptype} (usa \"dotnet\" o \"js\")")
    return path, env, steps, cleanup, token


class Job:
    def __init__(self, pid, ptype):
        self.pid = pid
        self.status = "queued"
        self.steps = STEP_LABELS.get(ptype, ["Analizar"])
        self.step_index = -1
        self.lines = []
        self.started = None
        self.ended = None
        self.proc = None
        self.cancelled = False

    def log(self, text):
        self.lines.append(text)

    def finish(self, status):
        self.status = status
        self.ended = time.time()

    def to_dict(self):
        return {
            "status": self.status, "steps": self.steps, "step_index": self.step_index,
            "started": self.started, "ended": self.ended, "lines": len(self.lines),
        }


JOBS = {}
JOBS_LOCK = threading.Lock()


def run_scan(job):
    if job.cancelled:
        return
    cfg = load_config()
    p = find_project(cfg, job.pid)
    job.status = "running"
    job.started = time.time()
    if not p:
        job.log("✖ El proyecto ya no está en projects.json")
        job.finish("error")
        return
    try:
        path, env, steps, cleanup, token = build_plan(p, cfg)
    except ScanError as e:
        job.log(f"✖ {e}")
        job.finish("error")
        _record(job)
        return

    def mask(s):
        return s.replace(token, "****") if token else s

    def clean():
        for c in cleanup:
            shutil.rmtree(path / c, ignore_errors=True)

    job.log(f"Proyecto {p['name']}  ({path})")
    clean()
    ok = True
    try:
        for i, (label, argv) in enumerate(steps):
            if job.cancelled:
                ok = False
                break
            job.step_index = i
            job.log("")
            job.log(f"▶ {label}")
            job.log("$ " + mask(" ".join(argv)))
            try:
                proc = subprocess.Popen(
                    argv, cwd=str(path), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, errors="replace", start_new_session=True,
                )
            except FileNotFoundError:
                job.log(f"✖ No se encontró el comando «{argv[0]}»")
                ok = False
                break
            job.proc = proc
            for line in proc.stdout:
                job.log(mask(line.rstrip("\n")))
            rc = proc.wait()
            job.proc = None
            if rc != 0:
                job.log(f"✖ «{label}» terminó con código {rc}")
                ok = False
                break
    finally:
        clean()

    if job.cancelled:
        job.log("■ Escaneo cancelado")
        job.finish("cancelled")
    elif ok:
        job.log("")
        job.log("✔ Escaneo enviado. SonarQube lo procesa en unos segundos.")
        job.finish("ok")
    else:
        job.finish("error")
    _record(job)


def _record(job):
    record_state(job.pid, {
        "status": job.status,
        "ended": job.ended,
        "duration": (job.ended - job.started) if job.started and job.ended else None,
    })


def enqueue(pids):
    """Encola proyectos y los ejecuta uno tras otro. Devuelve los que se encolaron."""
    cfg = load_config()
    jobs = []
    with JOBS_LOCK:
        for pid in pids:
            p = find_project(cfg, pid)
            if not p:
                continue
            cur = JOBS.get(pid)
            if cur and cur.status in ("queued", "running"):
                continue
            j = Job(pid, p.get("type"))
            JOBS[pid] = j
            jobs.append(j)

    def worker():
        for j in jobs:
            run_scan(j)

    if jobs:
        threading.Thread(target=worker, daemon=True).start()
    return [j.pid for j in jobs]


def cancel(pid):
    job = JOBS.get(pid)
    if not job or job.status not in ("queued", "running"):
        return False
    job.cancelled = True
    if job.status == "queued":
        job.log("■ Quitado de la cola")
        job.finish("cancelled")
    proc = job.proc
    if proc and proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            proc.terminate()
    return True


# --------------------------------------------------------------------------- sonar

_METRICS_CACHE = {"keys": None, "at": 0.0}


def sonar_get(cfg, path, timeout=4):
    req = urllib.request.Request(cfg["sonar_url"].rstrip("/") + path)
    tok = read_token(cfg)
    if tok:
        req.add_header("Authorization", "Basic " + base64.b64encode(f"{tok}:".encode()).decode())
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def available_metrics(cfg):
    if _METRICS_CACHE["keys"] and time.time() - _METRICS_CACHE["at"] < 600:
        return _METRICS_CACHE["keys"]
    keys, page = set(), 1
    while True:
        d = sonar_get(cfg, f"/api/metrics/search?ps=500&p={page}")
        keys.update(m["key"] for m in d.get("metrics", []))
        if page * 500 >= d.get("total", 0):
            break
        page += 1
    _METRICS_CACHE.update(keys=keys, at=time.time())
    return keys


def sonar_summary(cfg):
    out = {"up": False, "version": None, "url": cfg["sonar_url"], "measures": {}, "error": None}
    try:
        st = sonar_get(cfg, "/api/system/status", timeout=3)
        out["up"] = st.get("status") == "UP"
        out["status"] = st.get("status")
        out["version"] = st.get("version")
    except Exception as e:
        out["error"] = str(e)
        return out
    if not out["up"]:
        return out
    try:
        avail = available_metrics(cfg)
        metric_keys = ",".join(m for m in METRICS_WANTED if m in avail) or "alert_status"
    except Exception:
        metric_keys = "alert_status,bugs,vulnerabilities,code_smells,coverage"
    for p in cfg["projects"]:
        key = p.get("key") or p["folder"]
        try:
            d = sonar_get(cfg, f"/api/measures/component?component={quote(key)}&metricKeys={metric_keys}")
            vals = {}
            for m in d.get("component", {}).get("measures", []):
                v = m.get("value")
                if v is not None and m["metric"].startswith("software_quality_") and v.startswith("{"):
                    try:
                        v = str(json.loads(v).get("total", v))
                    except Exception:
                        pass
                vals[m["metric"]] = v
            out["measures"][key] = vals
        except urllib.error.HTTPError as e:
            if e.code == 401:
                out["error"] = "El token no es válido para la API de SonarQube"
                break
        except Exception:
            pass
    return out


# ---------------------------------------------------------------------------- http

def state_payload():
    cfg = load_config()
    st = load_state()
    ws = expand(cfg["workspace"])
    projects = []
    for p in cfg["projects"]:
        if p.get("hidden"):
            continue
        pid = p["folder"]
        job = JOBS.get(pid)
        projects.append({
            "id": pid, "name": p.get("name") or pid, "layer": p.get("layer") or "Otro",
            "folder": pid, "type": p.get("type"), "key": p.get("key") or pid,
            "exists": bool(ws and (ws / pid).is_dir()),
            "job": job.to_dict() if job else None,
            "last": st.get(pid),
        })
    return {
        "workspace": str(ws), "sonar_url": cfg["sonar_url"], "layers": LAYER_ORDER,
        "tools": tool_status(cfg), "projects": projects,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "SonarLocal/1.0"

    def log_message(self, *args):
        pass

    def _allowed(self):
        host = self.headers.get("Host", "")
        if host not in (f"127.0.0.1:{PORT}", f"localhost:{PORT}"):
            return False
        origin = self.headers.get("Origin")
        if origin and self.command == "POST":
            o = urlparse(origin)
            return o.hostname in ("127.0.0.1", "localhost") and o.port == PORT
        return True

    def _send(self, body, ctype, code=200):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8", code)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        if not self._allowed():
            return self._json({"error": "forbidden"}, 403)
        u = urlparse(self.path)
        parts = [unquote(x) for x in u.path.strip("/").split("/") if x]
        if u.path in ("/", "/index.html"):
            return self._send(INDEX_HTML, "text/html; charset=utf-8")
        if u.path == "/api/state":
            return self._json(state_payload())
        if u.path == "/api/sonar":
            return self._json(sonar_summary(load_config()))
        if len(parts) == 3 and parts[:2] == ["api", "logs"]:
            job = JOBS.get(parts[2])
            if not job:
                return self._json({"lines": [], "next": 0, "status": None})
            try:
                since = max(0, int(parse_qs(u.query).get("from", ["0"])[0]))
            except ValueError:
                since = 0
            lines = job.lines[since:]
            return self._json({"lines": lines, "next": since + len(lines), "status": job.status})
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self._allowed():
            return self._json({"error": "forbidden"}, 403)
        parts = [unquote(x) for x in urlparse(self.path).path.strip("/").split("/") if x]
        if len(parts) == 3 and parts[:2] == ["api", "scan"]:
            started = enqueue([parts[2]])
            return self._json({"queued": started}, 200 if started else 409)
        if parts == ["api", "scan-all"]:
            ids = self._body().get("ids")
            if not ids:
                ids = [p["folder"] for p in load_config()["projects"] if not p.get("hidden")]
            return self._json({"queued": enqueue(ids)})
        if len(parts) == 3 and parts[:2] == ["api", "cancel"]:
            return self._json({"ok": cancel(parts[2])})
        if parts == ["api", "discover"]:
            cfg = load_config()
            added = discover(cfg, cfg["projects"])
            if added:
                cfg["projects"].extend(added)
                save_config(cfg)
            return self._json({"added": [a["name"] for a in added]})
        return self._json({"error": "not found"}, 404)


# ---------------------------------------------------------------------------- page

INDEX_HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sonar Local</title>
<style>
:root{
  --bg:#EEF1F4; --surface:#FFFFFF; --ink:#16202C; --muted:#5E6A79; --line:#D9DEE5;
  --accent:#2448B8; --accent-ink:#FFFFFF; --accent-soft:#E4EAFB;
  --pass:#1C7448; --pass-bg:#DFF2E7; --fail:#B33A2B; --fail-bg:#FBE5E1;
  --run:#94600A; --run-bg:#FCF0D4; --todo:#C9D0D9;
  --log-bg:#0E131A; --log-ink:#D3DAE3; --log-dim:#7F8B99;
  --radius:10px; color-scheme:light;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#11161D; --surface:#19202A; --ink:#E6EAF0; --muted:#97A2B1; --line:#29323E;
    --accent:#7B9BF2; --accent-ink:#0C1424; --accent-soft:#1F2A44;
    --pass:#62C792; --pass-bg:#15301F; --fail:#F2877A; --fail-bg:#3A1D19;
    --run:#E9B64C; --run-bg:#352A10; --todo:#36404D;
    --log-bg:#0A0E13; color-scheme:dark;
  }
}
*{box-sizing:border-box}
html,body{margin:0}
body{
  background:var(--bg); color:var(--ink);
  font:15px/1.45 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif;
  padding-bottom:48vh;
}
button,a.btn{
  font:inherit; font-size:13.5px; font-weight:560; border-radius:7px; padding:7px 13px;
  border:1px solid var(--line); background:var(--surface); color:var(--ink);
  cursor:pointer; text-decoration:none; white-space:nowrap; display:inline-flex; align-items:center;
}
button:hover,a.btn:hover{border-color:var(--muted)}
button:focus-visible,a.btn:focus-visible{outline:2px solid var(--accent); outline-offset:2px}
button.primary{background:var(--accent); color:var(--accent-ink); border-color:var(--accent)}
button.primary:hover{filter:brightness(1.08)}
button:disabled{opacity:.45; cursor:not-allowed}

.wrap{max-width:1240px; margin:0 auto; padding:28px 24px}
.top{display:flex; align-items:flex-end; justify-content:space-between; gap:16px; flex-wrap:wrap}
.top h1{margin:0; font-size:30px; letter-spacing:-.02em; font-weight:720}
.where{margin:4px 0 0; color:var(--muted); font-size:13.5px}
.top .actions{display:flex; gap:8px; align-items:center; flex-wrap:wrap}
.status{display:inline-flex; align-items:center; gap:8px; font-size:13.5px; color:var(--muted); margin-right:6px}
.dot{width:9px; height:9px; border-radius:50%; background:var(--todo)}
.status.up .dot{background:var(--pass)}
.status.down .dot{background:var(--fail)}
.status.down{color:var(--fail)}

.tools{margin:18px 0 6px; display:flex; flex-wrap:wrap; gap:6px}
.chip{font-size:12.5px; padding:4px 10px; border-radius:20px; background:var(--surface); border:1px solid var(--line); color:var(--muted)}
.chip.bad{background:var(--fail-bg); border-color:transparent; color:var(--fail)}

.group{margin-top:28px}
.group-head{display:flex; align-items:baseline; gap:12px; margin:0 0 10px}
.group-head h2{margin:0; font-size:17px; font-weight:680}
.group-head .count{color:var(--muted); font-size:13px}
.group-head button{margin-left:auto; padding:4px 10px; font-size:12.5px}

.rows{background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); overflow:hidden}
.row{
  display:grid; align-items:center; gap:10px 18px; padding:14px 16px;
  grid-template-columns:minmax(210px,1.5fr) 70px 112px minmax(250px,2fr) 118px auto;
}
.row + .row{border-top:1px solid var(--line)}
.row.busy{background:linear-gradient(var(--run-bg),var(--run-bg)) left/3px 100% no-repeat}
.ident h3{margin:0; font-size:15.5px; font-weight:650; letter-spacing:-.005em}
.ident p{margin:2px 0 0; color:var(--muted); font-size:12.5px; word-break:break-all}
.kind{font-size:12px; font-weight:600; color:var(--muted)}
.gate{font-size:12.5px; font-weight:650; padding:4px 9px; border-radius:6px; text-align:center; background:var(--bg); color:var(--muted)}
.gate.pass{background:var(--pass-bg); color:var(--pass)}
.gate.fail{background:var(--fail-bg); color:var(--fail)}
.gate.warn{background:var(--run-bg); color:var(--run)}
.metrics{display:flex; gap:16px; margin:0; flex-wrap:wrap}
.metrics div{display:flex; flex-direction:column-reverse}
.metrics dt{font-size:11.5px; color:var(--muted)}
.metrics dd{margin:0; font-size:15px; font-weight:640; font-variant-numeric:tabular-nums}
.metrics dd.zero{color:var(--muted); font-weight:500}
.last{font-size:12.5px; color:var(--muted)}
.last .err{color:var(--fail)}
.last .ok{color:var(--pass)}
.btns{display:flex; gap:6px; justify-content:flex-end}

.pipe{grid-column:1/-1; display:flex; gap:4px; align-items:center}
.seg{flex:1; display:flex; flex-direction:column; gap:5px; font-size:12px; color:var(--muted)}
.seg i{display:block; height:5px; border-radius:3px; background:var(--todo); overflow:hidden; position:relative}
.seg.done i{background:var(--pass)}
.seg.active{color:var(--run); font-weight:600}
.seg.active i{background:var(--run-bg)}
.seg.active i::after{content:""; position:absolute; inset:0 auto 0 0; width:40%; background:var(--run); border-radius:3px; animation:slide 1.3s ease-in-out infinite}
@keyframes slide{0%{transform:translateX(-100%)}100%{transform:translateX(260%)}}
.queued{grid-column:1/-1; font-size:12.5px; color:var(--run)}

.empty{background:var(--surface); border:1px dashed var(--line); border-radius:var(--radius); padding:28px; margin-top:24px}
.empty h2{margin:0 0 6px; font-size:17px}
.empty p{margin:0 0 14px; color:var(--muted)}

.drawer{
  position:fixed; left:0; right:0; bottom:0; height:44vh; background:var(--log-bg); color:var(--log-ink);
  display:flex; flex-direction:column; transform:translateY(100%); transition:transform .22s ease;
  box-shadow:0 -1px 0 var(--line);
}
.drawer.open{transform:none}
.drawer-head{display:flex; align-items:center; gap:12px; padding:10px 18px; border-bottom:1px solid #222b36}
.drawer-head strong{font-size:14px}
.drawer-head .st{font-size:12.5px; color:var(--log-dim)}
.drawer-head button{margin-left:auto; background:transparent; color:var(--log-ink); border-color:#2c3744}
.drawer pre{
  margin:0; padding:12px 18px 24px; overflow:auto; flex:1;
  font:12.5px/1.5 ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace; white-space:pre-wrap; word-break:break-word;
}
.l-step{color:#9DB7FF; font-weight:700}
.l-cmd{color:var(--log-dim)}
.l-err{color:#FF9A8C}
.l-ok{color:#7FDCA5; font-weight:600}
.l-warn{color:#F2C46B}

.toast{position:fixed; top:16px; right:16px; background:var(--ink); color:var(--surface); padding:10px 14px; border-radius:8px; font-size:13.5px; opacity:0; transform:translateY(-6px); transition:.2s; pointer-events:none; max-width:360px}
.toast.show{opacity:1; transform:none}

@media (max-width: 980px){
  .row{grid-template-columns:1fr auto; }
  .kind{justify-self:end}
  .gate{justify-self:start}
  .metrics,.last,.btns{grid-column:1/-1}
  .btns{justify-content:flex-start; flex-wrap:wrap}
}
@media (prefers-reduced-motion: reduce){
  .drawer,.toast{transition:none}
  .seg.active i::after{animation:none; width:100%}
}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div>
      <h1>Sonar Local</h1>
      <p class="where" id="where"></p>
    </div>
    <div class="actions">
      <span class="status" id="sonarStatus"><span class="dot"></span><span>Conectando con SonarQube…</span></span>
      <button id="btnDiscover">Detectar proyectos</button>
      <button id="btnAll" class="primary">Escanear todos</button>
    </div>
  </header>
  <div class="tools" id="tools"></div>
  <main id="list"></main>
</div>

<section class="drawer" id="drawer" aria-label="Log del escaneo">
  <div class="drawer-head">
    <strong id="logTitle"></strong><span class="st" id="logStatus"></span>
    <button id="logClose">Cerrar</button>
  </div>
  <pre id="logBody"></pre>
</section>
<div class="toast" id="toast" role="status"></div>

<script>
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state = null, sonar = null, lastSig = '', running = new Set();
let logId = null, logFrom = 0, logTimer = null, stateTimer = null;

async function api(path, opts){
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok && r.status !== 409) throw new Error(data.error || r.statusText);
  return data;
}
function toast(msg){
  const t = $('#toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove('show'), 2600);
}
function ago(ts){
  if (!ts) return '';
  const s = Math.max(0, Date.now()/1000 - ts);
  if (s < 60) return 'hace un momento';
  if (s < 3600) return `hace ${Math.round(s/60)} min`;
  if (s < 86400) return `hace ${Math.round(s/3600)} h`;
  const d = Math.round(s/86400); return d === 1 ? 'ayer' : `hace ${d} días`;
}
function dur(s){
  if (!s && s !== 0) return '';
  s = Math.round(s); const m = Math.floor(s/60);
  return m ? `${m} min ${s%60} s` : `${s} s`;
}
function isBusy(p){ return p.job && (p.job.status === 'running' || p.job.status === 'queued'); }

function gateInfo(m){
  const g = m && m.alert_status;
  if (g === 'OK') return {cls:'pass', label:'Aprobado'};
  if (g === 'ERROR') return {cls:'fail', label:'No aprobado'};
  if (g === 'WARN') return {cls:'warn', label:'Advertencia'};
  return {cls:'', label: m ? 'Sin quality gate' : 'Sin análisis'};
}
function metric(label, v, suffix=''){
  if (v === undefined || v === null) return '';
  const n = Number(v);
  const txt = Number.isFinite(n) ? (suffix ? n.toFixed(1).replace('.', ',') + suffix : n.toLocaleString('es')) : v;
  return `<div><dt>${label}</dt><dd class="${n === 0 ? 'zero' : ''}">${esc(txt)}</dd></div>`;
}
function metricsHtml(m){
  if (!m) return '<span class="last">Todavía no hay datos en SonarQube</span>';
  return metric('Bugs', m.bugs ?? m.software_quality_reliability_issues)
       + metric('Vulnerab.', m.vulnerabilities ?? m.software_quality_security_issues)
       + metric('Code smells', m.code_smells ?? m.software_quality_maintainability_issues)
       + metric('Hotspots', m.security_hotspots)
       + metric('Cobertura', m.coverage, ' %');
}
function lastHtml(p){
  const j = p.job;
  if (j && j.status === 'running') return `<span>Escaneando desde ${ago(j.started)}</span>`;
  if (j && j.status === 'queued') return `<span>En cola</span>`;
  const l = (j && j.ended) ? {status:j.status, ended:j.ended, duration:j.ended - (j.started||j.ended)} : p.last;
  if (!l || !l.ended) return '<span>Nunca escaneado desde aquí</span>';
  const tag = l.status === 'ok' ? '<span class="ok">Correcto</span>'
            : l.status === 'cancelled' ? '<span>Cancelado</span>' : '<span class="err">Falló</span>';
  return `${tag} ${ago(l.ended)}${l.duration ? '<br>' + dur(l.duration) : ''}`;
}
function pipeHtml(j){
  if (j.status === 'queued') return '<div class="queued">En cola: empieza cuando termine el escaneo anterior</div>';
  return '<div class="pipe">' + j.steps.map((s, i) => {
    const c = i < j.step_index ? 'done' : i === j.step_index ? 'active' : '';
    return `<div class="seg ${c}"><i></i>${esc(s)}</div>`;
  }).join('') + '</div>';
}
function rowHtml(p){
  const m = sonar && sonar.measures ? sonar.measures[p.key] : null;
  const g = gateInfo(m), busy = isBusy(p);
  const dash = (state.sonar_url || '').replace(/\/$/, '') + '/dashboard?id=' + encodeURIComponent(p.key);
  const main = busy
    ? `<button data-act="cancel">Cancelar</button>`
    : `<button data-act="scan" class="primary" ${p.exists ? '' : 'disabled title="No encuentro la carpeta"'}>Escanear</button>`;
  return `<article class="row ${busy ? 'busy' : ''}" data-id="${esc(p.id)}">
    <div class="ident"><h3>${esc(p.name)}</h3><p>${esc(p.folder)}${p.exists ? '' : ' (carpeta no encontrada)'}</p></div>
    <span class="kind">${p.type === 'dotnet' ? '.NET' : 'JS / TS'}</span>
    <span class="gate ${g.cls}">${g.label}</span>
    <dl class="metrics">${metricsHtml(m)}</dl>
    <div class="last">${lastHtml(p)}</div>
    <div class="btns">${main}<button data-act="log">Log</button><a class="btn" href="${esc(dash)}" target="_blank" rel="noopener">Abrir en Sonar</a></div>
    ${busy ? pipeHtml(p.job) : ''}
  </article>`;
}
function render(){
  if (!state) return;
  const sig = JSON.stringify([state.projects, state.tools, sonar && sonar.measures, Math.floor(Date.now()/30000)]);
  if (sig === lastSig) return; lastSig = sig;

  $('#where').textContent = state.workspace;
  const bad = state.tools.filter(t => !t.ok);
  $('#tools').innerHTML = bad.length
    ? bad.map(t => `<span class="chip bad" title="${esc(t.detail)}">Falta ${esc(t.name)}: ${esc(t.detail)}</span>`).join('')
    : `<span class="chip">Listo: ${state.tools.map(t => esc(t.name)).join(', ')}</span>`;

  if (!state.projects.length){
    $('#list').innerHTML = `<div class="empty"><h2>No hay proyectos todavía</h2>
      <p>Busco carpetas con un .sln, .csproj o package.json dentro de ${esc(state.workspace)}.</p>
      <button class="primary" data-act="discover">Detectar proyectos</button></div>`;
    return;
  }
  const groups = {};
  for (const p of state.projects) (groups[p.layer] ||= []).push(p);
  const order = [...state.layers.filter(l => groups[l]), ...Object.keys(groups).filter(l => !state.layers.includes(l))];
  $('#list').innerHTML = order.map(l => `<section class="group">
      <div class="group-head"><h2>${esc(l)}</h2><span class="count">${groups[l].length} ${groups[l].length === 1 ? 'proyecto' : 'proyectos'}</span>
      <button data-act="group" data-layer="${esc(l)}">Escanear ${esc(l)}</button></div>
      <div class="rows">${groups[l].map(rowHtml).join('')}</div></section>`).join('');
}

async function refreshState(){
  try{
    state = await api('/api/state');
    const now = new Set(state.projects.filter(isBusy).map(p => p.id));
    const finished = [...running].filter(id => !now.has(id));
    running = now;
    if (finished.length){ setTimeout(refreshSonar, 4000); setTimeout(refreshSonar, 12000); }
    render();
  }catch(e){ toast('No pude leer el estado: ' + e.message); }
  clearTimeout(stateTimer); stateTimer = setTimeout(refreshState, running.size ? 1500 : 8000);
}
async function refreshSonar(){
  try{
    sonar = await api('/api/sonar');
    const el = $('#sonarStatus');
    el.className = 'status ' + (sonar.up ? 'up' : 'down');
    el.lastElementChild.textContent = sonar.up
      ? `SonarQube ${sonar.version || ''} en línea`
      : `SonarQube no responde en ${sonar.url}. ¿Está corriendo el contenedor?`;
    if (sonar.up && sonar.error) toast(sonar.error);
    render();
  }catch(e){}
}

function lineClass(t){
  if (t.startsWith('▶')) return 'l-step';
  if (t.startsWith('$ ')) return 'l-cmd';
  if (t.startsWith('✖') || /\b(ERROR|error [A-Z]+\d+|EXECUTION FAILURE)\b/.test(t)) return 'l-err';
  if (t.startsWith('✔') || /EXECUTION SUCCESS|ANALYSIS SUCCESSFUL/.test(t)) return 'l-ok';
  if (/\bWARN(ING)?\b/.test(t)) return 'l-warn';
  return '';
}
function openLog(id){
  const p = state.projects.find(x => x.id === id);
  logId = id; logFrom = 0;
  $('#logTitle').textContent = p ? p.name : id;
  $('#logBody').textContent = '';
  $('#drawer').classList.add('open');
  clearTimeout(logTimer); pollLog();
}
async function pollLog(){
  if (!logId) return;
  const id = logId;
  try{
    const d = await api(`/api/logs/${encodeURIComponent(id)}?from=${logFrom}`);
    if (id !== logId) return;
    const pre = $('#logBody');
    const atBottom = pre.scrollHeight - pre.scrollTop - pre.clientHeight < 40;
    if (!d.status && logFrom === 0) pre.textContent = 'Este proyecto no se escaneó desde que abriste la app.';
    const frag = document.createDocumentFragment();
    for (const t of d.lines){
      const s = document.createElement('span'); s.className = lineClass(t); s.textContent = t + '\n'; frag.appendChild(s);
    }
    pre.appendChild(frag); logFrom = d.next;
    if (atBottom) pre.scrollTop = pre.scrollHeight;
    const labels = {running:'Escaneando…', queued:'En cola', ok:'Terminado', error:'Falló', cancelled:'Cancelado'};
    $('#logStatus').textContent = labels[d.status] || '';
    if (d.status === 'running' || d.status === 'queued') logTimer = setTimeout(pollLog, 700);
  }catch(e){ logTimer = setTimeout(pollLog, 2000); }
}
$('#logClose').onclick = () => { logId = null; clearTimeout(logTimer); $('#drawer').classList.remove('open'); };

async function scan(ids){
  const d = ids.length === 1
    ? await api('/api/scan/' + encodeURIComponent(ids[0]), {method:'POST'})
    : await api('/api/scan-all', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ids})});
  if (!d.queued || !d.queued.length) toast('Ya está en curso');
  else toast(d.queued.length === 1 ? 'Escaneo iniciado' : `${d.queued.length} escaneos en cola`);
  if (ids.length === 1) openLog(ids[0]);
  lastSig = ''; refreshState();
}
async function discover(){
  const d = await api('/api/discover', {method:'POST'});
  toast(d.added.length ? `Agregados: ${d.added.join(', ')}` : 'No hay proyectos nuevos');
  lastSig = ''; state = await api('/api/state'); render(); refreshSonar();
}

document.addEventListener('click', async ev => {
  const b = ev.target.closest('[data-act]'); if (!b) return;
  const row = b.closest('.row'), id = row && row.dataset.id;
  try{
    switch (b.dataset.act){
      case 'scan': await scan([id]); break;
      case 'cancel': await api('/api/cancel/' + encodeURIComponent(id), {method:'POST'}); toast('Cancelando…'); break;
      case 'log': openLog(id); break;
      case 'group': await scan(state.projects.filter(p => p.layer === b.dataset.layer && p.exists).map(p => p.id)); break;
      case 'discover': await discover(); break;
    }
  }catch(e){ toast(e.message); }
});
$('#btnAll').onclick = () => scan(state.projects.filter(p => p.exists).map(p => p.id)).catch(e => toast(e.message));
$('#btnDiscover').onclick = () => discover().catch(e => toast(e.message));

refreshState(); refreshSonar(); setInterval(refreshSonar, 30000);
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------- main

def main():
    cfg = load_config()
    added = discover(cfg, cfg["projects"])
    if added:
        cfg["projects"].extend(added)
        save_config(cfg)
        print("Proyectos nuevos detectados:")
        for a in added:
            print(f"  + {a['name']:<32} {a['layer']:<18} {a['folder']}")
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"\nSonar Local corriendo en {url}  (Ctrl+C para salir)")
    print(f"Configuración: {CONFIG_FILE}\n")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nHasta luego.")
        for job in list(JOBS.values()):
            cancel(job.pid)


if __name__ == "__main__":
    main()
