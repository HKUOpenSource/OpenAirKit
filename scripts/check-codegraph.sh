#!/usr/bin/env bash
set -euo pipefail
test -f codegraph.json
python3 -m json.tool codegraph.json >/dev/null
echo "CodeGraph configuration is valid"
