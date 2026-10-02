# HireHaul Backend

Flask와 SQLite로 구성된 HireHaul API 서버입니다. 현재는 외부 채용 API 대신 샘플 Provider를 사용합니다.

## 로컬 실행

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:APP_ENV = "development"
$env:SECRET_KEY = "local-development-key"
python run.py
```

`run.py`는 로컬 개발용입니다. 운영 환경에서는 `gunicorn run:app`을 사용하고 `APP_ENV=production`으로 설정합니다.

## 환경변수

- `APP_ENV`: `development`, `testing`, `production`
- `SECRET_KEY`: Flask 비밀 키. 운영 환경에서 안전한 무작위 값 필수
- `DATABASE_PATH`: SQLite DB 경로
- `DEFAULT_KEYWORDS`: 기본 검색어
- `SYNC_API_KEY`: `/api/sync` 요청의 `X-API-Key` 값. 운영 환경에서 필수
- `CORS_ORIGINS`: 허용할 프론트엔드 Origin. 여러 개면 쉼표로 구분

## API

- `GET /api/health`: 서버와 DB 상태
- `GET /api/jobs`: `q`, `location`, `source`, `limit`, `offset` 지원
- `GET /api/stats`: 활성 공고 통계
- `POST /api/sync`: 공고 동기화. `SYNC_API_KEY` 설정 시 `X-API-Key` 헤더 필수

## 테스트

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`.env.example`은 필요한 값의 예시이며 자동으로 로드되지 않습니다. 실행 환경이나 배포 서비스에 환경변수를 설정하세요.

DB, WAL 파일, 로그, `.env`, 가상환경은 Git에 포함되지 않습니다.
