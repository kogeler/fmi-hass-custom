#!/usr/bin/env bash

# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

# Verify confinement before unpacking the source archive. BOX_EXPORT is a
# space-separated allowlist of paths returned as a tar stream on stdout.

set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
    printf 'toolbox: running as root inside the container\n' >&2
    exit 1
fi
if ! grep -Eq '^CapEff:[[:space:]]+0+$' /proc/self/status; then
    printf 'toolbox: effective capabilities are not empty\n' >&2
    exit 1
fi
if ! grep -Eq '^NoNewPrivs:[[:space:]]+1$' /proc/self/status; then
    printf 'toolbox: NoNewPrivs is not set\n' >&2
    exit 1
fi
if ! grep -Eq '^Seccomp:[[:space:]]+2$' /proc/self/status; then
    printf 'toolbox: seccomp filtering is not active\n' >&2
    exit 1
fi

(( $# )) || {
    printf 'toolbox: no command given\n' >&2
    exit 2
}

mkdir -p "$HOME"
chmod 0700 "$HOME"

[[ ! -e /work/src ]] || {
    printf 'toolbox: unexpected pre-existing work tree\n' >&2
    exit 1
}
mkdir -p /work/src /work/out
chmod 0700 /work/src /work/out
tar --extract --file=- --directory=/work/src
cd /work/src

if [[ -z "${BOX_EXPORT:-}" ]]; then
    exec "$@"
fi

status=0
"$@" >&2 || status=$?

if (( status != 0 )) && [[ "${BOX_EXPORT_ON_SUCCESS:-0}" == 1 ]]; then
    tar --create --file=- --files-from=/dev/null
    exit "$status"
fi

exported=()
for path in ${BOX_EXPORT}; do
    if [[ -e "$path" ]]; then exported+=("$path"); fi
done
if (( ${#exported[@]} )); then
    tar --create --file=- --directory=/work/src -- "${exported[@]}"
else
    tar --create --file=- --files-from=/dev/null
fi
exit "$status"
