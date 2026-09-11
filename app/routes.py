from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from .db import connect, upsert_jobs
from .providers import SampleProvider


bp = Blueprint("main", __name__)


@bp.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/api/jobs")
def jobs():
    keyword = request.args.get("q", "").strip()
    location = request.args.get("location", "").strip()
    source = request.args.get("source", "").strip()
    limit = min(max(request.args.get("limit", 50, type=int), 1), 200)
    clauses, values = ["active = 1"], []
    if keyword:
        clauses.append("(title LIKE ? OR company LIKE ? OR keywords LIKE ?)")
        values.extend([f"%{keyword}%"] * 3)
    if location:
        clauses.append("location LIKE ?")
        values.append(f"%{location}%")
    if source:
        clauses.append("source = ?")
        values.append(source)
    sql = f"SELECT * FROM jobs WHERE {' AND '.join(clauses)} ORDER BY posted_at DESC LIMIT ?"
    values.append(limit)
    with connect(current_app.config["DATABASE_PATH"]) as db:
        rows = [dict(row) for row in db.execute(sql, values).fetchall()]
    return jsonify({"count": len(rows), "jobs": rows})


@bp.get("/api/stats")
def stats():
    with connect(current_app.config["DATABASE_PATH"]) as db:
        total = db.execute("SELECT COUNT(*) FROM jobs WHERE active=1").fetchone()[0]
        companies = db.execute("SELECT COUNT(DISTINCT company) FROM jobs WHERE active=1").fetchone()[0]
        sources = [dict(row) for row in db.execute(
            "SELECT source, COUNT(*) AS count FROM jobs WHERE active=1 GROUP BY source"
        ).fetchall()]
    return jsonify({"total": total, "companies": companies, "sources": sources})


@bp.post("/api/sync")
def sync():
    body = request.get_json(silent=True) or {}
    keyword = str(body.get("keyword") or current_app.config["DEFAULT_KEYWORDS"])
    try:
        provider = SampleProvider()
        fetched = provider.fetch(keyword, int(body.get("count", 50)))
        count = upsert_jobs(current_app.config["DATABASE_PATH"], fetched)
        return jsonify({"ok": True, "source": provider.name, "saved": count})
    except (ValueError, OSError, TimeoutError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502
