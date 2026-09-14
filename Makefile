.PHONY: check-python install-dev test-jetson-backend test-spark-backend typecheck build-jetson-frontend build-spark-frontend build-jetson-release build-spark-release e2e-jetson e2e-spark docs-audit release-audit license-audit shell-check check
PYTHON ?= python3
RELEASE_OUT ?= /tmp/agentic-ocudu-release
WHEELS ?= /tmp/agentic-ocudu-wheels
check-python:
	$(PYTHON) --version
install-dev:
	$(PYTHON) -m pip install -r requirements-tools.txt
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
	deploy/jetson/build-release.sh --output $(RELEASE_OUT) --wheels $(WHEELS)
build-spark-release:
	deploy/spark/platform/build-release.sh stage --path $(RELEASE_OUT)
	deploy/spark/platform/build-release.sh download --path $(RELEASE_OUT)
e2e-jetson:
	node apps/jetson-console/frontend/check-browser.mjs
e2e-spark:
	@if [ -x scripts/e2e/spark.sh ]; then scripts/e2e/spark.sh; else echo 'Spark E2E requires a running local preview'; fi
docs-audit:
	$(PYTHON) scripts/audit/docs_audit.py
release-audit:
	$(PYTHON) scripts/audit/release_audit.py
license-audit:
	$(PYTHON) scripts/audit/license_audit.py
shell-check:
	find deploy scripts -type f -name '*.sh' -print0 | xargs -0 -r -n1 bash -n
check: check-python test-jetson-backend test-spark-backend typecheck docs-audit release-audit license-audit shell-check
