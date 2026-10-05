.PHONY: help setup test migrate run run-worker run-beat docker-build docker-up docker-down seed clean

help:
	@echo "Available commands:"
	@echo "  make setup        - Install dependencies in virtualenv"
	@echo "  make test         - Run full test suite with pytest"
	@echo "  make migrate      - Apply Alembic migrations"
	@echo "  make seed         - Seed default admin user"
	@echo "  make run          - Run FastAPI development server"
	@echo "  make run-worker   - Run Celery background worker"
	@echo "  make run-beat     - Run Celery Beat scheduler"
	@echo "  make docker-build - Build Docker containers"
	@echo "  make docker-up    - Start entire stack with docker-compose"
	@echo "  make docker-down  - Stop docker-compose services"
	@echo "  make clean        - Remove caches and temporary files"

setup:
	python3 -m venv .venv
	./.venv/bin/pip install --upgrade pip
	./.venv/bin/pip install -r requirements.txt

test:
	./.venv/bin/pytest -v

migrate:
	./.venv/bin/alembic upgrade head

seed:
	./.venv/bin/python3 scripts/seed_admin.py

run:
	./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-worker:
	./.venv/bin/celery -A app.workers.celery_app.celery_app worker --loglevel=info

run-beat:
	./.venv/bin/celery -A app.workers.celery_app.celery_app beat --loglevel=info

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
