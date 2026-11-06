"""요청/응답 Pydantic 모델.

검증 실패 메시지는 ValueError로 던지면 errors.py의 핸들러가
`{"ok": false, "error": "<메시지>"}` 형태의 400 응답으로 바꾼다.
"""
from __future__ import annotations

from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, StrictBool, field_validator

from .discord_webhook import valid_discord_webhook_url


def _password(value: str, label: str = "비밀번호") -> str:
    if not 8 <= len(value) <= 128:
        raise ValueError(f"{label}는 8~128자여야 합니다.")
    return value


def _display_name(value: str) -> str:
    value = value.strip()
    if not 1 <= len(value) <= 50:
        raise ValueError("표시 이름은 1~50자여야 합니다.")
    return value


def _webhook_url(value: str | None) -> str | None:
    value = value.strip() if value else None
    if value and not valid_discord_webhook_url(value):
        raise ValueError("유효한 Discord 웹훅 URL이 아닙니다.")
    return value


def _http_url(value: str, field: str) -> str:
    value = value.strip()
    parsed = urlparse(value)
    if len(value) > 2048 or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"올바른 {field}을 입력해주세요.")
    return value


# ---------- 인증 ----------

class RegisterRequest(BaseModel):
    email: str = ""
    password: str = ""
    display_name: str = ""

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        value = value.strip()
        if "@" not in value or len(value) > 254:
            raise ValueError("올바른 이메일을 입력해주세요.")
        return value

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return _password(value)

    @field_validator("display_name")
    @classmethod
    def check_display_name(cls, value: str) -> str:
        return _display_name(value)


class LoginRequest(BaseModel):
    email: str = ""
    password: str = ""


class DisplayNameRequest(BaseModel):
    display_name: str = ""

    @field_validator("display_name")
    @classmethod
    def check_display_name(cls, value: str) -> str:
        return _display_name(value)


class PasswordChangeRequest(BaseModel):
    current_password: str = ""
    new_password: str = ""

    @field_validator("new_password")
    @classmethod
    def check_new_password(cls, value: str) -> str:
        return _password(value, "새 비밀번호")


class PasswordRequest(BaseModel):
    password: str = ""


class EmailRequest(BaseModel):
    email: str = ""


class TokenRequest(BaseModel):
    token: str = ""


class PasswordResetConfirmRequest(BaseModel):
    token: str = ""
    new_password: str = ""

    @field_validator("new_password")
    @classmethod
    def check_new_password(cls, value: str) -> str:
        return _password(value, "새 비밀번호")


# ---------- 키워드 구독 ----------

class SubscriptionCreateRequest(BaseModel):
    keyword: str = ""
    discord_webhook_url: str | None = None

    @field_validator("keyword")
    @classmethod
    def check_keyword(cls, value: str) -> str:
        value = " ".join(value.split())
        if not 1 <= len(value) <= 100:
            raise ValueError("키워드는 1~100자여야 합니다.")
        return value

    @field_validator("discord_webhook_url")
    @classmethod
    def check_webhook_url(cls, value: str | None) -> str | None:
        return _webhook_url(value)


class SubscriptionUpdateRequest(BaseModel):
    """보낸 필드만 변경한다. discord_webhook_url에 null을 보내면 알림이 꺼진다."""

    discord_webhook_url: str | None = None
    active: StrictBool | None = None

    @field_validator("discord_webhook_url")
    @classmethod
    def check_webhook_url(cls, value: str | None) -> str | None:
        return _webhook_url(value)


# ---------- 관리자 블로그 ----------

class _BlogFields(BaseModel):
    @field_validator("name", "company", check_fields=False)
    @classmethod
    def check_label(cls, value: str | None, info) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not 1 <= len(value) <= 100:
            raise ValueError(f"{info.field_name}은 1~100자여야 합니다.")
        return value

    @field_validator("feed_url", "site_url", check_fields=False)
    @classmethod
    def check_url(cls, value: str | None, info) -> str | None:
        return None if value is None else _http_url(value, info.field_name)

    @field_validator("description", check_fields=False)
    @classmethod
    def check_description(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if len(value) > 1000:
            raise ValueError("description은 1000자 이하여야 합니다.")
        return value


class BlogCreateRequest(_BlogFields):
    name: str
    company: str
    feed_url: str
    site_url: str
    description: str = ""
    active: StrictBool = True


class BlogUpdateRequest(_BlogFields):
    name: str | None = None
    company: str | None = None
    feed_url: str | None = None
    site_url: str | None = None
    description: str | None = None
    active: StrictBool | None = None


# ---------- 응답 ----------

class ArticleSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    blog_id: int
    entry_key: str
    title: str
    url: str
    author: str
    summary: str
    published_at: str | None
    feed_updated_at: str | None
    fetched_at: str
    blog_name: str
    company: str


class ArticleDetail(ArticleSummary):
    content: str
    created_at: str
    updated_at: str
    blog_site_url: str


class ArticleListResponse(BaseModel):
    count: int
    total: int
    limit: int
    offset: int
    articles: list[ArticleSummary]


class ArticleDetailResponse(BaseModel):
    article: ArticleDetail


class BlogSummary(BaseModel):
    id: int
    name: str
    company: str
    feed_url: str
    site_url: str
    description: str
    last_checked_at: str | None
    last_success_at: str | None
    article_count: int


class BlogListResponse(BaseModel):
    count: int
    blogs: list[BlogSummary]


class BlogDetailResponse(BaseModel):
    blog: BlogSummary
