PYTHON ?= python3.11
VENV := .venv
BIN := $(VENV)/bin
PY := $(BIN)/$(notdir $(PYTHON))
export PYTHONPATH := $(CURDIR)
export FLOWSCOPE_DB_PATH ?= $(CURDIR)/data/flowscope.duckdb

.PHONY: setup ingest build app test lint compose

setup:
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install -U pip
	$(PY) -m pip install -r requirements.txt -r requirements-dev.txt

ingest:
	$(PY) -m ingestion.fetch_issuer_files
	$(PY) -m ingestion.fetch_prices
	$(PY) -m ingestion.fetch_macro

build:
	cd dbt && $(CURDIR)/$(BIN)/dbt deps --profiles-dir . || true
	cd dbt && $(CURDIR)/$(BIN)/dbt run --profiles-dir .

app:
	$(BIN)/streamlit run app/dashboard.py

test:
	$(BIN)/pytest tests/ -q
	$(PY) -m quality.run_expectations --dry-run

lint:
	$(BIN)/ruff check ingestion warehouse quality app tests orchestration

compose:
	docker compose up --build
