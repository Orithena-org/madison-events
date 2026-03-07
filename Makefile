# Madison Events - Makefile
# GitHub Pages shell. Pipeline lives in orithena-org/content/

PYTHON ?= python3
ORG_DIR = ../orithena-org

.PHONY: help run scrape build demo clean serve open open-landing

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

run: ## Run full pipeline (scrape + build + post)
	cd $(ORG_DIR) && $(PYTHON) -m content.pipeline --domain madison_events

scrape: ## Scrape events only
	cd $(ORG_DIR) && $(PYTHON) -m content.pipeline --domain madison_events --scrape-only

build: ## Build site from cached events
	cd $(ORG_DIR) && $(PYTHON) -m content.pipeline --domain madison_events --build-only

demo: ## Run with sample data (no network)
	cd $(ORG_DIR) && $(PYTHON) -m content.pipeline --domain madison_events --demo --no-post

open: build ## Build and open site in browser
	open output/site/index.html

open-landing: build ## Build and open landing page
	open output/site/landing.html

clean: ## Remove generated output
	rm -rf output/site/* output/newsletter/* output/social/*

serve: build ## Build and serve locally on port 8001
	cd output/site && $(PYTHON) -m http.server 8001
