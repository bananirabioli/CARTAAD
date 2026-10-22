# Build context: repository root (needs prompts/, schemas/, fixtures/, evals/).
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app/backend

COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt \
 && playwright install --with-deps chromium \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY prompts /app/prompts
COPY schemas /app/schemas
COPY fixtures /app/fixtures
COPY evals /app/evals
COPY scripts /app/scripts
COPY backend /app/backend

RUN chmod +x /app/backend/docker-entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["/app/backend/docker-entrypoint.sh"]
CMD ["api"]
