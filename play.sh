#!/usr/bin/env bash
# Play from a source checkout on macOS or Linux.
set -euo pipefail
cd "$(dirname "$0")"
exec python3 run.py
