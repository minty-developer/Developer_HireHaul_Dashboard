# 개발자 채용 API 서버

Python/Flask로 만든 백엔드 전용 JSON API 서버입니다. 외부 채용 API는 아직 확정하지 않았으며 현재는 샘플 공급자로 전체 흐름을 시험할 수 있습니다.

## VS Code에서 시작

1. VS Code에서 이 `job_dashboard` 폴더를 엽니다.
2. `Terminal > Run Task`에서 **Python: 가상환경 만들기**, **Python: 패키지 설치**를 차례로 실행합니다.
3. 실행 및 디버그 화면에서 **Flask 대시보드 실행**을 선택하고 `F5`를 누릅니다.
4. `http://127.0.0.1:5000/api/health`에서 서버 상태를 확인합니다.

## 실행

```powershell
cd job_dashboard
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

서버는 기본적으로 `http://127.0.0.1:5000`에서 실행됩니다. `/` 화면은 제공하지 않으며 모든 기능은 `/api` 경로의 JSON API로 노출됩니다.

## API 명세

- `GET /api/health`: 서버 상태
- `GET /api/jobs?q=&location=&source=&limit=`: 활성 공고 검색
- `GET /api/stats`: 공고·기업·소스 통계
- `POST /api/sync`: 공고 수집 및 upsert. JSON 예: `{"keyword":"Python 백엔드","count":50}`

## 구조와 다음 단계

- `app/providers.py`: 모든 외부 공식 API 어댑터가 구현할 `JobProvider` 인터페이스와 개발용 `SampleProvider`
- `app/db.py`: SQLite 저장소와 중복 방지(`source + external_id`)
- `app/routes.py`: JSON API 엔드포인트
- 운영 전에는 `/api/sync`에 관리자 인증을 추가하고, Windows 작업 스케줄러나 APScheduler로 주기 수집을 구성하는 것을 권장합니다.
- 공식 API가 결정되면 `JobProvider.fetch()`를 구현한 클래스를 만들고 `routes.py`의 공급자 생성 부분에 연결합니다. 외부 응답 형식과 관계없이 DB의 공통 job 필드로 정규화합니다.

### 추후 실제 API 연결 체크리스트

1. 공식 이용 약관, 표시 의무, 호출 제한 확인 및 API 키 발급
2. `JobProvider` 구현체에서 인증·페이지네이션·timeout 처리
3. 외부 필드를 공통 job 스키마로 정규화
4. `/api/sync`에서 `SampleProvider`를 실제 공급자로 교체
5. 실패 재시도, 호출량 로깅, 관리자 인증 추가

## 테스트

```powershell
python -m unittest discover -s tests -v
```
