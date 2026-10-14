.PHONY: help install run lint format test test-cov migrate migration upgrade downgrade \
        docker-up docker-down docker-logs admin seed clean

# ============================================
# Help
# ============================================
help:
	@echo "Available commands:"
	@echo "  install        Install dependencies via uv"
	@echo "  run            Run development server"
	@echo "  lint           Run Ruff linter"
	@echo "  format         Run Ruff formatter"
	@echo "  test           Run tests"
	@echo "  test-cov       Run tests with coverage"
	@echo "  migrate        Apply all migrations"
	@echo "  migration      Create new migration (use: make migration m=\"message\")"
	@echo "  upgrade        Alias for migrate"
	@echo "  downgrade      Rollback last migration"
	@echo "  docker-up      Start docker-compose services"
	@echo "  docker-down    Stop docker-compose services"
	@echo "  docker-logs    Tail docker-compose logs"
	@echo "  admin          Create admin user"
	@echo "  seed           Seed database with test data"
	@echo "  clean          Remove caches and build artifacts"

# ============================================
# Dependencies
# ============================================
install:
	uv sync

# ============================================
# Development
# ============================================
run:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir src

lint:
	uv run ruff check src tests

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

# ============================================
# Testing
# ============================================
test:
	uv run pytest

test-cov:
	uv run pytest --cov=src/app --cov-report=term-missing --cov-report=html

# ============================================
# Database / Alembic
# ============================================
migrate:
	uv run alembic upgrade head

migration:
	uv run alembic revision --autogenerate -m "$(m)"

upgrade: migrate

downgrade:
	uv run alembic downgrade -1

# ============================================
# Docker
# ============================================
docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

# ============================================
# Scripts
# ============================================
admin:
	uv run python scripts/create_admin.py

seed:
	uv run python scripts/seed.py

# ============================================
# Cleanup
# ============================================
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
