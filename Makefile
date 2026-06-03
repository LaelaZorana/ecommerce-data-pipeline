# CommercePipeline -- Makefile DAG.
# The pipeline target is itself a small DAG: ingest -> load -> transform -> quality,
# wired through file-stamp prerequisites so `make` only reruns what changed.

PYTHON ?= python3
PORT ?= 8501
RAW_DIR := data/raw
WAREHOUSE := data/warehouse/commerce.duckdb
RAW_STAMP := $(RAW_DIR)/.ingested

.DEFAULT_GOAL := help

.PHONY: help install ingest load transform quality pipeline test dashboard demo clean lint

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install runtime + dev dependencies
	$(PYTHON) -m pip install -r requirements.txt

$(RAW_STAMP): pipeline/ingest.py pipeline/config.py
	$(PYTHON) -m pipeline ingest
	@touch $(RAW_STAMP)

ingest: $(RAW_STAMP) ## Generate the synthetic raw dataset

$(WAREHOUSE): $(RAW_STAMP) pipeline/load.py pipeline/transform.py $(wildcard pipeline/sql/**/*.sql)
	$(PYTHON) -m pipeline load
	$(PYTHON) -m pipeline transform

load: $(WAREHOUSE) ## Load raw files into DuckDB
transform: $(WAREHOUSE) ## Build staging + mart models

quality: $(WAREHOUSE) ## Run the data-quality gate (fails on violations)
	$(PYTHON) -m pipeline quality

pipeline: ## Run the full pipeline: ingest -> load -> transform -> quality
	$(PYTHON) -m pipeline run

test: ## Run the test suite
	$(PYTHON) -m pytest -q

dashboard: ## Serve the Streamlit dashboard (PORT overrideable)
	$(PYTHON) -m streamlit run dashboard/app.py --server.port $(PORT)

demo: pipeline ## Run the pipeline, then launch the dashboard
	$(MAKE) dashboard

clean: ## Remove generated data and caches
	rm -rf $(RAW_DIR)/* data/warehouse/* .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
