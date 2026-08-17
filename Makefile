# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help
# Test suites already parallelize internally. Serializing the orchestration
# graph prevents `make -j` from multiplying auto-xdist workers or racing on
# shared locks, images, and exported artifacts.
.NOTPARALLEL:

RUNTIME_LOCK := requirements.txt
DEVELOPMENT_LOCK := requirements-dev.txt
LINT_LOCK := requirements-lint.txt
LINT_PROJECT := tools/lint/pyproject.toml
LINT_VENV := venv-lint
LINT_PYTHON := $(LINT_VENV)/bin/python
RUFF := $(LINT_VENV)/bin/ruff
SYSTEM_PYTHON ?= python3
COMPILE := --quiet --strip-extras --allow-unsafe --generate-hashes
LOCK_UPGRADE ?=
VERSION_ARGS ?=

PYTEST_WORKERS ?= auto
PYTEST_XDIST := -n $(PYTEST_WORKERS) --dist=worksteal
RUFF_SOURCES := custom_components tests .github/scripts
PYTHON_SOURCES := custom_components/fmi tests .github/scripts
SHELL_FILES := containers/toolbox/entrypoint.sh
COVERAGE_REPORT := coverage-report.md
COVERAGE_TOTAL := coverage-total.txt
DEPENDENCY_SNAPSHOT := dependency-snapshot.json
RUFF_OUTPUT_FORMAT ?=
RUFF_OUTPUT := $(if $(RUFF_OUTPUT_FORMAT),--output-format=$(RUFF_OUTPUT_FORMAT))

HASSFEST_IMAGE := ghcr.io/home-assistant/hassfest@sha256:a77f1cf7cfc21ad626ebaae52ecb6131a45ab20223f8c2c0750bfca487aa4f05
ACTIONLINT_IMAGE := docker.io/rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667
HACS_IMAGE := ghcr.io/hacs/action@sha256:ea472b182558d08e50221c550fc5cdbba9e1bc1efba53f92bc4fed38e7bc56b9

include make/container.mk

.PHONY: help lint-venv lock refresh-dependencies freeze-check dev-build format \
	format-check lint type-check bandit syntax shellcheck test-fast test-full \
	test-network-block coverage-report confinement-test version-check version-sync \
	validate validate-local validate-actions validate-hassfest validate-hacs live \
	compatibility-stable compatibility-prerelease audit audit-raw licenses outdated \
	validator-images dependency-snapshot release-notes check ci clean

help:
	@printf '%s\n' \
		'make doctor        Verify required host orchestration tools and rootless Podman' \
		'make lock          Regenerate all three hash-verified dependency locks' \
		'make freeze-check  Recompile locks without upgrades and reject drift' \
		'make dev-build     Build the content-addressed toolbox image' \
		'make format        Apply Ruff fixes and formatting on the host' \
		'make format-check  Check Ruff formatting on the host' \
		'make lint          Run host Ruff and containerized Pylint' \
		'make type-check    Run mypy in the confined toolbox' \
		'make bandit        Scan integration runtime Python for security issues' \
		'make test-fast     Run offline pytest with automatic xdist workers' \
		'make test-full     Run offline pytest and the 95% coverage gate' \
		'make live          Run bounded live FMI probes with automatic workers' \
		'make validate      Run local, workflow, hassfest, and optional HACS validation' \
		'make validator-images' \
		'                   Pull immutable external validator images' \
		'make audit         Enforce reviewed dependency vulnerability exceptions' \
		'make licenses      Print the installed dependency license inventory' \
		'make dependency-snapshot' \
		'                   Build all three GitHub dependency manifests offline' \
		'make check         Run the complete local gate set' \
		'make ci            Run local gates plus the online reviewed audit' \
		'make clean         Remove generated caches and reports, never tmp/'

# Ruff is the one intentionally persistent host tool. Recreate its environment
# whenever the dedicated lock changes so removed packages cannot linger.
lint-venv:
	@command -v $(SYSTEM_PYTHON) >/dev/null 2>&1 || { \
		printf 'required command not found: %s\n' '$(SYSTEM_PYTHON)' >&2; exit 1; \
	}
	@if [[ ! -x "$(RUFF)" ]] || \
		[[ ! -f "$(LINT_VENV)/.$(LINT_LOCK)" ]] || \
		! cmp -s $(LINT_LOCK) "$(LINT_VENV)/.$(LINT_LOCK)"; then \
		if [[ -e "$(LINT_VENV)" ]]; then find "$(LINT_VENV)" -depth -delete; fi; \
		$(SYSTEM_PYTHON) -m venv "$(LINT_VENV)"; \
		$(LINT_PYTHON) -m pip install --quiet --require-hashes \
			--only-binary=:all: --requirement $(LINT_LOCK); \
		cp -- $(LINT_LOCK) "$(LINT_VENV)/.$(LINT_LOCK)"; \
	fi

lock: lock-image
	@$(BOX_ARCHIVE) | $(PODMAN) run $(LOCK_ONLINE) \
		--env BOX_EXPORT="$(RUNTIME_LOCK) $(DEVELOPMENT_LOCK) $(LINT_LOCK)" \
		--env BOX_EXPORT_ON_SUCCESS=1 $(LOCK_TAG) \
		bash -ceu 'python -m piptools compile $(COMPILE) $(LOCK_UPGRADE) \
				--output-file=$(RUNTIME_LOCK) pyproject.toml; \
			python -m piptools compile $(COMPILE) $(LOCK_UPGRADE) --extra=dev \
				--output-file=$(DEVELOPMENT_LOCK) pyproject.toml; \
			python -m piptools compile $(COMPILE) $(LOCK_UPGRADE) \
				--output-file=$(LINT_LOCK) $(LINT_PROJECT); \
			chmod 0644 $(RUNTIME_LOCK) $(DEVELOPMENT_LOCK) $(LINT_LOCK)' \
		| tar --extract --file=- --no-same-owner

refresh-dependencies:
	@$(MAKE) lock LOCK_UPGRADE=--upgrade
	@if [[ -e "$(LINT_VENV)" ]]; then find "$(LINT_VENV)" -depth -delete; fi
	@$(MAKE) lint-venv

freeze-check: lock-image
	@$(BOX_ARCHIVE) | $(PODMAN) run $(LOCK_ONLINE) $(LOCK_TAG) \
		bash -ceu 'cp $(RUNTIME_LOCK) /tmp/runtime.txt; \
			cp $(DEVELOPMENT_LOCK) /tmp/development.txt; \
			cp $(LINT_LOCK) /tmp/lint.txt; \
			python -m piptools compile $(COMPILE) \
				--output-file=/tmp/runtime.txt pyproject.toml; \
			python -m piptools compile $(COMPILE) --extra=dev \
				--output-file=/tmp/development.txt pyproject.toml; \
			python -m piptools compile $(COMPILE) \
				--output-file=/tmp/lint.txt $(LINT_PROJECT); \
			diff -u <(sed "/^[[:space:]]*#/d" $(RUNTIME_LOCK)) \
				<(sed "/^[[:space:]]*#/d" /tmp/runtime.txt); \
			diff -u <(sed "/^[[:space:]]*#/d" $(DEVELOPMENT_LOCK)) \
				<(sed "/^[[:space:]]*#/d" /tmp/development.txt); \
			diff -u <(sed "/^[[:space:]]*#/d" $(LINT_LOCK)) \
				<(sed "/^[[:space:]]*#/d" /tmp/lint.txt)'

dev-build: toolbox-image

format: lint-venv
	@$(RUFF) check --fix $(RUFF_SOURCES)
	@$(RUFF) format $(RUFF_SOURCES)

format-check: lint-venv
	@$(RUFF) format --check $(RUFF_SOURCES)

lint: lint-venv toolbox-image
	@$(RUFF) check $(RUFF_OUTPUT) $(RUFF_SOURCES)
	@$(RUFF) format --check $(RUFF_SOURCES)
	$(BOX_RUN) python -m pylint custom_components/fmi/*.py \
		--init-hook='import sys; sys.path.append(".")'

type-check: toolbox-image
	$(BOX_RUN) python -m mypy

bandit: toolbox-image
	$(BOX_RUN) python -m bandit -q -c pyproject.toml -r custom_components/fmi

syntax: toolbox-image
	$(BOX_RUN) sh -ceu 'python -m compileall -q $(PYTHON_SOURCES); bash -n $(SHELL_FILES)'

shellcheck: toolbox-image
	$(BOX_RUN) shellcheck $(SHELL_FILES)

test-fast: toolbox-image
	$(BOX_RUN) python -m pytest $(PYTEST_XDIST) -q

test-full: toolbox-image
	@mkdir -p $(ARTIFACTS)
	@$(BOX_ARCHIVE) | $(PODMAN) run $(BOX_CONFINE) \
		--env BOX_EXPORT="coverage.xml $(COVERAGE_REPORT) $(COVERAGE_TOTAL)" \
		$(TOOLBOX_TAG) sh -ceu 'status=0; \
			python -m pytest $(PYTEST_XDIST) --cov=custom_components.fmi \
				--cov-report=term-missing --cov-report=xml:coverage.xml || status=$$?; \
			python -m coverage report --format=markdown > $(COVERAGE_REPORT); \
			python -m coverage report --format=total > $(COVERAGE_TOTAL); \
			exit $$status' \
		| tar --extract --file=- --directory=$(ARTIFACTS) --no-same-owner

test-network-block: toolbox-image
	$(BOX_RUN) python -m pytest $(PYTEST_XDIST) -q tests/network_probe.py

coverage-report:
	@test -s $(ARTIFACTS)/coverage.xml \
		-a -s $(ARTIFACTS)/$(COVERAGE_REPORT) \
		-a -s $(ARTIFACTS)/$(COVERAGE_TOTAL) || { \
		printf 'No coverage report; run make test-full first.\n' >&2; exit 1; \
	}
	@cat -- $(ARTIFACTS)/$(COVERAGE_REPORT)

confinement-test: toolbox-image
	@test ! -e custom_components/fmi/.container-mutation
	@$(BOX_ARCHIVE) | $(PODMAN) run $(BOX_CONFINE) $(TOOLBOX_TAG) bash -ceu '\
		test "$$(id -u)" -ne 0; \
		grep -Eq "^CapEff:[[:space:]]+0+$$" /proc/self/status; \
		grep -Eq "^NoNewPrivs:[[:space:]]+1$$" /proc/self/status; \
		grep -Eq "^Seccomp:[[:space:]]+2$$" /proc/self/status; \
		test ! -e .git; test ! -e /workspace; test ! -e /run/podman/podman.sock; \
		test -z "$${SSH_AUTH_SOCK:-}"; test -z "$${GITHUB_TOKEN:-}"; \
		! touch /etc/fmi-toolbox-write 2>/dev/null; touch /tmp/write-ok /work/write-ok; \
		touch custom_components/fmi/.container-mutation; \
		python -c "import socket; s=socket.socket(); s.settimeout(0.2); \
		raise SystemExit(s.connect_ex((\"1.1.1.1\", 443)) == 0)"'
	@test ! -e custom_components/fmi/.container-mutation

version-check: toolbox-image
	$(BOX_RUN) python .github/scripts/version.py check $(VERSION_ARGS)

version-sync: toolbox-image
	@$(BOX_ARCHIVE) | $(PODMAN) run $(BOX_CONFINE) \
		--env BOX_EXPORT=custom_components/fmi/manifest.json \
		--env BOX_EXPORT_ON_SUCCESS=1 $(TOOLBOX_TAG) \
		python .github/scripts/version.py sync \
		| tar --extract --file=- --no-same-owner

validate-local: toolbox-image
	$(BOX_RUN) python -m pytest $(PYTEST_XDIST) -q \
		tests/test_layout.py tests/test_distribution.py tests/test_setup.py

validator-images:
	@for image in '$(ACTIONLINT_IMAGE)' '$(HASSFEST_IMAGE)' '$(HACS_IMAGE)'; do \
		$(PODMAN) image exists "$$image" || $(PODMAN) pull --quiet "$$image" >/dev/null; \
	done

# External validator images receive the same archive snapshot through stdin.
# Their wrappers unpack only into private tmpfs; the host checkout is never
# mounted. HACS is enabled only when its exact repository/ref token inputs exist.
validate-actions:
	@$(PODMAN) image exists '$(ACTIONLINT_IMAGE)' || { \
		printf 'actionlint image is missing; run make validator-images\n' >&2; exit 1; \
	}
	@$(BOX_ARCHIVE) | $(PODMAN) run $(BOX_CONFINE) \
		--entrypoint sh $(ACTIONLINT_IMAGE) -ceu \
		'mkdir -p /work/src; tar -xf - -C /work/src; cd /work/src; \
			actionlint -no-color -config-file .github/actionlint.yaml \
				.github/workflows/*.yml'

validate-hassfest:
	@$(PODMAN) image exists '$(HASSFEST_IMAGE)' || { \
		printf 'hassfest image is missing; run make validator-images\n' >&2; exit 1; \
	}
	@$(BOX_ARCHIVE) | $(PODMAN) run $(BOX_CONFINE) \
		--tmpfs=/dev/shm:rw,nosuid,nodev,noexec,size=64m,mode=1777 \
		--entrypoint sh $(HASSFEST_IMAGE) -ceu \
		'mkdir -p /work/src; tar -xf - -C /work/src; cd /work/src; \
			/usr/src/homeassistant/script/hassfest/docker/entrypoint.sh'

validate-hacs:
	@$(PODMAN) image exists '$(HACS_IMAGE)' || { \
		printf 'HACS image is missing; run make validator-images\n' >&2; exit 1; \
	}
	@test -n "$${INPUT_GITHUB_TOKEN:-}" || { \
		printf 'INPUT_GITHUB_TOKEN is required for HACS validation\n' >&2; exit 2; \
	}
	@test -n "$${REPOSITORY:-}" -a -n "$${REPOSITORY_REF:-}" || { \
		printf 'REPOSITORY and REPOSITORY_REF are required for HACS validation\n' >&2; exit 2; \
	}
	@$(PODMAN) run $(BOX_ONLINE) \
		--env CATEGORY=integration \
		--env INPUT_GITHUB_TOKEN="$${INPUT_GITHUB_TOKEN}" \
		--env REPOSITORY="$${REPOSITORY}" \
		--env REPOSITORY_REF="$${REPOSITORY_REF}" \
		--env GITHUB_ACTOR="$${GITHUB_ACTOR:-local}" \
		--env GITHUB_REPOSITORY="$${REPOSITORY}" \
		--env GITHUB_WORKSPACE=/tmp/workspace \
		$(HACS_IMAGE)

validate: validate-local validate-actions validate-hassfest
	@if [[ -n "$${INPUT_GITHUB_TOKEN:-}" && -n "$${REPOSITORY:-}" \
		&& -n "$${REPOSITORY_REF:-}" ]]; then $(MAKE) validate-hacs; \
	else printf 'HACS validation skipped: token/repository/ref not provided\n'; fi

live: toolbox-image
	@$(BOX_ARCHIVE) | $(PODMAN) run $(BOX_ONLINE) \
		--env FMI_LIVE_BUDGET_DIR=/tmp/fmi-live-budget $(TOOLBOX_TAG) \
		bash -ceu 'mkdir -m 0700 "$${FMI_LIVE_BUDGET_DIR}"; \
			status=0; \
			python -m pytest -o addopts= --strict-config --strict-markers \
				$(PYTEST_XDIST) -m live -q || status=$$?; \
			count=0; \
			if [[ -s "$${FMI_LIVE_BUDGET_DIR}/requests" ]]; then \
				read -r count < "$${FMI_LIVE_BUDGET_DIR}/requests"; \
			fi; \
			[[ "$$count" =~ ^[0-9]+$$ ]] || { \
				printf "invalid live FMI request counter: %s\\n" "$$count" >&2; exit 1; \
			}; \
			(( count <= 12 )) || { \
				printf "live FMI request budget exceeded: %s > 12\\n" "$$count" >&2; exit 1; \
			}; \
			printf "live FMI request attempts: %s/12\\n" "$$count"; \
			exit $$status'

compatibility-stable: lock-image
	@mkdir -p $(ARTIFACTS)/compatibility
	@$(BOX_ARCHIVE) | $(PODMAN) run $(LOCK_ONLINE) \
		--env BOX_EXPORT=.artifacts/compatibility $(LOCK_TAG) \
		python .github/scripts/compatibility.py stable \
			--project pyproject.toml \
			--output .artifacts/compatibility/stable-resolved.txt \
		| tar --extract --file=- --no-same-owner

compatibility-prerelease: lock-image
	@mkdir -p $(ARTIFACTS)/compatibility
	@$(BOX_ARCHIVE) | $(PODMAN) run $(LOCK_ONLINE) \
		--env BOX_EXPORT=.artifacts/compatibility $(LOCK_TAG) \
		python .github/scripts/compatibility.py prerelease \
			--project pyproject.toml \
			--output .artifacts/compatibility/prerelease-resolved.txt \
		| tar --extract --file=- --no-same-owner

audit: toolbox-image
	$(BOX_RUN_ONLINE) python .github/scripts/dependency_audit.py

audit-raw: toolbox-image
	$(BOX_RUN_ONLINE) python -m pip_audit --local --strict

licenses: toolbox-image
	$(BOX_RUN) python -m piplicenses --format=markdown

outdated: toolbox-image
	$(BOX_RUN_ONLINE) python -m pip list --outdated

dependency-snapshot: toolbox-image
	@mkdir -p $(ARTIFACTS)
	@$(BOX_ARCHIVE) | $(PODMAN) run $(BOX_CONFINE) \
		--env BOX_EXPORT=$(DEPENDENCY_SNAPSHOT) \
		--env BOX_EXPORT_ON_SUCCESS=1 $(TOOLBOX_TAG) \
		python .github/scripts/dependency_snapshot.py \
			--output $(DEPENDENCY_SNAPSHOT) \
		| tar --extract --file=- --directory=$(ARTIFACTS) --no-same-owner

release-notes: toolbox-image
	@mkdir -p $(ARTIFACTS)
	@$(BOX_ARCHIVE) | $(PODMAN) run $(BOX_CONFINE) \
		--env BOX_EXPORT=.artifacts/release-notes.md \
		--env BOX_EXPORT_ON_SUCCESS=1 $(TOOLBOX_TAG) \
		sh -ceu 'mkdir -p .artifacts; \
			python .github/scripts/version.py notes \
				--output .artifacts/release-notes.md' \
		| tar --extract --file=- --no-same-owner

check: lint type-check bandit syntax shellcheck test-full \
	test-network-block version-check confinement-test freeze-check validate \
	dependency-snapshot

ci: validator-images check audit

clean:
	@find custom_components tests .github/scripts -type f -path '*/__pycache__/*' -delete
	@find custom_components tests .github/scripts -depth -type d -name __pycache__ -empty -delete
	@for path in .pytest_cache .ruff_cache .mypy_cache __pycache__; do \
		if [[ -d "$$path" ]]; then find "$$path" -depth -delete; fi; \
	 done
	@for path in .coverage coverage.xml $(COVERAGE_REPORT) $(COVERAGE_TOTAL) \
		$(ARTIFACTS)/coverage.xml $(ARTIFACTS)/$(COVERAGE_REPORT) \
		$(ARTIFACTS)/$(COVERAGE_TOTAL) $(ARTIFACTS)/$(DEPENDENCY_SNAPSHOT) \
		$(ARTIFACTS)/release-notes.md; do \
		if [[ -f "$$path" ]]; then unlink "$$path"; fi; \
	done
