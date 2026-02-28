# Madison Events - Makefile
# Simple commands for running the events pipeline

PYTHON ?= python3
VENV = .venv

.PHONY: help install run scrape build demo clean deploy-preview

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	$(PYTHON) -m pip install -r requirements.txt

run: ## Run full pipeline (scrape + build)
	$(PYTHON) run.py

scrape: ## Scrape events only
	$(PYTHON) run.py --scrape-only

build: ## Build site from cached events
	$(PYTHON) run.py --build-only

demo: ## Run with sample data (no network)
	$(PYTHON) run.py --demo

open: build ## Build and open site in browser
	open output/site/index.html

open-landing: build ## Build and open landing page
	open output/site/landing.html

clean: ## Remove generated output
	rm -rf output/site/* output/newsletter/* output/social/*

serve: build ## Build and serve locally on port 8001
	cd output/site && $(PYTHON) -m http.server 8001
