#!/usr/bin/env sh
set -e
cd "$(dirname "$0")/backend"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
python seed_demo.py || true
echo "Abra http://localhost:8000"
uvicorn app.main:app --port 8000
