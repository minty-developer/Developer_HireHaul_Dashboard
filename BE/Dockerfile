FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/app \
    PORT=5000

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run.py ./

RUN mkdir -p /app/data && chown -R app:app /app
USER app

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '5000') + '/api/health', timeout=3)"

# 프록시 뒤에서 실제 클라이언트 IP를 쓰려면 FORWARDED_ALLOW_IPS에 프록시 주소를 지정한다.
CMD ["sh", "-c", "exec uvicorn run:app --host 0.0.0.0 --port ${PORT} --proxy-headers --no-access-log"]
