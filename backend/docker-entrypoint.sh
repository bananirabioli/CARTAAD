#!/bin/sh
set -e
cd /app/backend

wait_for_db() {
  python - <<'PY'
import time
from sqlalchemy import create_engine, text
from app.config import get_settings
url = get_settings().database_url
for attempt in range(60):
    try:
        with create_engine(url).connect() as c:
            c.execute(text("select 1"))
        break
    except Exception as exc:  # noqa: BLE001
        print(f"esperando base de datos ({attempt + 1}/60): {exc.__class__.__name__}")
        time.sleep(2)
else:
    raise SystemExit("la base de datos no respondió")
PY
}

case "$1" in
  api)
    wait_for_db
    alembic upgrade head
    python -m app.seed.seed_once
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
    ;;
  worker)
    wait_for_db
    exec celery -A app.worker worker --loglevel=INFO --concurrency=3
    ;;
  beat)
    wait_for_db
    exec celery -A app.worker beat --loglevel=INFO --schedule /tmp/celerybeat-schedule
    ;;
  *)
    exec "$@"
    ;;
esac
