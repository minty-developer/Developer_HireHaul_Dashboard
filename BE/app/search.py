"""게시글 검색.

- 검색어는 공백으로 나눠 모든 단어가 포함된 글만 찾는다(AND).
- 3글자 이상 단어는 FTS5 trigram 색인으로, 1~2글자 단어는 LIKE로 찾는다.
  trigram 색인은 3글자 미만 문자열을 찾을 수 없기 때문이다.
- sort=relevance면 FTS 점수(bm25)순, 기본값 latest면 게시일 최신순으로 정렬한다.
"""
from __future__ import annotations

from dataclasses import dataclass

from .db import connect

SORTS = ("latest", "relevance")
MAX_TERMS = 10
LIST_COLUMNS = """
    a.id, a.blog_id, a.entry_key, a.title, a.url, a.author,
    a.summary, a.published_at, a.feed_updated_at, a.fetched_at,
    b.name AS blog_name, b.company
"""


@dataclass
class ArticleQuery:
    q: str = ""
    blog_id: int | None = None
    company: str = ""
    date_from: str = ""
    date_to: str = ""
    sort: str = "latest"
    limit: int = 20
    offset: int = 0


def split_terms(query: str) -> list[str]:
    seen: list[str] = []
    for term in query.split():
        if term.casefold() not in (existing.casefold() for existing in seen):
            seen.append(term)
    return seen[:MAX_TERMS]


def _fts_phrase(term: str) -> str:
    # 큰따옴표로 감싸 FTS 문법(AND, OR, *, - 등)을 일반 문자로 취급한다.
    return '"' + term.replace('"', '""') + '"'


def _like_pattern(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def search_articles(database_path: str, query: ArticleQuery) -> tuple[int, list[dict]]:
    terms = split_terms(query.q)
    fts_terms = [term for term in terms if len(term) >= 3]
    like_terms = [term for term in terms if len(term) < 3]

    joins = ["JOIN blogs b ON b.id = a.blog_id"]
    clauses = ["b.active = 1"]
    values: list[object] = []

    if fts_terms:
        joins.append(
            """JOIN (
                SELECT rowid, bm25(articles_fts, 10.0, 3.0, 1.0, 2.0) AS rank
                FROM articles_fts WHERE articles_fts MATCH ?
            ) f ON f.rowid = a.id"""
        )
        values.append(" AND ".join(_fts_phrase(term) for term in fts_terms))

    for term in like_terms:
        clauses.append(
            "(a.title LIKE ? ESCAPE '\\' OR a.summary LIKE ? ESCAPE '\\'"
            " OR a.content LIKE ? ESCAPE '\\' OR a.author LIKE ? ESCAPE '\\')"
        )
        values.extend([_like_pattern(term)] * 4)
    if query.blog_id is not None:
        clauses.append("a.blog_id = ?")
        values.append(query.blog_id)
    if query.company:
        clauses.append("b.company = ?")
        values.append(query.company)
    if query.date_from:
        clauses.append("date(a.published_at) >= date(?)")
        values.append(query.date_from)
    if query.date_to:
        clauses.append("date(a.published_at) <= date(?)")
        values.append(query.date_to)

    latest = "COALESCE(a.published_at, a.fetched_at) DESC, a.id DESC"
    order = f"f.rank, {latest}" if query.sort == "relevance" and fts_terms else latest
    source = f"articles a {' '.join(joins)} WHERE {' AND '.join(clauses)}"

    with connect(database_path) as db:
        total = db.execute(f"SELECT COUNT(*) FROM {source}", values).fetchone()[0]
        rows = db.execute(
            f"SELECT {LIST_COLUMNS} FROM {source} ORDER BY {order} LIMIT ? OFFSET ?",
            [*values, query.limit, query.offset],
        ).fetchall()
    return total, [dict(row) for row in rows]
