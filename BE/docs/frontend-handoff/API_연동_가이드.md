# 기술블로그 수집기 — 프론트엔드 API 연동 가이드

작성일: 2026-11-06 · 백엔드: FastAPI

같은 폴더의 `openapi.json`은 전체 API 명세입니다. Postman이나 Insomnia에서 Import하면 모든 요청이 자동으로 만들어집니다.

## 1. 접속 정보

| 항목 | 값 |
| --- | --- |
| 서버 주소 (로컬) | `http://127.0.0.1:5000` |
| API 문서 (Swagger) | `http://127.0.0.1:5000/api/docs` |
| OpenAPI 명세 | `http://127.0.0.1:5000/api/openapi.json` |
| 허용된 프론트 주소 (CORS) | `http://localhost:3000` (다른 주소면 백엔드에 요청) |

- Swagger에서 모든 API를 직접 호출해 볼 수 있습니다.
- 토큰이 필요한 API는 오른쪽 위 **Authorize** 버튼에 토큰을 넣고 호출하면 됩니다.

## 2. 공통 규칙

- 요청과 응답은 모두 JSON입니다. 요청할 때 `Content-Type: application/json`을 붙여 주세요.
- **로그인 인증:** `Authorization: Bearer <token>` 헤더를 붙입니다.
- **에러 응답:** `{"error": "한국어 안내 메시지"}` 형식입니다.
  - 일부 API는 `"ok": false`도 같이 옵니다.
  - 화면에는 `error` 값을 그대로 보여주면 됩니다.
- **입력값 검증 실패:** **400**이 옵니다. Swagger 문서에는 422로 적혀 있지만 실제 응답은 400입니다.

| 상태 코드 | 의미 |
| --- | --- |
| 200 / 201 | 성공 / 생성됨 |
| 202 | 접수됨 (메일 발송 요청) |
| 204 | 성공, 응답 본문 없음 (`response.json()` 호출하지 말 것) |
| 400 | 입력값 오류 |
| 401 | 토큰 없음, 만료, 또는 비밀번호 틀림 |
| 403 | 이메일 인증 필요 |
| 404 | 없는 데이터 |
| 409 | 중복 (이미 가입된 이메일, 이미 구독 중인 키워드) |
| 429 | 로그인 시도 초과. `Retry-After` 헤더에 기다릴 초가 들어 있음 |

## 3. 로그인 흐름

1. **회원가입:** `POST /api/auth/register` 에 `{email, password, display_name}`
   - 비밀번호는 8~128자, 표시 이름은 1~50자입니다.
2. **로그인:** `POST /api/auth/login` 에 `{email, password}`
   - 응답은 `{token, expires_at, user}`입니다.
   - 토큰은 7일 동안 유효합니다.
3. 받은 토큰은 저장해 두고 이후 요청마다 `Authorization` 헤더에 붙입니다.
4. **401이 오면** 토큰이 만료된 것이니 저장한 토큰을 지우고 로그인 화면으로 보내 주세요.
5. **로그아웃:** `POST /api/auth/logout` (토큰 필요, 204 응답)
6. **비밀번호 변경:** 변경하면 기존 토큰이 전부 폐기되므로 다시 로그인해야 합니다.

## 4. 프론트에서 만들어야 하는 페이지 2개

메일에 들어가는 링크가 아래 프론트 주소로 연결됩니다.

| 페이지 주소 | 할 일 | 성공 응답 |
| --- | --- | --- |
| `/verify-email?token=...` | `POST /api/auth/email/verification/confirm` 에 `{token}` | 204 |
| `/reset-password?token=...` | 새 비밀번호를 입력받아 `POST /api/auth/password/reset/confirm` 에 `{token, new_password}` | 204 |

## 5. API 목록 (🔒 = 토큰 필요)

| 화면 | 메서드 | 주소 | 요청 본문 |
| --- | --- | --- | --- |
| 게시글 목록·검색 | GET | `/api/articles` | 6번 참고 |
| 게시글 상세 | GET | `/api/articles/{id}` | |
| 블로그 목록 (필터용) | GET | `/api/blogs` | |
| 블로그 상세 | GET | `/api/blogs/{id}` | |
| 회원가입 | POST | `/api/auth/register` | `{email, password, display_name}` |
| 로그인 | POST | `/api/auth/login` | `{email, password}` |
| 내 정보 🔒 | GET | `/api/auth/me` | |
| 이름 수정 🔒 | PATCH | `/api/auth/me` | `{display_name}` |
| 비밀번호 변경 🔒 | PUT | `/api/auth/password` | `{current_password, new_password}` |
| 회원 탈퇴 🔒 | DELETE | `/api/auth/me` | `{password}` |
| 로그아웃 🔒 | POST | `/api/auth/logout` | |
| 인증 메일 재요청 | POST | `/api/auth/email/verification/request` | `{email}` |
| 비밀번호 찾기 | POST | `/api/auth/password/reset/request` | `{email}` |
| 내 구독 목록 🔒 | GET | `/api/subscriptions` | |
| 구독 추가 🔒 | POST | `/api/subscriptions` | `{keyword, discord_webhook_url?}` |
| 구독 수정 🔒 | PATCH | `/api/subscriptions/{id}` | `{discord_webhook_url?, active?}` |
| 구독 삭제 🔒 | DELETE | `/api/subscriptions/{id}` | |

## 6. 게시글 검색 — `GET /api/articles`

| 파라미터 | 설명 | 기본값 |
| --- | --- | --- |
| `q` | 검색어 (최대 200자). 띄어쓰기로 나눈 단어가 **모두** 들어간 글을 찾습니다 | 없음 |
| `blog_id` | 블로그 ID | 없음 |
| `company` | 회사명. 정확히 일치해야 합니다 (예: `카카오`, `네이버`) | 없음 |
| `from`, `to` | 게시일 범위 `YYYY-MM-DD` | 없음 |
| `sort` | `latest`(최신순) 또는 `relevance`(관련도순) | `latest` |
| `limit` | 한 번에 가져올 개수 (1~100) | 20 |
| `offset` | 건너뛸 개수 | 0 |

- **검색할 때:** 검색어가 있을 때는 `sort=relevance`를 쓰는 걸 추천합니다.
- **페이지 계산:** 응답의 `total`로 전체 페이지 수를 계산하고, 다음 페이지는 `offset = page * limit`로 요청합니다.

응답 예시:

```json
{
  "count": 20,
  "total": 48,
  "limit": 20,
  "offset": 0,
  "articles": [
    {
      "id": 12,
      "blog_id": 2,
      "title": "글 제목",
      "url": "https://원문주소",
      "author": "작성자",
      "summary": "요약(HTML 태그 제거된 텍스트)",
      "published_at": "2026-10-05T01:00:00+00:00",
      "fetched_at": "2026-10-06T01:00:00+00:00",
      "blog_name": "NAVER D2",
      "company": "네이버",
      "entry_key": "...",
      "feed_updated_at": null
    }
  ]
}
```

- **상세 응답:** `GET /api/articles/{id}`는 `{"article": {...}}` 형식입니다. 목록 필드에 `content`(본문 텍스트)와 `blog_site_url`이 추가됩니다.
- **원문 이동:** 원문 링크는 `url`입니다. 본문 전체가 아니라 요약만 있는 피드도 많아서, "원문 보기" 버튼으로 `url`을 열어 주세요.
- **날짜:** 날짜는 UTC 기준 ISO 형식이라 화면에서 한국 시간으로 바꿔서 보여주세요.
  - `published_at`이 `null`일 수 있습니다. 그때는 `fetched_at`을 대신 보여주면 됩니다.

## 7. 블로그 목록 — `GET /api/blogs`

- **응답:** `{"count": 3, "blogs": [...]}` 형식입니다.
- **블로그 필드:** `id`, `name`, `company`, `site_url`, `feed_url`, `description`, `article_count`, `last_success_at`
- **용도:** 블로그·회사 필터 드롭다운을 만들 때 쓰면 됩니다.

## 8. 키워드 구독

- **구독 필드:** `id`, `keyword`, `discord_webhook_url`, `active`, `created_at`, `updated_at`
  - `active`는 응답에서 `1` 또는 `0`으로 옵니다.
- **구독 추가:** `{"keyword": "쿠버네티스", "discord_webhook_url": "https://discord.com/api/webhooks/..."}`
  - 웹훅 주소는 넣지 않아도 됩니다.
  - 넣으면 새 글이 올라왔을 때 Discord로 알림이 갑니다.
- **수정:** `PATCH`는 보낸 필드만 바뀝니다.

| 하고 싶은 것 | 요청 본문 |
| --- | --- |
| 일시정지 | `{"active": false}` |
| 다시 켜기 | `{"active": true}` |
| Discord 알림 끄기 | `{"discord_webhook_url": null}` |

- **`active` 값:** 요청할 때는 반드시 `true`/`false`로 보내야 합니다. `1`/`0`으로 보내면 400입니다.
- **중복 키워드:** 같은 키워드는 대소문자가 달라도 중복으로 처리되어 409가 옵니다.
