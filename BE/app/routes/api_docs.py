from flask import jsonify

from . import bp


ENDPOINTS = {
    "/api/health": {"get": "서버와 데이터베이스 상태 확인"},
    "/api/articles": {"get": "게시글 검색 및 목록 조회"},
    "/api/articles/{article_id}": {"get": "게시글 상세 조회"},
    "/api/blogs": {"get": "활성 기술 블로그 목록"},
    "/api/blogs/{blog_id}": {"get": "기술 블로그 상세 조회"},
    "/api/auth/register": {"post": "회원가입"},
    "/api/auth/login": {"post": "로그인"},
    "/api/auth/logout": {"post": "로그아웃"},
    "/api/auth/me": {
        "get": "현재 사용자 조회",
        "patch": "표시 이름 수정",
        "delete": "회원 탈퇴",
    },
    "/api/auth/password": {"put": "비밀번호 변경"},
    "/api/auth/email/verification/request": {"post": "이메일 인증 요청"},
    "/api/auth/email/verification/confirm": {"post": "이메일 인증 확정"},
    "/api/auth/password/reset/request": {"post": "비밀번호 재설정 요청"},
    "/api/auth/password/reset/confirm": {"post": "비밀번호 재설정 확정"},
    "/api/subscriptions": {"get": "키워드 구독 목록", "post": "키워드 구독 추가"},
    "/api/subscriptions/{subscription_id}": {"delete": "키워드 구독 삭제"},
    "/api/admin/blogs": {"get": "블로그 관리 목록", "post": "블로그 등록"},
    "/api/admin/blogs/{blog_id}": {
        "patch": "블로그 수정",
        "delete": "블로그 비활성화",
    },
    "/api/admin/sync": {"post": "전체 피드 수집"},
    "/api/admin/sync/{blog_id}": {"post": "개별 피드 수집"},
    "/api/admin/status": {"get": "운영 상태 조회"},
}


@bp.get("/api/openapi.json")
def openapi_spec():
    paths = {
        path: {
            method: {
                "summary": summary,
                "responses": {"200": {"description": "성공"}},
            }
            for method, summary in operations.items()
        }
        for path, operations in ENDPOINTS.items()
    }
    return jsonify({
        "openapi": "3.1.0",
        "info": {"title": "Tech Blog Aggregator API", "version": "1.0.0"},
        "paths": paths,
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer"},
                "adminApiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
            }
        },
    })
