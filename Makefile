PY ?= python

check:            ## validate fixtures against contracts
	$(PY) eval/check_fixtures.py

serve-fixture:    ## serve the fixture app on http://localhost:8001
	$(PY) -m http.server 8001 -d fixtures/app1

test-p1:          ## each lane replaces its own target
	@echo "P1: add court tests"
test-p2:
	@echo "P2: add dig/medium tests"
test-p3:
	@echo "P3: add UI tests"
test-p4:
	$(PY) -m pytest -q eval revive

.PHONY: check serve-fixture test-p1 test-p2 test-p3 test-p4
