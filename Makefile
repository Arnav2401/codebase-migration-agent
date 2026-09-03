.PHONY: setup neo4j neo4j-down lint format typecheck test corpus corpus-baselines eval clean

# .venv lives at .venv.nosync, symlinked as .venv: on machines where this repo sits under
# ~/Documents, something (observed: not iCloud itself per `brctl status`, but never
# conclusively identified without sudo-level tracing) repeatedly sets the macOS UF_HIDDEN
# flag on pip's generated .pth files — and Python 3.13's site.py silently SKIPS hidden .pth
# files, so `import pmigrate` starts failing minutes after a clean install with no error
# pointing at the cause. The .nosync suffix is the standard convention iCloud/related tools
# respect to exclude a directory from being touched at all. Editable install also uses a
# direct symlink into site-packages instead of relying on the generated .pth file being
# processed, since that .pth mechanism is the exact thing observed breaking — see
# docs/decisions.md for the corpus-discovery session where this was diagnosed.
setup:
	python3 -m venv .venv.nosync
	ln -sf .venv.nosync .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"
	ln -sf "$$(pwd)/src/pmigrate" .venv.nosync/lib/python3.13/site-packages/pmigrate
	.venv/bin/pre-commit install || true

neo4j:
	docker compose up -d neo4j
	@echo "Neo4j browser: http://localhost:7474  (neo4j / pmigrate-dev)"

neo4j-down:
	docker compose down

lint:
	.venv/bin/ruff check src tests
	.venv/bin/ruff format --check src tests

format:
	.venv/bin/ruff format src tests
	.venv/bin/ruff check --fix src tests

typecheck:
	.venv/bin/mypy src/pmigrate

test:
	.venv/bin/pytest -q

# Phase 0 targets
corpus:
	.venv/bin/python -m pmigrate.corpus.discover
	.venv/bin/python -m pmigrate.corpus.validate

corpus-baselines:
	.venv/bin/python -m pmigrate.corpus.capture_baselines --manifest corpus/manifest.json

eval:
	.venv/bin/python -m pmigrate.eval.run --config $(CONFIG) --split $(SPLIT)

clean:
	find . -name '__pycache__' -exec rm -rf {} +
	rm -rf .mypy_cache .ruff_cache .pytest_cache
