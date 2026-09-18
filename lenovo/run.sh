#!/bin/bash
# Match Intel — pipeline runner
# Usage: ./run.sh [pipeline|stage1|stage2|stage3|email|...] [--date YYYY-MM-DD]
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"
source venv/bin/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null || true
export PYTHONPATH="$DIR"
python3 pipeline/orchestrator.py "$@"
