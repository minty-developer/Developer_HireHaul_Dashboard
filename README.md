# Tech Blog Aggregator

국내 IT 기업 기술 블로그의 RSS/Atom 피드를 주기적으로 수집하고 검색·구독할 수 있게 제공하는 서비스입니다.

현재 저장소에는 새 서비스 구현을 위한 Flask 백엔드 기반이 구성되어 있습니다.

## 목표 기능

- 기술 블로그 RSS/Atom 주기적 수집
- 게시글 검색 및 블로그별 조회
- 회원가입과 로그인
- 사용자별 키워드 구독
- Discord 웹훅 알림
- Docker 기반 실행 및 배포

## 현재 제공 기능

- `GET /`: 서비스 안내
- `GET /api/health`: 애플리케이션과 SQLite 연결 상태 확인

## 백엔드 실행

```powershell
cd BE
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

기본 주소는 `http://127.0.0.1:5000`입니다.

## 테스트

```powershell
cd BE
python -m unittest discover -s tests -v
```
