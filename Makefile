PYTHON ?= python3
CONFIG ?= config/spark.example.json

.PHONY: plan check
plan:
	$(PYTHON) scripts/validate.py --config $(CONFIG) --plan

check:
	$(PYTHON) scripts/validate.py --config $(CONFIG)
	$(PYTHON) -m unittest discover -s tests -v
