from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone


# 한국 시간대
KST = timezone(
    timedelta(hours=9)
)


# 모든 채용 API Provider가 따라야 하는 기본 구조
class JobProvider(ABC):

    name: str

    @abstractmethod
    def fetch(
        self,
        keywords: str = "개발자",
        count: int = 50
    ) -> list[dict]:

        """
        외부 채용 API에서 데이터를 가져온 뒤
        우리 DB 형식으로 변환해서 반환한다.
        """

        pass


# 테스트용 샘플 Provider
class SampleProvider(JobProvider):

    name = "sample"

    def fetch(
        self,
        keywords: str = "개발자",
        count: int = 50
    ) -> list[dict]:

        jobs = sample_jobs(
            keywords
        )

        return jobs[:count]


# 샘플 채용공고 생성
def sample_jobs(
    keywords: str = "개발자"
) -> list[dict]:

    now = datetime.now(KST)

    samples = [
        (
            "sample-1",
            "Python 백엔드 개발자",
            "샘플테크",
            "서울 강남구",
            "신입·경력",
            "Python,Flask,SQL"
        ),

        (
            "sample-2",
            "프론트엔드 개발자",
            "예시랩",
            "경기 성남시",
            "경력 2년 이상",
            "JavaScript,React,HTML"
        ),

        (
            "sample-3",
            "데이터 엔지니어",
            "데모데이터",
            "서울 마포구",
            "경력무관",
            "Python,ETL,Cloud"
        ),
    ]

    jobs = []

    for (
        external_id,
        title,
        company,
        location,
        experience,
        job_keywords
    ) in samples:

        job = {
            "source": "sample",

            "external_id": external_id,

            "title": title,

            "company": company,

            "location": location,

            "experience": experience,

            "education": "학력무관",

            "employment_type": "정규직",

            "salary": "회사내규",

            "url":
                "https://example.com/jobs/"
                + external_id,

            "posted_at":
                now.isoformat(),

            "expires_at":
                (
                    now
                    + timedelta(days=14)
                ).isoformat(),

            "keywords":
                job_keywords
                if job_keywords
                else keywords,

            "active": 1,

            "fetched_at":
                now.isoformat(),
        }

        jobs.append(job)

    return jobs