# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

# Project source is streamed into a private tmpfs. No check receives a bind
# mount of the checkout, Git metadata, host virtual environments, or sockets.

PODMAN ?= podman
ARTIFACTS := .artifacts
IMAGE_ARTIFACTS := $(ARTIFACTS)/images

TOOLBOX_CONTEXT := containers/toolbox/Containerfile containers/toolbox/entrypoint.sh
TOOLBOX_KEY = $(shell cat $(TOOLBOX_CONTEXT) requirements-dev.txt | sha256sum | cut -c1-16)
TOOLBOX_TAG = localhost/fmi-hass-custom-toolbox:$(TOOLBOX_KEY)

LOCK_CONTEXT := containers/toolbox/Containerfile containers/toolbox/entrypoint.sh
LOCK_KEY = $(shell cat $(LOCK_CONTEXT) | sha256sum | cut -c1-16)
LOCK_TAG = localhost/fmi-hass-custom-lock:$(LOCK_KEY)

BOX_CONFINE = \
	--rm \
	--interactive \
	--network=none \
	--userns=auto:size=2048 \
	--security-opt=no-new-privileges \
	--cap-drop=ALL \
	--read-only \
	--read-only-tmpfs=false \
	--ipc=private \
	--pid=private \
	--uts=private \
	--cgroupns=private \
	--systemd=false \
	--no-hosts \
	--unsetenv-all \
	--umask=077 \
	--pids-limit=1024 \
	--memory=8g \
	--memory-swap=8g \
	--ulimit=nofile=4096:4096 \
	--log-driver=none \
	--timeout=1800 \
	--pull=never \
	--label=fmi-hass-custom.owner \
	--tmpfs=/tmp:rw,nosuid,nodev,size=512m,mode=1777 \
	--tmpfs=/work:rw,exec,nosuid,nodev,size=2g,mode=1777 \
	--env HOME=/tmp/home \
	--env LANG=C.UTF-8 \
	--env LC_ALL=C.UTF-8 \
	--env TZ=UTC \
	--env PATH=/usr/local/bin:/usr/bin:/bin

BOX_ONLINE = $(subst --network=none,--network=slirp4netns,$(BOX_CONFINE))

# Hashing every distribution in the Home Assistant development graph exceeded
# a measured 4 GiB /tmp. Keep the larger workspace confined to online resolver
# runs; ordinary checks retain the reference limits above.
LOCK_ONLINE = $(filter-out --tmpfs=/tmp:% --tmpfs=/work:%,$(BOX_ONLINE)) \
	--tmpfs=/tmp:rw,nosuid,nodev,size=16g,mode=1777 \
	--tmpfs=/work:rw,exec,nosuid,nodev,size=4g,mode=1777

BOX_ARCHIVE = git ls-files --cached --others --exclude-standard -z \
	| while IFS= read -r -d '' path; do \
		if [[ -e "$$path" || -L "$$path" ]]; then printf '%s\0' "$$path"; fi; \
	done \
	| sort -z \
	| tar --create --file=- --null --verbatim-files-from --files-from=-

BOX_RUN = @$(BOX_ARCHIVE) | $(PODMAN) run $(BOX_CONFINE) $(TOOLBOX_TAG)
BOX_RUN_ONLINE = @$(BOX_ARCHIVE) | $(PODMAN) run $(BOX_ONLINE) $(TOOLBOX_TAG)

.PHONY: images toolbox-image lock-image image-key image-save \
	image-save-toolbox image-save-resolver image-load image-load-toolbox \
	image-load-resolver doctor clean-containers

images: toolbox-image lock-image

toolbox-image:
	@$(PODMAN) image exists $(TOOLBOX_TAG) || { \
		printf 'building %s\n' '$(TOOLBOX_TAG)' >&2; \
		$(PODMAN) build --quiet --pull=missing --tag $(TOOLBOX_TAG) \
			--label=fmi-hass-custom.owner --target dev \
			--file containers/toolbox/Containerfile . >/dev/null; \
	}

lock-image:
	@$(PODMAN) image exists $(LOCK_TAG) || { \
		printf 'building %s\n' '$(LOCK_TAG)' >&2; \
		$(PODMAN) build --quiet --pull=missing --tag $(LOCK_TAG) \
			--label=fmi-hass-custom.owner --target lock \
			--file containers/toolbox/Containerfile . >/dev/null; \
	}

image-key:
	@printf 'toolbox=%s\nresolver=%s\n' '$(TOOLBOX_KEY)' '$(LOCK_KEY)'

define save_image
	@mkdir -p $(IMAGE_ARTIFACTS)
	@temporary='$(1).tmp.'$$$$; \
		trap 'rm -f "$$temporary"' EXIT; \
		$(PODMAN) save --quiet --format oci-archive \
			--output "$$temporary" '$(2)'; \
		mv -f "$$temporary" '$(1)'
endef

define load_image
	@test -r '$(1)' || { \
		printf 'cached image archive is missing: %s\n' '$(1)' >&2; exit 1; \
	}
	@$(PODMAN) load --quiet --input '$(1)' >/dev/null
	@$(PODMAN) image exists '$(2)' || { \
		printf 'cached archive did not restore expected image: %s\n' '$(2)' >&2; \
		exit 1; \
	}
endef

image-save: image-save-toolbox image-save-resolver

image-save-toolbox: toolbox-image
	$(call save_image,$(IMAGE_ARTIFACTS)/toolbox.tar,$(TOOLBOX_TAG))

image-save-resolver: lock-image
	$(call save_image,$(IMAGE_ARTIFACTS)/resolver.tar,$(LOCK_TAG))

image-load: image-load-toolbox image-load-resolver

image-load-toolbox:
	$(call load_image,$(IMAGE_ARTIFACTS)/toolbox.tar,$(TOOLBOX_TAG))

image-load-resolver:
	$(call load_image,$(IMAGE_ARTIFACTS)/resolver.tar,$(LOCK_TAG))

doctor:
	@for command in git sha256sum tar $(PODMAN); do \
		command -v "$$command" >/dev/null 2>&1 || { \
			printf 'required command not found: %s\n' "$$command" >&2; exit 1; \
		}; \
	done
	@$(PODMAN) info >/dev/null 2>&1 || { \
		printf 'podman is unavailable\n' >&2; exit 1; \
	}
	@rootless=$$($(PODMAN) info --format '{{.Host.Security.Rootless}}'); \
		if [[ "$$rootless" != true ]]; then \
			printf 'rootless podman is required, got %s\n' "$$rootless" >&2; \
			exit 1; \
		fi
	@printf '%s\n' \
		"podman   $$($(PODMAN) version --format '{{.Client.Version}}')" \
		'rootless yes' \
		'toolbox  $(TOOLBOX_TAG)' \
		'resolver $(LOCK_TAG)'

clean-containers:
	@stale=$$($(PODMAN) ps --all --quiet \
		--filter 'label=fmi-hass-custom.owner' 2>/dev/null); \
		if [[ -n "$$stale" ]]; then \
			$(PODMAN) rm --force --time 5 $$stale >/dev/null; \
		fi
	@images=$$($(PODMAN) images --quiet \
		--filter 'reference=localhost/fmi-hass-custom-*' 2>/dev/null); \
		if [[ -n "$$images" ]]; then \
			$(PODMAN) rmi --force $$images >/dev/null; \
		fi
