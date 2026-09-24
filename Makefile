.PHONY: check-python install-dev test-jetson-backend test-spark-backend typecheck build-jetson-frontend build-spark-frontend build-jetson-release build-spark-release e2e-jetson e2e-spark docs-audit release-audit license-audit shell-check check ci
VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
BOOTSTRAP_PYTHON ?= python3
RELEASE_OUT ?= /tmp/agentic-ocudu-release
check-python:
	$(PYTHON) -c 'import sys; assert (3, 10) <= sys.version_info[:2] <= (3, 12), "Use Python 3.10-3.12 (Jetson: 3.10; Spark: 3.12)"; print(sys.version)'
install-dev:
	$(BOOTSTRAP_PYTHON) -c 'import sys; assert (3, 10) <= sys.version_info[:2] <= (3, 12), "BOOTSTRAP_PYTHON must be Python 3.10-3.12"'
	@test -x $(PYTHON) || $(BOOTSTRAP_PYTHON) -m venv $(VENV)
	$(MAKE) check-python
	$(PYTHON) -m pip install -r requirements-tools.txt -r apps/jetson-console/requirements-dev.txt -r apps/spark-platform/requirements-dev.txt
	npm --prefix apps/jetson-console/frontend ci
	npm --prefix apps/jetson-console/frontend run build
	npm --prefix apps/spark-platform/frontend ci
	npm --prefix apps/spark-platform/frontend run build
test-stack:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'
test-jetson-backend:
	PYTHONPATH=apps/jetson-console/backend:apps/spark-platform/backend $(PYTHON) -m unittest discover -s apps/jetson-console/tests -p 'test_*.py'
test-spark-backend:
	PYTHONPATH=apps/jetson-console/backend:apps/spark-platform/backend $(PYTHON) -m unittest discover -s apps/spark-platform/tests -p 'test_*.py'
typecheck:
	npm --prefix apps/jetson-console/frontend run typecheck
	npm --prefix apps/spark-platform/frontend run typecheck
build-jetson-frontend:
	npm --prefix apps/jetson-console/frontend ci
	npm --prefix apps/jetson-console/frontend run build
build-spark-frontend:
	npm --prefix apps/spark-platform/frontend ci
	npm --prefix apps/spark-platform/frontend run build
build-jetson-release:
	$(PYTHON) scripts/build_release.py jetson --output $(RELEASE_OUT)
build-spark-release:
	$(PYTHON) scripts/build_release.py spark --output $(RELEASE_OUT)
e2e-jetson:
	$(PYTHON) scripts/e2e_jetson.py
e2e-spark:
	$(PYTHON) scripts/e2e_spark.py
docs-audit:
	$(PYTHON) scripts/audit/docs_audit.py
release-audit:
	$(PYTHON) scripts/audit/release_audit.py
license-audit:
	$(PYTHON) scripts/audit/license_audit.py
shell-check:
	find deploy scripts -type f -name '*.sh' -print0 | xargs -0 -r -n1 bash -n
check: check-python test-jetson-backend test-spark-backend test-stack typecheck docs-audit release-audit license-audit shell-check

# One local/CI entry point; production builds already include TypeScript checks.
ci: check-python test-jetson-backend test-spark-backend test-stack build-jetson-frontend build-spark-frontend docs-audit release-audit license-audit shell-check

.PHONY: test-stack
