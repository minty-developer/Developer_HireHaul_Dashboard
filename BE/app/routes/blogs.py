from fastapi import APIRouter

from ..db import connect
from ..deps import DatabasePath
from ..errors import ApiError
from ..schemas import BlogDetailResponse, BlogListResponse

router = APIRouter(tags=["blogs"])

BLOG_SELECT = """
    SELECT
        b.id, b.name, b.company, b.feed_url, b.site_url,
        b.description, b.last_checked_at, b.last_success_at,
        COUNT(a.id) AS article_count
    FROM blogs b
    LEFT JOIN articles a ON a.blog_id = b.id
"""


@router.get("/api/blogs", response_model=BlogListResponse, summary="활성 기술 블로그 목록")
def list_blogs(database_path: DatabasePath):
    with connect(database_path) as db:
        rows = db.execute(
            f"{BLOG_SELECT} WHERE b.active = 1 GROUP BY b.id ORDER BY b.company, b.name"
        ).fetchall()
    return {"count": len(rows), "blogs": [dict(row) for row in rows]}


@router.get(
    "/api/blogs/{blog_id}", response_model=BlogDetailResponse, summary="기술 블로그 상세 조회"
)
def blog_detail(blog_id: int, database_path: DatabasePath):
    with connect(database_path) as db:
        row = db.execute(
            f"{BLOG_SELECT} WHERE b.id = ? AND b.active = 1 GROUP BY b.id", (blog_id,)
        ).fetchone()
    if row is None:
        raise ApiError(404, "블로그를 찾을 수 없습니다.", ok_field=True)
    return {"blog": dict(row)}
