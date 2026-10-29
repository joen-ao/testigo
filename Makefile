# TESTIGO+ — one command: `make run`. Works with GNU make 3.81 (macOS) and Linux.

PY312 ?= $(shell command -v python3.12 2>/dev/null || echo /opt/homebrew/bin/python3.12)
VENV  := .venv
PY    := $(VENV)/bin/python
READY := $(VENV)/.ready

.PHONY: run setup up test test-live gate doctor check-secrets clean

## run: install whatever is missing, then start the portal and the interceptor
run: $(READY)
	$(PY) -m scripts.up

$(READY):
	$(MAKE) setup

## setup: venv + locked dependencies + Chromium + SCORER_TOKEN + fast tests (repeatable)
setup:
	@test -x "$(PY312)" || { echo "Python 3.12 not found. macOS: brew install python@3.12"; exit 1; }
	@test -d $(VENV) || $(PY312) -m venv $(VENV)
	$(PY) -m pip install --quiet --upgrade pip
	@if [ -f requirements.lock ]; then \
		$(PY) -m pip install --quiet -r requirements.lock; \
	else \
		$(PY) -m pip install --quiet -e ".[dev]" && \
		$(PY) -m pip freeze --exclude-editable > requirements.lock && \
		echo "wrote requirements.lock"; \
	fi
	$(PY) -m pip install --quiet --no-deps -e .
	@if [ "$$(uname)" = "Linux" ]; then \
		$(PY) -m playwright install --with-deps chromium; \
	else \
		$(PY) -m playwright install chromium; \
	fi
	$(PY) -m scripts.ensure_scorer_token
	$(PY) -m pytest -q
	@touch $(READY)

## up: start the portal (PORTAL_PORT) and the interceptor (INTERCEPTOR_PORT)
up: $(READY)
	$(PY) -m scripts.up

## test: unit tests with test data only (no network, no keys)
test: $(READY)
	$(PY) -m pytest

## test-live: tests that call real Meta models (needs .env)
test-live: $(READY)
	$(PY) -m pytest -m live

## gate: today's gate checklist (real models only; scripts are written by the team)
gate: $(READY)
	@if [ -f gate/run_gate.py ]; then $(PY) -m gate.run_gate; \
	else echo "gate/run_gate.py not written yet (see docs/specs/F0-infraestructura.md §13)"; exit 1; fi

## doctor: versions, Chromium, and a 1280x800 capture of the portal
doctor: $(READY)
	$(PY) -m scripts.doctor

## check-secrets: no keys, signing keys, .env or evidence in files that would be committed
check-secrets:
	@if [ -x $(PY) ]; then $(PY) -m scripts.check_secrets; else python3 -m scripts.check_secrets; fi

## clean: remove the venv and caches (never .env, .secrets/ or runs/)
clean:
	rm -rf $(VENV) .pytest_cache build *.egg-info
	find . -name __pycache__ -type d -prune -not -path "./.venv/*" -exec rm -rf {} +
