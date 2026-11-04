# TESTIGO+ — one command: `make run`. Works with GNU make 3.81 (macOS) and Linux.

PY312 ?= $(shell command -v python3.12 2>/dev/null || echo /opt/homebrew/bin/python3.12)
VENV  := .venv
PY    := $(VENV)/bin/python
READY := $(VENV)/.ready

.PHONY: run setup deps-linux up test test-live gate doctor check-secrets clean

## run: install whatever is missing, then start the portal and the interceptor
run: $(READY)
	$(PY) -m scripts.up

$(READY):
	$(MAKE) setup

## setup: venv + locked dependencies + Chromium + SCORER_TOKEN + fast tests (repeatable; never uses sudo)
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
	$(PY) -m playwright install chromium
	$(PY) -m scripts.check_chromium
	$(PY) -m scripts.ensure_scorer_token
	$(PY) -m pytest -q
	@touch $(READY)

## deps-linux: optional, Linux only: the system libraries Chromium needs (apt, asks for sudo)
deps-linux:
	@test -x $(PY) || { echo "run make setup first"; exit 1; }
	@echo "Playwright will install, with apt and sudo, the system libraries Chromium needs:"
	-$(PY) -m playwright install-deps chromium --dry-run
	$(PY) -m playwright install-deps chromium

## up: start the portal (PORTAL_PORT) and the interceptor (INTERCEPTOR_PORT)
up: $(READY)
	$(PY) -m scripts.up

## test: unit tests with test data only (no network, no keys)
test: $(READY)
	$(PY) -m pytest

## test-live: unit tests that call real Meta models (none today; real-model checks are WitnessBench and the gate)
test-live: $(READY)
	@$(PY) -m pytest -m live; code=$$?; \
	if [ $$code -eq 5 ]; then echo "No live unit tests: the real-model checks are WitnessBench (bench/) and make gate (internal, spends credits)."; exit 0; fi; \
	exit $$code

## gate: the team's day-0 gate checklist (real models, spends credits; g3 now fails by design: Wonder resists A1 and A2)
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
