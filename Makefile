.PHONY: install dev run test lint format typecheck cov check \
        docker-build docker-up docker-down clean

IMAGE ?= budgetbot:local
CONTAINER ?= budgetbot

install:
	python3 -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

# Dev server with auto-reload (alias: run).
dev:
	uvicorn src.app:app --reload --host 0.0.0.0 --port 8000

run: dev

test:
	pytest -v tests/

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

typecheck:
	mypy src/

cov:
	pytest -q --cov=src --cov-report=term-missing tests/

# Full quality gate (matches the PR bar): lint + types + tests w/ coverage.
check: lint typecheck cov

# ── Docker (Fargate/App Runner image; see Dockerfile.web) ────────────────────
docker-build:
	docker build -f Dockerfile.web -t $(IMAGE) .

docker-up:
	docker run -d --rm --name $(CONTAINER) -p 8000:8000 --env-file .env $(IMAGE)

docker-down:
	-docker rm -f $(CONTAINER)

clean:
	rm -rf _data __pycache__ .pytest_cache src/__pycache__ src/adapters/__pycache__ tests/__pycache__
