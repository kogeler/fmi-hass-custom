SHELL := /bin/bash

CONTAINER_ENGINE ?= podman
PYTHON_IMAGE := docker.io/library/python@sha256:1a3c6dbfd2173971abba880c3cc2ec4643690901f6ad6742d0827bae6cefc925
LOCK_IMAGE := localhost/fmi-hass-custom-lock:2026.7.4
DEV_IMAGE := localhost/fmi-hass-custom-dev:2026.7.4
DEV_STAMP := .cache/podman-dev-2026.7.4.stamp
HASSFEST_IMAGE := ghcr.io/home-assistant/hassfest@sha256:5284df007e5b53dada13b07db08a8980780239216bd92ba63b211c0e3d20ca73
PYTEST_WORKERS ?= 0

CONTAINER_BUILD = $(CONTAINER_ENGINE) build --build-arg PYTHON_IMAGE=$(PYTHON_IMAGE) -f Containerfile.dev
CONTAINER_RUN = $(CONTAINER_ENGINE) run --rm --userns=keep-id -v "$(CURDIR):/workspace:Z" -w /workspace
CONTAINER_RUN_OFFLINE = $(CONTAINER_RUN) --network=none

.PHONY: lock lock-build dev-build shell format format-check lint \
	type-check test-fast test-full test-network-block validate validate-local \
	validate-hassfest live audit licenses outdated

lock-build:
	$(CONTAINER_BUILD) --target lock -t $(LOCK_IMAGE) .

lock: lock-build
	@tmp_file="$$(mktemp requirements.txt.XXXXXX)"; \
	$(CONTAINER_ENGINE) run --rm $(LOCK_IMAGE) python -m pip freeze > "$$tmp_file"; \
	mv "$$tmp_file" requirements.txt

$(DEV_STAMP): Containerfile.dev Makefile requirements.txt
	test -s requirements.txt
	$(CONTAINER_BUILD) --target dev -t $(DEV_IMAGE) .
	mkdir -p $(dir $@)
	touch $@

dev-build: $(DEV_STAMP)
	@$(CONTAINER_ENGINE) image exists $(DEV_IMAGE) || { \
		rm -f $(DEV_STAMP); \
		$(MAKE) $(DEV_STAMP); \
	}

shell: dev-build
	$(CONTAINER_RUN) -it $(DEV_IMAGE) /bin/bash

format: dev-build
	$(CONTAINER_RUN_OFFLINE) $(DEV_IMAGE) python -m ruff format .

format-check: dev-build
	$(CONTAINER_RUN_OFFLINE) $(DEV_IMAGE) python -m ruff format --check .

lint: dev-build
	$(CONTAINER_RUN_OFFLINE) $(DEV_IMAGE) python -m ruff check .
	$(CONTAINER_RUN_OFFLINE) $(DEV_IMAGE) python -m pylint custom_components/fmi/*.py --init-hook='import sys; sys.path.append(".")'

type-check: dev-build
	$(CONTAINER_RUN_OFFLINE) $(DEV_IMAGE) python -m mypy

test-fast: dev-build
	$(CONTAINER_RUN_OFFLINE) $(DEV_IMAGE) python -m pytest -n $(PYTEST_WORKERS) -q

test-full: dev-build
	$(CONTAINER_RUN_OFFLINE) $(DEV_IMAGE) python -m pytest -n $(PYTEST_WORKERS) --cov=custom_components.fmi --cov-report=term-missing

test-network-block: dev-build
	@output="$$( $(CONTAINER_RUN_OFFLINE) $(DEV_IMAGE) python -m pytest -q tests/network_probe.py 2>&1 )"; \
	status=$$?; \
	printf '%s\n' "$$output"; \
	test $$status -ne 0; \
	printf '%s\n' "$$output" | grep -Eq 'SocketBlockedError|SocketConnectBlockedError'

validate-local: dev-build
	$(CONTAINER_RUN_OFFLINE) $(DEV_IMAGE) python -m pytest -q tests/test_layout.py
	$(CONTAINER_RUN_OFFLINE) $(DEV_IMAGE) python -m ruff check .

validate-hassfest:
	$(CONTAINER_ENGINE) run --rm --network=none -v "$(CURDIR):/github/workspace:ro,Z" $(HASSFEST_IMAGE)

validate: validate-local validate-hassfest

live: dev-build
	$(CONTAINER_RUN) $(DEV_IMAGE) python -m pytest -o addopts= --strict-config --strict-markers -m live

audit: dev-build
	$(CONTAINER_RUN) $(DEV_IMAGE) python -m pip_audit --strict

licenses: dev-build
	$(CONTAINER_RUN_OFFLINE) $(DEV_IMAGE) python -m piplicenses --format=markdown

outdated: dev-build
	$(CONTAINER_RUN) $(DEV_IMAGE) python -m pip list --outdated
