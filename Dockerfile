# Build: docker build -t exercises-api .
# Run:   docker run -p 8000:8000 --env-file .env exercises-api
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Dependencies first, so a code change does not reinstall them on every build.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY engine/ ./engine/
COPY app/ ./app/
COPY api/ ./api/
COPY data/ ./data/
COPY images/ ./images/
COPY videos/ ./videos/
COPY NOTICE.md LICENSE ./

# Run as a non-root user: a web process should never be able to write to its
# own code. The data directory stays writable for the default SQLite file.
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /srv/var \
    && chown -R app:app /srv/var
USER app

ENV DATABASE_URL=sqlite:////srv/var/exercises.db
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/v1/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
