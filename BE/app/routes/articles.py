from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from ..db import connect
from ..deps import DatabasePath
from ..errors import ApiError
from ..schemas import ArticleDetailResponse, ArticleListResponse
from ..search import ArticleQuery, search_articles

router = APIRouter(tags=["articles"])


def _parse_date(value: str | None) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ApiError(400, "날짜는 YYYY-MM-DD 형식이어야 합니다.", ok_field=True) from None


@router.get(
    "/api/articles",
    response_model=ArticleListResponse,
    summary="게시글 검색 및 목록 조회",
    description=(
        "`q`는 공백으로 구분한 모든 단어가 제목·요약·본문·작성자 중 하나에 포함된 글을 찾습니다. "
        "3글자 이상 단어는 전문 검색 색인을 사용합니다. `sort=relevance`는 검색 관련도순입니다."
    ),
)
def list_articles(
    database_path: DatabasePath,
    q: Annotated[str, Query(max_length=200, description="검색어")] = "",
    blog_id: Annotated[int | None, Query(ge=1)] = None,
    company: Annotated[str, Query(max_length=100, description="회사명 정확히 일치")] = "",
    date_from: Annotated[str | None, Query(alias="from", description="YYYY-MM-DD")] = None,
    date_to: Annotated[str | None, Query(alias="to", description="YYYY-MM-DD")] = None,
    sort: Literal["latest", "relevance"] = "latest",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    start, end = _parse_date(date_from), _parse_date(date_to)
    if start and end and start > end:
        raise ApiError(400, "from은 to보다 늦을 수 없습니다.", ok_field=True)

    total, rows = search_articles(database_path, ArticleQuery(
        q=q.strip(),
        blog_id=blog_id,
        company=company.strip(),
        date_from=start,
        date_to=end,
        sort=sort,
        limit=limit,
        offset=offset,
    ))
    return {
        "count": len(rows),
        "total": total,
        "limit": limit,
        "offset": offset,
        "articles": rows,
    }


@router.get(
    "/api/articles/{article_id}",
    response_model=ArticleDetailResponse,
    summary="게시글 상세 조회",
)
def article_detail(article_id: int, database_path: DatabasePath):
    with connect(database_path) as db:
        row = db.execute(
            """
            SELECT a.*, b.name AS blog_name, b.company, b.site_url AS blog_site_url
            FROM articles a
            JOIN blogs b ON b.id = a.blog_id
            WHERE a.id = ? AND b.active = 1
            """,
            (article_id,),
        ).fetchone()
    if row is None:
        raise ApiError(404, "게시글을 찾을 수 없습니다.", ok_field=True)
    return {"article": dict(row)}
