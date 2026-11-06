# Tech Blog Aggregator

국내 IT 기업 기술 블로그의 RSS/Atom 피드를 주기적으로 수집하고 검색·구독할 수 있게 제공하는 서비스입니다.

백엔드는 FastAPI + SQLite로 구현되어 있으며 자세한 API·운영 방법은 [BE/README.md](BE/README.md)를 참고하세요.

## 목표 기능

- 기술 블로그 RSS/Atom 주기적 수집
- 게시글 검색 및 블로그별 조회
- 회원가입과 로그인
- 사용자별 키워드 구독
- Discord 웹훅 알림
- Docker 기반 실행 및 배포

## 현재 제공 기능

- RSS/Atom 수집(조건부 요청, 실패 블로그 격리) 및 스케줄러·DB 백업
- 게시글 전문 검색(FTS5, 다중 키워드, 관련도순 정렬)과 블로그·회사·기간 필터
- 회원가입·로그인(Bearer 토큰), 이메일 인증·비밀번호 재설정
- 키워드 구독과 Discord 웹훅·봇 알림(재시도 포함)
- 관리자 블로그 관리·수집·상태 API
- Swagger 문서: `/api/docs`

## 백엔드 실행

```powershell
cd BE
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python run.py
```

기본 주소는 `http://127.0.0.1:5000`입니다.

## 테스트

```powershell
cd BE
python -m unittest discover -s tests -v
```
