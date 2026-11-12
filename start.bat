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
start "rag" cmd /c "cd evaluation-projects\ltid-ai-competition-rag-final\web_demo && set PORT=8008&& python server.py"
start "devbot" cmd /c "cd evaluation-projects\GitHub Development Automation System\web_demo && set PORT=8009&& python server.py"
start "frontend" cmd /c "cd frontend && npx vite preview --port 3000 --host"
echo Dashboard: http://localhost:3000   Prompt B weather demo: http://localhost:8002   LTID RAG: http://localhost:8008   devbot: http://localhost:8009
