from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone


KST = timezone(timedelta(hours=9))


class JobProvider(ABC):
    """추후 공식 채용 API 어댑터가 구현할 공통 계약입니다."""

    name: str

    @abstractmethod
    def fetch(self, keywords: str = "개발자", count: int = 50) -> list[dict]:
        """외부 응답을 DB의 job 필드 형식으로 정규화해 반환합니다."""


class SampleProvider(JobProvider):
    name = "sample"

    def fetch(self, keywords: str = "개발자", count: int = 50) -> list[dict]:
        return sample_jobs()[:count]


def sample_jobs() -> list[dict]:
    now = datetime.now(KST)
    samples = [
        ("sample-1", "Python 백엔드 개발자", "샘플테크", "서울 강남구", "신입·경력", "Python,Flask,SQL"),
        ("sample-2", "프론트엔드 개발자", "예시랩", "경기 성남시", "경력 2년 이상", "JavaScript,React,HTML"),
        ("sample-3", "데이터 엔지니어", "데모데이터", "서울 마포구", "경력무관", "Python,ETL,Cloud"),
    ]
    return [{
        "source": "sample", "external_id": ext_id, "title": title,
        "company": company, "location": location, "experience": experience,
        "education": "학력무관", "employment_type": "정규직", "salary": "회사내규",
        "url": "https://example.com/jobs/" + ext_id, "posted_at": now.isoformat(),
        "expires_at": (now + timedelta(days=14)).isoformat(), "keywords": keywords,
        "active": 1, "fetched_at": now.isoformat(),
    } for ext_id, title, company, location, experience, keywords in samples]
