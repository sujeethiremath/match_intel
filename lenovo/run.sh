#!/bin/bash
# Match Intel — pipeline runner
# Usage: ./run.sh [pipeline|stage1|stage2|stage3|email|...] [--date YYYY-MM-DD]
cd /home/superman/match-intel
source venv/bin/activate
export PYTHONPATH=/home/superman/match-intel
python3 pipeline/orchestrator.py "$@"
