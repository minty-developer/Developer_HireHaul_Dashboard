# Tech Blog Aggregator Backend

Flask와 SQLite 기반의 기술 블로그 RSS 수집 서비스 백엔드입니다.

RSS 수집·검색, 사용자 키워드 구독, Discord 알림, 운영 스케줄러와 Docker 배포 구성을 제공합니다.

## 데이터 구조

- `blogs`: 블로그·회사·RSS 주소와 활성 상태, 조건부 요청용 ETag, 최근 수집 상태
- `articles`: 블로그별 RSS 항목 식별자, 제목, 원문 주소, 작성자, 요약·본문, 게시·수집 시각

게시글은 `blog_id + entry_key` 조합으로 중복 저장을 막습니다. RSS의 GUID를 `entry_key`로 사용하고, GUID가 없다면 원문 URL을 사용합니다.

## 환경변수

- `APP_ENV`: `development`, `testing`, `production`
- `SECRET_KEY`: Flask 비밀키. 운영 환경에서는 안전한 무작위 값 필수
- `DATABASE_PATH`: SQLite 데이터베이스 경로
- `ADMIN_API_KEY`: 관리자 수집 API의 `X-API-Key` 값
- `CORS_ORIGINS`: 허용할 프론트엔드 Origin. 여러 개면 쉼표로 구분

## API

- `GET /`: 서비스 안내
- `GET /api/health`: 서버 및 데이터베이스 상태
- `GET /api/openapi.json`: OpenAPI 3.1 명세
- `POST /api/discord/interactions`: Discord Slash Command 수신
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
- `DELETE /api/subscriptions/{subscription_id}`: 키워드 구독 삭제
- `POST /api/admin/sync`: 활성 블로그 전체 수집
- `POST /api/admin/sync/{blog_id}`: 특정 블로그 수집
- `GET /api/admin/blogs`: 전체 블로그 관리 목록
- `POST /api/admin/blogs`: 블로그 등록
- `PATCH /api/admin/blogs/{blog_id}`: 블로그 수정·재활성화
- `DELETE /api/admin/blogs/{blog_id}`: 블로그 비활성화
- `GET /api/admin/status`: DB·수집 운영 상태

게시글 목록은 `q`, `blog_id`, `from`, `to`, `limit`, `offset` 쿼리를 지원합니다. 날짜는 `YYYY-MM-DD` 형식입니다.
키워드 구독 생성 시 선택적으로 `discord_webhook_url`을 전달하면, 새로 수집된 글의
제목·요약·본문에 키워드가 포함될 때 Discord로 한 번만 알림을 보냅니다. 일시적인
발송 실패는 이후 수집 주기에 최대 3회까지 자동 재시도합니다.

## 테스트

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 기본 기술 블로그 등록

```powershell
$env:FLASK_APP = "run.py"
.venv\Scripts\python.exe -m flask seed-blogs
```

카카오 Tech, NAVER D2, LY Corporation 한국어 기술 블로그를 중복 없이 등록합니다.

## RSS 수집 실행

모든 관리자 수집 요청에는 `X-API-Key` 헤더가 필요합니다.

```powershell
$env:ADMIN_API_KEY = "local-admin-key"
python run.py
```

다른 터미널에서 전체 또는 특정 블로그를 수집할 수 있습니다.

```powershell
curl.exe -X POST -H "X-API-Key: local-admin-key" http://127.0.0.1:5000/api/admin/sync
curl.exe -X POST -H "X-API-Key: local-admin-key" http://127.0.0.1:5000/api/admin/sync/1
```

전체 수집은 한 블로그가 실패해도 나머지 블로그를 계속 처리합니다. 피드 서버가 ETag 또는 Last-Modified를 제공하면 다음 수집부터 조건부 요청에 사용합니다.

작업 스케줄러나 cron에서는 HTTP 요청 대신 CLI를 사용할 수 있습니다.

```powershell
$env:FLASK_APP = "run.py"
.venv\Scripts\python.exe -m flask collect-feeds
.venv\Scripts\python.exe -m flask prune-auth-tokens
.venv\Scripts\python.exe -m flask prune-login-attempts
.venv\Scripts\python.exe -m flask backup-db
.venv\Scripts\python.exe -m flask restore-db data\backups\tech_blog_YYYYMMDDTHHMMSSZ.db --yes
.venv\Scripts\python.exe -m flask run-scheduler
```

`run-scheduler`는 설정된 간격으로 RSS를 수집하고 하루 한 번 DB 백업을 생성합니다.
복원할 때는 API와 스케줄러를 먼저 중지해야 합니다. Docker Compose에서는 `scheduler`
서비스가 자동 수집을 담당하며 백업은 SQLite 데이터 볼륨의 `backups` 폴더에 저장됩니다.

이메일 인증과 비밀번호 재설정을 실제 발송하려면 `SMTP_HOST`, `SMTP_PORT`,
`MAIL_FROM`을 설정합니다. 인증을 로그인 필수 조건으로 만들려면
`REQUIRE_EMAIL_VERIFICATION=true`를 사용합니다.

## Discord 봇

Discord Developer Portal에서 애플리케이션을 만든 뒤 `.env`에 다음 값을 설정합니다.

```env
DISCORD_APPLICATION_ID=애플리케이션_ID
DISCORD_PUBLIC_KEY=공개키
DISCORD_BOT_TOKEN=봇_토큰
DISCORD_TEST_GUILD_ID=개발용_서버_ID
```

개발 서버 명령은 즉시 반영되며, `DISCORD_TEST_GUILD_ID`를 비우면 전역 명령으로
등록됩니다.

```powershell
.venv\Scripts\python.exe -m flask register-discord-commands
```

Interaction Endpoint URL에는 공개 HTTPS 주소의
`/api/discord/interactions`를 등록합니다. 봇은 `/알림채널`, `/구독추가`,
`/구독목록`, `/구독삭제`, `/최신글`, `/검색` 명령을 제공합니다. 새 게시글이
Discord 구독 키워드와 일치하면 설정된 채널로 한 번만 전송합니다.

## Docker 실행

저장소 루트에서 다음 명령을 실행합니다.

```powershell
docker compose up --build -d
docker compose exec backend python -m flask seed-blogs
docker compose exec backend python -m flask collect-feeds
```

API는 기본적으로 `http://127.0.0.1:5000`에서 열립니다. SQLite 데이터는
`backend_data` 볼륨에 보존됩니다. 운영 환경에서는 `APP_ENV=production`과 함께
안전한 `SECRET_KEY`, `ADMIN_API_KEY`, 실제 `CORS_ORIGINS`를 반드시 설정해야 합니다.
