#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../../.." && pwd)
exec "${PYTHON:-python3}" "$repo/scripts/build_release.py" spark "$@"
