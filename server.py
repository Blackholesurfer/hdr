#!/usr/bin/env python3
"""Flask backend for the Image-to-Video Generation showcase.

Endpoints:
  GET  /                       → showcase.html
  GET  /<path>                 → static files (with path traversal guard)
  POST /api/upload             → start a job; returns {"job_id": ...}
  GET  /api/status/<job_id>    → poll job status + progress
  GET  /uploads/<job_id>/result.html → generated video page (built on completion)
"""

from pathlib import Path
from datetime import datetime
import html
import json
import os
import secrets
import threading
import traceback
from typing import Optional

from flask import Flask, jsonify, request, send_from_directory, abort

from pipeline import run_pipeline, IMAGE_EXTS, load_prompts, save_prompts

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "").strip()

BASE_DIR = Path(__file__).parent.resolve()
UPLOAD_ROOT = BASE_DIR / "uploads"
UPLOAD_ROOT.mkdir(exist_ok=True)
JOBS_INDEX = UPLOAD_ROOT / "jobs.json"
JOBS_INDEX_LOCK = threading.Lock()


def _load_jobs_index() -> list[dict]:
    if not JOBS_INDEX.exists():
        return []
    try:
        return json.loads(JOBS_INDEX.read_text(encoding="utf-8")).get("jobs", [])
    except (json.JSONDecodeError, OSError):
        return []


def _append_job_to_index(entry: dict) -> None:
    with JOBS_INDEX_LOCK:
        jobs = _load_jobs_index()
        jobs = [j for j in jobs if j.get("id") != entry.get("id")]
        jobs.append(entry)
        JOBS_INDEX.write_text(
            json.dumps({"jobs": jobs}, indent=2),
            encoding="utf-8",
        )


def _delete_job_from_index(job_id: str) -> bool:
    with JOBS_INDEX_LOCK:
        jobs = _load_jobs_index()
        new = [j for j in jobs if j.get("id") != job_id]
        if len(new) == len(jobs):
            return False
        JOBS_INDEX.write_text(
            json.dumps({"jobs": new}, indent=2),
            encoding="utf-8",
        )
        return True

app = Flask(__name__, static_folder=None)

# Allow the static showcase page (hosted elsewhere, e.g. blackholesurfer.com)
# to call this API from the browser.
ALLOWED_ORIGINS = {
    "https://blackholesurfer.com",
    "http://blackholesurfer.com",
    "https://www.blackholesurfer.com",
    "http://www.blackholesurfer.com",
    "http://localhost:8765",
    "http://127.0.0.1:8765",
}


@app.after_request
def _cors(response):
    origin = request.headers.get("Origin")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/api/upload", methods=["OPTIONS"])
@app.route("/api/status/<job_id>", methods=["OPTIONS"])
@app.route("/api/prompts", methods=["OPTIONS"])
@app.route("/api/jobs", methods=["OPTIONS"])
@app.route("/api/jobs/<job_id>", methods=["OPTIONS"])
def _cors_preflight(job_id=None):
    return ("", 204)


def _check_admin() -> Optional[tuple]:
    """Return a Flask error response tuple if the request is not authorized,
    otherwise None. If no ADMIN_TOKEN is set on the server, the endpoint is
    open (useful for purely-local dev)."""
    if not ADMIN_TOKEN:
        return None
    supplied = request.headers.get("X-Admin-Token", "").strip()
    if not supplied or not secrets.compare_digest(supplied, ADMIN_TOKEN):
        return jsonify({"error": "unauthorized"}), 401
    return None

# In-memory job registry. The Flask dev server is single-process, so a dict
# with a lock is sufficient for the per-upload jobs we run here.
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def _set_status(job_id: str, **fields) -> None:
    with JOBS_LOCK:
        JOBS[job_id].update(fields)


def _build_result_page(job_dir: Path, video_rel: str) -> Path:
    page = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Generated Video · {job_dir.name}</title>
<style>
  body {{ background:#0a0a0c; color:#e8e8ec; font-family:-apple-system,Helvetica,Arial,sans-serif; margin:0; padding:24px; }}
  header {{ display:flex; align-items:center; gap:16px; margin-bottom:16px; }}
  header img {{ height:48px; background:#fff; padding:4px 8px; border-radius:4px; }}
  header h1 {{ margin:0; font-weight:300; letter-spacing:0.05em; font-size:20px; }}
  a {{ color:#9fd3ff; text-decoration:none; font-size:13px; }}
  .video-wrap {{ background:#000; border:1px solid #2a2a32; border-radius:12px; overflow:hidden; max-width:1280px; margin:0 auto; }}
  video {{ width:100%; display:block; }}
  .meta {{ max-width:1280px; margin:12px auto 0; color:#9a9aa6; font-size:12px; }}
</style></head><body>
<header>
  <img src="/bhs_logo.jpg" alt="BHS">
  <div>
    <h1>Generated Video · {html.escape(job_dir.name)}</h1>
    <a href="/showcase.html">← back to showcase</a>
  </div>
</header>
<div class="video-wrap">
  <video src="{html.escape(video_rel)}" autoplay loop playsinline controls></video>
</div>
<div class="meta">Forward + reverse boomerang loop. <a href="{html.escape(video_rel)}" download>Download MP4</a></div>
</body></html>
"""
    out = job_dir / "result.html"
    out.write_text(page, encoding="utf-8")
    return out


def _run_job(job_id: str, job_dir: Path, raw_dir: Path) -> None:
    def status(stage: str, info: Optional[dict]) -> None:
        _set_status(job_id, stage=stage, info=info or {})

    try:
        _set_status(job_id, state="running", stage="starting", info={})
        final_pp = run_pipeline(raw_dir, job_dir, status)
        rel = f"/uploads/{job_id}/{final_pp.name}"
        link = f"/uploads/{job_id}/result.html"
        _build_result_page(job_dir, final_pp.name)
        # Count input images so the history panel can show "12 images".
        try:
            count = sum(1 for p in raw_dir.iterdir() if p.is_file())
        except OSError:
            count = 0
        _append_job_to_index({
            "id": job_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "video": rel,
            "link": link,
            "count": count,
        })
        _set_status(
            job_id,
            state="done",
            stage="done",
            info={},
            video=rel,
            link=link,
        )
    except Exception as e:
        traceback.print_exc()
        _set_status(job_id, state="error", stage="error", info={"message": str(e)})


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "showcase.html")


@app.route("/<path:filename>")
def static_files(filename: str):
    target = (BASE_DIR / filename).resolve()
    if not str(target).startswith(str(BASE_DIR)):
        abort(404)
    if not target.is_file():
        abort(404)
    return send_from_directory(BASE_DIR, filename)


@app.route("/api/upload", methods=["POST"])
def upload():
    files = request.files.getlist("images")
    if not files:
        return jsonify({"error": "No files received"}), 400

    job_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
    job_dir = UPLOAD_ROOT / job_id
    raw_dir = job_dir / "raw"
    raw_dir.mkdir(parents=True)

    saved = 0
    skipped: list[str] = []
    for f in files:
        original_name = Path(f.filename or "").name
        if not original_name:
            continue
        ext = Path(original_name).suffix.lower()
        if ext not in IMAGE_EXTS:
            skipped.append(original_name)
            continue
        f.save(raw_dir / original_name)
        saved += 1

    if saved == 0:
        return jsonify({"error": "No valid images saved", "skipped": skipped}), 400

    with JOBS_LOCK:
        JOBS[job_id] = {
            "state": "queued",
            "stage": "queued",
            "info": {},
            "saved": saved,
            "skipped": skipped,
        }

    t = threading.Thread(target=_run_job, args=(job_id, job_dir, raw_dir), daemon=True)
    t.start()

    return jsonify({"job_id": job_id, "saved": saved, "skipped": skipped})


@app.route("/api/prompts", methods=["GET"])
def get_prompts():
    err = _check_admin()
    if err is not None:
        return err
    return jsonify({"prompts": load_prompts(), "auth_required": bool(ADMIN_TOKEN)})


@app.route("/api/prompts", methods=["POST"])
def post_prompts():
    err = _check_admin()
    if err is not None:
        return err
    data = request.get_json(silent=True) or {}
    prompts = data.get("prompts")
    if not isinstance(prompts, list) or not all(isinstance(p, str) for p in prompts):
        return jsonify({"error": "Body must be {\"prompts\": [\"...\", ...]}"}), 400
    cleaned = [p.strip() for p in prompts if p.strip()]
    if not cleaned:
        return jsonify({"error": "At least one non-empty prompt is required"}), 400
    save_prompts(cleaned)
    return jsonify({"saved": len(cleaned)})


@app.route("/api/jobs", methods=["GET"])
def list_jobs():
    jobs = sorted(_load_jobs_index(), key=lambda j: j.get("created_at", ""), reverse=True)
    return jsonify({"jobs": jobs})


@app.route("/api/jobs/<job_id>", methods=["DELETE"])
def delete_job(job_id: str):
    err = _check_admin()
    if err is not None:
        return err
    removed = _delete_job_from_index(job_id)
    return jsonify({"removed": removed})


@app.route("/api/status/<job_id>")
def status(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({"error": "unknown job_id"}), 404
        return jsonify(job)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8765, debug=False, threaded=True)
