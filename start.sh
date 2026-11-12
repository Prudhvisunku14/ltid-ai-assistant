#!/usr/bin/env bash
# One-command launcher. Uses Docker if available, otherwise runs services natively.
set -e
cd "$(dirname "$0")"
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  docker compose up --build
else
  echo "Docker not available - starting natively (needs Python 3.11+ and Node 20+)"
  pip install -q -r backend/requirements.txt
  (cd frontend && npm install --no-audit --no-fund && npm run build)
  (cd backend && python -m uvicorn app.main:app --port 8001) &
  (cd evaluation-projects/prompt-a-website/source && python -m http.server 8000) &
  (cd evaluation-projects/prompt-b-weather/source && python -m weather_app --serve --port 8002) &
  (cd evaluation-projects/ltid-ai-competition-rag-final/web_demo && PORT=8008 python server.py) &
  (cd "evaluation-projects/GitHub Development Automation System/web_demo" && PORT=8009 python server.py) &
  (cd frontend && npx vite preview --port 3000 --host) &
  echo "Dashboard: http://localhost:3000   Prompt B weather demo: http://localhost:8002   LTID RAG: http://localhost:8008   devbot: http://localhost:8009"; wait
fi
