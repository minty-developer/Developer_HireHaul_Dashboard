# 임시 배포용 Dockerfile (Render). 4번(Docker/배포 담당)이 자기 설정을 만들면 바꿔도 된다.
#
# 빌드 컨텍스트는 저장소 루트다. rss-collector/의 수집 결과(JSON)도 이미지에 넣어야 해서다.
#   docker build -f BE/Dockerfile .
# Render 설정: Root Directory 비움, Dockerfile Path ./BE/Dockerfile, Build Context .
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/app \
    PORT=5000

WORKDIR /app/BE

RUN addgroup --system app && adduser --system --ingroup app app

COPY BE/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY BE/app ./app
COPY BE/run.py ./
COPY rss-collector/blogs.json rss-collector/posts.json /app/rss-collector/

RUN mkdir -p /app/BE/data && chown -R app:app /app
USER app

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '5000') + '/api/health', timeout=3)"

# 서버를 켜기 전에 RSS 수집 결과를 DB에 넣는다. 여러 번 실행해도 글이 중복되지 않는다.
# 가져오기가 실패해도 서버는 켜지도록 `;`로 잇는다 (실패 내용은 로그에 남는다).
CMD ["sh", "-c", "python -m app.cli import-rss ../rss-collector/blogs.json ../rss-collector/posts.json; exec uvicorn run:app --host 0.0.0.0 --port ${PORT} --proxy-headers --no-access-log"]
