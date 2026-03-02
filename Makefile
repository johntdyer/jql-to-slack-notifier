VENV   := .venv
PYTHON := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip

.DEFAULT_GOAL := help

# ── Setup ─────────────────────────────────────────────────────────────────────

.PHONY: setup
setup: $(VENV)/bin/activate .env ## Create venv and install dependencies

$(VENV)/bin/activate: requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@touch $(VENV)/bin/activate

.env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example — fill in your credentials before running."; \
	fi

# ── Run ───────────────────────────────────────────────────────────────────────

.PHONY: run
run: $(VENV)/bin/activate ## Run all configured queries and post to Slack
	$(PYTHON) main.py run

.PHONY: list
list: $(VENV)/bin/activate ## List all configured queries
	$(PYTHON) main.py list

.PHONY: schedule
schedule: $(VENV)/bin/activate ## Start the scheduler daemon
	$(PYTHON) main.py schedule

# Pass QUERY="name" to target a specific query: make query QUERY="Open CDS CR's"
.PHONY: query
query: $(VENV)/bin/activate ## Run a single query by name (usage: make query QUERY="My Query Name")
	$(PYTHON) main.py run --query "$(QUERY)"

# ── Lint / Test ───────────────────────────────────────────────────────────────

.PHONY: lint
lint: $(VENV)/bin/activate ## Run pylint on source and main
	$(VENV)/bin/pylint src/ main.py

.PHONY: test
test: $(VENV)/bin/activate ## Run the test suite
	$(VENV)/bin/pytest tests/ -v

.PHONY: pre-commit
pre-commit: $(VENV)/bin/activate ## Install pre-commit hooks into .git
	$(VENV)/bin/pre-commit install

# ── Cleanup ───────────────────────────────────────────────────────────────────

.PHONY: clean
clean: ## Remove the virtual environment
	rm -rf $(VENV)

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
