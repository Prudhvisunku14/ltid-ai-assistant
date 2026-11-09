@echo off
cd /d %~dp0
docker info >nul 2>&1
if %errorlevel%==0 ( docker compose up --build & goto :eof )
echo Docker not running - starting natively (needs Python 3.11+ and Node 20+)
pip install -q -r backend\requirements.txt
cd frontend && call npm install --no-audit --no-fund && call npm run build && cd ..
start "backend" cmd /c "cd backend && python -m uvicorn app.main:app --port 8001"
start "preview" cmd /c "cd evaluation-projects\prompt-a-website\source && python -m http.server 8000"
start "weather" cmd /c "cd evaluation-projects\prompt-b-weather\source && python -m weather_app --serve --port 8002"
start "frontend" cmd /c "cd frontend && npx vite preview --port 3000 --host"
echo Dashboard: http://localhost:3000   Prompt B weather demo: http://localhost:8002
