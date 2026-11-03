@echo off
cd /d "%~dp0backend"
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -q -r requirements.txt
python seed_demo.py
echo Abra http://localhost:8000
uvicorn app.main:app --port 8000
