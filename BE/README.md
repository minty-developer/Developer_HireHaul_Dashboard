# Tech Blog Aggregator Backend

FastAPI와 SQLite 기반 기술 블로그 서비스의 백엔드(API·검색·DB)입니다.

서버를 실행한 뒤 `http://127.0.0.1:5000/api/docs`에서 Swagger UI로 모든 API를 바로 호출해 볼 수 있습니다.

## 담당 범위

| 담당 | 범위 | 이 폴더에 있는가 |
| --- | --- | --- |
| 2번 백엔드 | FastAPI, API, 검색, DB 구조·연결(수집 결과 가져오기 포함), 회원, 키워드 구독 API | 있음 |
| 3번 RSS 수집 | RSS 자동 수집, 파싱, 중복 제거, JSON 저장 | 없음 (`rss-collector/`, 3번이 작성) |
| 4번 알림·배포 | Discord 알림 발송, 스케줄링, Docker | 없음 (4번이 작성) |

## 데이터 구조

- `blogs`: 블로그·회사·RSS 주소, 활성 상태, 수집 상태 컬럼(`etag`, `last_modified`, `last_checked_at`, `last_success_at`, `last_error`)
- `articles`: 블로그별 글 식별자(`entry_key`), 제목, 원문 주소, 작성자, 요약·본문, 게시·수집 시각
- `articles_fts`: 제목·요약·본문·작성자 전문 검색 색인(FTS5 trigram). `articles`에 넣거나 고치면 트리거가 자동으로 맞춰 줌
- `users`, `auth_tokens`, `auth_action_tokens`, `login_attempts`: 회원·로그인
- `subscriptions`: 사용자별 키워드 구독과 Discord 웹훅 주소

테이블은 서버를 띄우거나 `python -m app.cli`를 실행할 때 `app/db.py`의 마이그레이션으로 만들어집니다.

## RSS 수집 결과를 DB에 넣기 (3번 → 2번)

3번의 수집기(`rss-collector/`)는 결과를 JSON 파일로 저장하고, 백엔드가 그 파일을 DB로 가져옵니다.

```powershell
.venv\Scripts\python.exe -m app.cli import-rss ..\rss-collector\blogs.json ..\rss-collector\posts.json
```

- **블로그:** `blogs.json`의 `rss_url`을 기준으로 등록·갱신합니다. `enabled: false`이면 비활성으로 들어가 목록과 검색에서 빠집니다.
- **글:** `posts.json`의 `link`를 중복 기준으로 씁니다. 여러 번 실행해도 같은 글이 두 번 들어가지 않고, 이미 있는 글은 제목·날짜가 갱신됩니다.
- **날짜:** ISO 8601이든 RSS 형식(`Wed, 30 Sep 2026 12:00:11 GMT`)이든 `2026-09-30T12:00:11+00:00` 형식의 UTC로 바꿔 저장합니다.
- **검색 색인:** 트리거가 자동으로 맞춥니다.

`app/rss_import.py`가 읽는 필드는 아래와 같습니다. `?`는 있으면 쓰는 선택 필드입니다.

| 파일 | 필드 | 들어가는 곳 |
| --- | --- | --- |
| `blogs.json` | `name`, `rss_url`, `enabled?` | `blogs.name`, `feed_url`, `active` |
| `blogs.json` | `company?`, `site_url?` | 없으면 각각 블로그 이름, RSS 주소의 도메인 |
| `posts.json` | `title`, `link`, `published`, `blog` | `articles.title`, `url`·`entry_key`, `published_at`, 블로그 연결 |
| `posts.json` | `summary?`, `content?`, `author?` | 검색 대상. 비어 있으면 제목만 검색됨 |

`posts.json`의 `blog` 값은 `blogs.json`의 `name`과 같아야 합니다. 다르면 그 글은 건너뛰고 블로그 이름을 출력합니다.

## 4번(알림·배포)과 맞물리는 지점

- **구독 정보:** `subscriptions`에서 `active = 1`이고 `discord_webhook_url`이 있는 행이 알림 대상입니다. `keyword`는 대소문자를 구분하지 않습니다.
- **알림 시점:** 4번의 스케줄러가 "3번 수집기 실행 → `import-rss` 실행 → 새 글 알림" 순서로 묶으면 됩니다. 새 글은 `articles.id`나 `created_at`이 지난번보다 큰 행으로 찾을 수 있습니다.
- **발송 기록 테이블:** 4번이 `app/db.py`의 `MIGRATIONS`에 9번부터 추가합니다. 4·6·7번은 삭제된 예전 마이그레이션이 쓰던 번호라 쓰지 않습니다.
  - 예전 코드로 만든 로컬 DB에는 `webhook_deliveries`, `discord_*` 테이블이 남아 있을 수 있으니, 다른 이름을 쓰거나 로컬 DB를 새로 만드세요.
- **서버 실행(Docker용):**
  - 실행 명령은 `uvicorn run:app --host 0.0.0.0 --port 5000`입니다.
  - 상태 확인은 `GET /api/health`로 합니다.
  - DB 백업은 `python -m app.cli backup-db`로 합니다.
  - 지금 Render 배포는 임시 `BE/Dockerfile`로 돌고 있습니다. 빌드 컨텍스트는 저장소 루트이고, 서버가 켜질 때 `import-rss`를 먼저 실행합니다. 4번이 자기 Docker·배포 설정을 만들면 바꿔도 됩니다.

## 환경변수

- `APP_ENV`: `development`, `testing`, `production`
- `SECRET_KEY`: 애플리케이션 비밀키. 운영 환경에서는 안전한 무작위 값 필수
- `DATABASE_PATH`: SQLite 데이터베이스 경로
- `ADMIN_API_KEY`: 관리자 API의 `X-API-Key` 값
- `CORS_ORIGINS`: 허용할 프론트엔드 Origin. 여러 개면 쉼표로 구분
- `BACKUP_DIRECTORY`, `BACKUP_RETENTION_DAYS`: DB 백업 위치와 보관 일수
- 이메일 발송: `PUBLIC_BASE_URL`, `MAIL_FROM`, `SMTP_*`, `REQUIRE_EMAIL_VERIFICATION`

## API

- `GET /`: 서비스 안내
- `GET /api/health`: 서버 및 데이터베이스 상태
- `GET /api/docs`: Swagger UI (Authorize 버튼으로 Bearer 토큰·관리자 키 입력)
- `GET /api/redoc`: ReDoc 문서
- `GET /api/openapi.json`: OpenAPI 3.1 명세 (FastAPI가 자동 생성)
- `GET /api/articles`: 게시글 목록 및 검색
- `GET /api/articles/{article_id}`: 게시글 상세 조회
- `GET /api/blogs`: 활성 기술 블로그 목록
- `GET /api/blogs/{blog_id}`: 기술 블로그 상세 조회
- `POST /api/auth/register`: 회원가입
- `POST /api/auth/login`: 로그인 및 Bearer 토큰 발급
- `GET /api/auth/me`: 로그인 사용자 조회
- `PATCH /api/auth/me`: 표시 이름 수정
- `PUT /api/auth/password`: 비밀번호 변경 및 기존 토큰 폐기
- `DELETE /api/auth/me`: 회원 탈퇴
- `POST /api/auth/logout`: 현재 토큰 폐기
- `POST /api/auth/email/verification/request`: 이메일 인증 메일 재요청
- `POST /api/auth/email/verification/confirm`: 이메일 인증 확정
- `POST /api/auth/password/reset/request`: 비밀번호 재설정 메일 요청
- `POST /api/auth/password/reset/confirm`: 비밀번호 재설정 확정
- `GET /api/subscriptions`: 내 키워드 구독 목록
- `POST /api/subscriptions`: 키워드 구독 추가
- `PATCH /api/subscriptions/{subscription_id}`: Discord 웹훅 주소 및 활성 상태 변경
- `DELETE /api/subscriptions/{subscription_id}`: 키워드 구독 삭제
- `GET /api/admin/blogs`: 전체 블로그 관리 목록
- `POST /api/admin/blogs`: 블로그 등록
- `PATCH /api/admin/blogs/{blog_id}`: 블로그 수정·재활성화
- `DELETE /api/admin/blogs/{blog_id}`: 블로그 비활성화
- `GET /api/admin/status`: DB·수집 상태

## 검색

`GET /api/articles` 쿼리 파라미터:

| 파라미터 | 설명 |
| --- | --- |
| `q` | 검색어(최대 200자). 공백으로 나눈 **모든 단어**가 제목·요약·본문·작성자 중 하나에 포함된 글 |
| `blog_id` | 블로그 ID |
| `company` | 회사명(정확히 일치, 예: `카카오`) |
| `from`, `to` | 게시일 범위 `YYYY-MM-DD` |
| `sort` | `latest`(기본, 최신순) 또는 `relevance`(검색 관련도순) |
| `limit`, `offset` | 페이지네이션 (`limit` 1~100, 기본 20) |

- 3글자 이상 단어는 FTS5 trigram 색인으로 찾아서, 한국어 부분 문자열도 빠르게 검색합니다.
- trigram은 3글자 미만을 색인할 수 없어서, `AI`, `검색` 같은 1~2글자 단어는 LIKE로 찾습니다.
- 관련도는 bm25 점수이고, 가중치는 제목 > 요약 > 작성자 > 본문 순입니다.
- `%`, `_`, `"`, `AND` 같은 문자는 검색 문법이 아닌 일반 글자로 처리합니다.

검증 실패는 `400 {"ok": false, "error": "<안내 메시지>"}` 형식으로 응답합니다.

## 키워드 구독

- 구독을 만들 때 `discord_webhook_url`을 함께 보낼 수 있습니다. Discord 웹훅 주소 형식만 허용합니다.
  - 실제 알림 발송은 4번 담당 기능입니다.
- 웹훅을 추가하거나 바꿀 때는 `PATCH` 본문에 `discord_webhook_url`을 보냅니다. `null`을 보내면 알림이 꺼집니다.
- 구독을 일시정지하거나 다시 켤 때는 `active: false` 또는 `active: true`를 보냅니다. 두 필드는 한 요청에서 함께 바꿀 수 있습니다.

## 실행과 테스트

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe run.py   # 개발 모드에서는 코드 변경 시 자동 재시작
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 운영 명령

```powershell
.venv\Scripts\python.exe -m app.cli prune-auth-tokens
.venv\Scripts\python.exe -m app.cli prune-login-attempts
.venv\Scripts\python.exe -m app.cli backup-db
.venv\Scripts\python.exe -m app.cli restore-db data\backups\tech_blog_YYYYMMDDTHHMMSSZ.db --yes
```

복원할 때는 API 서버를 먼저 멈춰야 합니다.

이메일 인증과 비밀번호 재설정 메일을 실제로 보내려면 `SMTP_HOST`, `SMTP_PORT`, `MAIL_FROM`을 설정합니다. 이메일 인증을 로그인 필수 조건으로 만들려면 `REQUIRE_EMAIL_VERIFICATION=true`를 씁니다.
