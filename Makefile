# Sentrix — Development Makefile
# Manages an isolated virtual environment to prevent global package conflicts.

# Detects pyenv Python or falls back to system python3.
PYTHON_BIN := $(shell command -v python3.11 2>/dev/null || \
	(test -x "$(HOME)/.pyenv/versions/3.11.1/bin/python" && echo "$(HOME)/.pyenv/versions/3.11.1/bin/python") || \
	echo python3)

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: test lint typecheck ci bench install clean

$(VENV)/bin/activate:
	$(PYTHON_BIN) -m venv $(VENV)
	$(PIP) install --upgrade pip

install: $(VENV)/bin/activate
	$(PIP) install -e ".[dev]"

test: install
	PYTHONPATH=src $(PYTHON) -m pytest --cov=sentrix

lint: install
	$(PYTHON) -m ruff check .

typecheck: install
	PYTHONPATH=src $(PYTHON) -m pyright

ci: lint typecheck test

bench: install
	PYTHONPATH=src $(PYTHON) scripts/bench.py

clean:
	rm -rf $(VENV)
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
