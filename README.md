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

## 역할 분담

| 담당 | 범위 |
| --- | --- |
| 1번 | 프론트엔드 + UI/UX: 웹 화면, 검색 화면, 블로그 목록, 구독 화면 |
| 2번 | 백엔드: FastAPI, API, 검색 기능, DB 연결 |
| 3번 | RSS 수집 + 데이터 처리: RSS 자동 수집, 파싱, 중복 제거, 데이터 저장 |
| 4번 | 알림 + Docker/배포: 키워드 구독 알림, Discord 웹훅, 스케줄링, Docker |

## 현재 백엔드(2번) 제공 기능

- 게시글 전문 검색(FTS5, 다중 키워드, 관련도순 정렬)과 블로그·회사·기간 필터
- 회원가입·로그인(Bearer 토큰), 이메일 인증·비밀번호 재설정
- 키워드 구독 API(Discord 웹훅 주소 저장)
- 관리자 블로그 관리·상태 API, DB 백업·복원 명령
- Swagger 문서: `/api/docs`

RSS 수집(3번)과 알림 발송·Docker(4번)가 DB와 맞물리는 규칙은 [BE/README.md](BE/README.md)에 있습니다.

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