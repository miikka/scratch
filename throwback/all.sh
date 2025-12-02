#!/usr/bin/env bash

set -euo pipefail

VAULT="$HOME/Documents/Obsidian"
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
python3 "$SCRIPT_DIR/throwback.py" "$VAULT"
python3 "$SCRIPT_DIR/masto_throwback.py" "$VAULT"
