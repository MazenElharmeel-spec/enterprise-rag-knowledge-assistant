.PHONY: up seed test eval lint migrate
up:
	cp -n .env.example .env || true
	docker compose up --build
seed:
	docker compose exec api python -m backend.app.scripts.seed
test:
	uv run pytest
	cd frontend && npm test
eval:
	docker compose exec api python -m backend.app.evals.cli
lint:
	uv run ruff check backend
	uv run mypy backend
migrate:
	docker compose exec api alembic upgrade head
