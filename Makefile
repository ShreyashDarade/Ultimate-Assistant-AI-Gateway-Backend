.PHONY: run dev test lint migrate seed docker-up docker-down worker

run:
	uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload

dev:
	docker compose up -d postgres redis minio
	uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload

test:
	pytest -v --cov=app --cov-report=term-missing

lint:
	ruff check app/ tests/
	mypy app/

format:
	ruff format app/ tests/
	ruff check --fix app/ tests/

migrate:
	alembic upgrade head

migrate-new:
	alembic revision --autogenerate -m "$(msg)"

seed:
	python -m scripts.seed_providers

genkey:
	python -m scripts.generate_master_key

worker:
	arq app.workers.worker.WorkerSettings

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f app
