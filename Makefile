# Rounds: doctor call scheduler. Run `make setup` once, then `make seed` and `make dev`.

PY      := api/.venv/bin/python
PYTHON  ?= python3

.PHONY: setup seed dev api web test lint typecheck simulate check

setup:            ## Create the API virtualenv and install web dependencies
	$(PYTHON) -m venv api/.venv
	api/.venv/bin/pip install -e "api[dev]"
	cd web && pnpm install

seed:             ## Reset the database with doctors and four weeks of replayed history
	cd api && .venv/bin/python -m scripts.seed

api:              ## Run the API on :8000
	cd api && .venv/bin/uvicorn app.main:app --reload --port 8000

web:              ## Run the web app on :3000
	cd web && pnpm dev

dev:              ## Run API and web together
	$(MAKE) -j2 api web

test:             ## Run API tests
	cd api && .venv/bin/pytest -q

lint:             ## Lint and format-check both apps
	cd api && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	cd web && pnpm lint && pnpm format:check

typecheck:        ## Strict type checks for both apps
	cd api && .venv/bin/mypy
	cd web && pnpm typecheck

simulate:         ## Compare placement strategies on synthetic demand
	cd api && .venv/bin/python -m scripts.simulate --days 10 --load 1.0

check: lint typecheck test   ## Everything CI would run
