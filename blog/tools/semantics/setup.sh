#!/bin/sh
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
python3.12 -m venv "$repo/.venv-semantics"
PIP_CACHE_DIR="$repo/var/semantics/pip-cache" "$repo/.venv-semantics/bin/python" -m pip install -r "$repo/tools/semantics/runtime-lock.txt"
"$repo/.venv-semantics/bin/python" -m pip check
