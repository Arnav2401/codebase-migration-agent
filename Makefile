.PHONY: setup neo4j neo4j-down lint format typecheck test corpus corpus-baselines eval clean

setup:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"
	.venv/bin/pre-commit install || true

neo4j:
	docker compose up -d neo4j
	@echo "Neo4j browser: http://localhost:7474  (neo4j / pmigrate-dev)"

neo4j-down:
	docker compose down

lint:
	ruff check src tests
	ruff format --check src tests

format:
	ruff format src tests
	ruff check --fix src tests

typecheck:
	mypy src/pmigrate

test:
	pytest -q

# Phase 0 targets
corpus:
	python -m pmigrate.corpus.discover
	python -m pmigrate.corpus.validate

corpus-baselines:
	python -m pmigrate.corpus.capture_baselines --manifest corpus/manifest.json

eval:
	python -m pmigrate.eval.harness --config $(CONFIG) --split $(SPLIT)

clean:
	find . -name '__pycache__' -exec rm -rf {} +
	rm -rf .mypy_cache .ruff_cache .pytest_cache
