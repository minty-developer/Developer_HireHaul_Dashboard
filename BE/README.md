# Tech Blog Aggregator Backend

Flask와 SQLite 기반의 기술 블로그 RSS 수집 서비스 백엔드입니다.

현재는 애플리케이션 초기화, RSS 블로그·게시글 데이터 구조, CORS, 헬스체크를 제공합니다. RSS 네트워크 수집과 사용자 기능은 이후 단계에서 추가합니다.

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
- `GET /api/subscriptions`: 내 키워드 구독 목록
- `POST /api/subscriptions`: 키워드 구독 추가
- `DELETE /api/subscriptions/{subscription_id}`: 키워드 구독 삭제
- `POST /api/admin/sync`: 활성 블로그 전체 수집
- `POST /api/admin/sync/{blog_id}`: 특정 블로그 수집
- `GET /api/admin/blogs`: 전체 블로그 관리 목록
- `POST /api/admin/blogs`: 블로그 등록
- `PATCH /api/admin/blogs/{blog_id}`: 블로그 수정·재활성화
- `DELETE /api/admin/blogs/{blog_id}`: 블로그 비활성화

게시글 목록은 `q`, `blog_id`, `from`, `to`, `limit`, `offset` 쿼리를 지원합니다. 날짜는 `YYYY-MM-DD` 형식입니다.

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
```

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
