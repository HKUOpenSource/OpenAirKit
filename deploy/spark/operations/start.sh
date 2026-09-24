#!/bin/sh
set -eu
if [ "$#" -ne 0 ]; then
    echo "This entrypoint accepts no arguments." >&2
    exit 2
fi
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec /usr/bin/python3 -I "$SCRIPT_DIR/platformctl.py" start
