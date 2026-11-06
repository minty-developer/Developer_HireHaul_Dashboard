from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Response

from ..db import connect, upsert_blog
from ..deps import AdminOnly, DatabasePath
from ..errors import ApiError
from ..schemas import BlogCreateRequest, BlogUpdateRequest

router = APIRouter(prefix="/api/admin/blogs", tags=["admin"], dependencies=[AdminOnly])


@router.get("", summary="전체 블로그 관리 목록")
def list_admin_blogs(database_path: DatabasePath):
    with connect(database_path) as db:
        rows = db.execute(
            """
            SELECT b.*, COUNT(a.id) AS article_count
            FROM blogs b
            LEFT JOIN articles a ON a.blog_id = b.id
            GROUP BY b.id
            ORDER BY b.company, b.name
            """
        ).fetchall()
    return {"count": len(rows), "blogs": [dict(row) for row in rows]}


@router.post("", status_code=201, summary="블로그 등록")
def create_admin_blog(body: BlogCreateRequest, database_path: DatabasePath):
    values = body.model_dump()
    values["active"] = int(values["active"])
    with connect(database_path) as db:
        existing = db.execute(
            "SELECT id FROM blogs WHERE feed_url = ?", (values["feed_url"],)
        ).fetchone()
    if existing:
        raise ApiError(409, "이미 등록된 피드 URL입니다.", ok_field=True)
    try:
        blog_id = upsert_blog(database_path, values)
    except sqlite3.IntegrityError:
        raise ApiError(409, "블로그를 저장할 수 없습니다.", ok_field=True) from None
    with connect(database_path) as db:
        row = db.execute("SELECT * FROM blogs WHERE id = ?", (blog_id,)).fetchone()
    return {"blog": dict(row)}


@router.patch("/{blog_id}", summary="블로그 수정·재활성화")
def update_admin_blog(blog_id: int, body: BlogUpdateRequest, database_path: DatabasePath):
    values = {field: getattr(body, field) for field in body.model_fields_set}
    if not values:
        raise ApiError(400, "수정할 필드가 없습니다.", ok_field=True)
    if any(value is None for value in values.values()):
        raise ApiError(400, "필드 값으로 null을 사용할 수 없습니다.", ok_field=True)
    if "active" in values:
        values["active"] = int(values["active"])

    # 컬럼 이름은 Pydantic 모델에 정의된 필드로만 제한된다.
    assignments = ", ".join(f"{field} = ?" for field in values)
    try:
        with connect(database_path) as db:
            cursor = db.execute(
                f"UPDATE blogs SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                [*values.values(), blog_id],
            )
            row = db.execute("SELECT * FROM blogs WHERE id = ?", (blog_id,)).fetchone()
    except sqlite3.IntegrityError:
        raise ApiError(409, "이미 등록된 피드 URL입니다.", ok_field=True) from None
    if cursor.rowcount == 0:
        raise ApiError(404, "블로그를 찾을 수 없습니다.", ok_field=True)
    return {"blog": dict(row)}


@router.delete("/{blog_id}", status_code=204, summary="블로그 비활성화")
def deactivate_admin_blog(blog_id: int, database_path: DatabasePath):
    with connect(database_path) as db:
        cursor = db.execute(
            "UPDATE blogs SET active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (blog_id,),
        )
    if cursor.rowcount == 0:
        raise ApiError(404, "블로그를 찾을 수 없습니다.", ok_field=True)
    return Response(status_code=204)
