# TwinOps Makefile
PYTHON = .venv/Scripts/python.exe
PYTEST = .venv/Scripts/pytest.exe
RUFF = .venv/Scripts/ruff.exe
NPM = npm

.PHONY: test test-backend test-web lint e2e dev simulator build-web

test: test-backend test-web

test-backend:
	$(PYTEST) -v

test-web:
	$(NPM) --prefix web run test

build-web:
	$(NPM) --prefix web run build

lint:
	$(RUFF) check services simulator ml tests
	$(RUFF) format --check services simulator ml tests

e2e:
	$(PYTEST) -v tests/test_e2e_integration.py

simulator:
	$(PYTHON) -m simulator.cli --site PUNE-01 --interval 1.0 --dump-stdout

dev:
	@echo "Starting TwinOps services..."
	$(PYTHON) -m services.telemetry.main &
	$(PYTHON) -m services.asset.main &
	$(PYTHON) -m services.twin.main &
	$(PYTHON) -m services.alarm.main &
	$(PYTHON) -m services.maintenance.main &
	$(PYTHON) -m services.analytics.main &
	$(PYTHON) -m services.copilot.main &
	$(NPM) --prefix web run dev &
