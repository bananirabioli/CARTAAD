SHELL := /bin/bash
PY := backend/.venv/bin/python
PYTHON312 ?= python3.12

.PHONY: help setup up down test eval openapi migration typecheck lint dev-api dev-web seed-sources

help:
	@echo "make up            # levanta todo con docker compose (modo mock, sin llaves)"
	@echo "make setup         # entorno local: venv del backend + dependencias del frontend"
	@echo "make test          # pruebas del backend (SQLite, Celery eager, MockProvider)"
	@echo "make eval          # set de evaluación con MockProvider → evals/report.md"
	@echo "make openapi       # regenera openapi.json y los tipos del frontend"
	@echo "make typecheck     # tsc del frontend"
	@echo "make seed-sources  # agrega 100 fuentes monitoreadas de prueba"

setup:
	$(PYTHON312) -m venv backend/.venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r backend/requirements.txt
	cd frontend && pnpm install

up:
	docker compose up --build

down:
	docker compose down

test:
	cd backend && .venv/bin/python -m pytest -q

eval:
	@if [ -x "$(PY)" ]; then cd backend && .venv/bin/python -m app.evals.run $(if $(EVAL_PROVIDER),--provider $(EVAL_PROVIDER),); \
	else docker compose run --rm -v "$(CURDIR)/evals:/app/evals" -e EVAL_PROVIDER=$(EVAL_PROVIDER) api python -m app.evals.run; fi

openapi:
	cd backend && AUTO_SEED=false .venv/bin/python -m app.scripts.dump_openapi
	cd frontend && npx openapi-typescript ../backend/openapi.json -o src/lib/api/schema.d.ts

migration:
	@test -n "$(m)" || (echo 'uso: make migration m="descripcion"' && exit 1)
	cd backend && rm -f .migrate.db && DATABASE_URL="sqlite:///$$PWD/.migrate.db" .venv/bin/alembic upgrade head \
	  && REV=$$(printf "%04d" $$(( $$(ls alembic/versions/*.py | wc -l) + 1 ))) \
	  && DATABASE_URL="sqlite:///$$PWD/.migrate.db" .venv/bin/alembic revision --autogenerate --rev-id $$REV -m "$(m)" \
	  && sed -i.bak 's/astext_type=Text()/astext_type=sa.Text()/g' alembic/versions/*.py && rm -f alembic/versions/*.bak .migrate.db

typecheck:
	cd frontend && npx tsc --noEmit

lint:
	cd frontend && pnpm lint

dev-api:
	cd backend && .venv/bin/alembic upgrade head && AUTO_SEED=true .venv/bin/uvicorn app.main:app --reload --port 8000

dev-web:
	cd frontend && pnpm dev

seed-sources:
	@if [ -x "$(PY)" ]; then $(PY) scripts/seed_sources.py --n 100; \
	else docker compose exec api python /app/scripts/seed_sources.py --n 100; fi
