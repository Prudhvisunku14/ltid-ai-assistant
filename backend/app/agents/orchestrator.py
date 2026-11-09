"""Agent orchestration layer (kept separate from the frontend).
This is an integration STRUCTURE: it reports which providers are configured and does not call any
paid API unless credentials are supplied. The Prompt A evidence in this repo was produced in a
Claude Code session, not by this module."""
from ..config import OPENAI_CONFIGURED, GITHUB_CONFIGURED, N8N_CONFIGURED

def integrations() -> list[dict]:
    return [
      {"id": "openai", "name": "OpenAI API", "role": "Reasoning and orchestration", "configured": OPENAI_CONFIGURED, "env": "OPENAI_API_KEY"},
      {"id": "github", "name": "GitHub", "role": "Branch, push, draft pull request", "configured": GITHUB_CONFIGURED, "env": "GITHUB_TOKEN"},
      {"id": "opencode", "name": "OpenCode", "role": "Coding execution tool", "configured": False, "env": "(external CLI)"},
      {"id": "n8n", "name": "n8n", "role": "Workflow orchestration", "configured": N8N_CONFIGURED, "env": "N8N_WEBHOOK_URL"},
    ]

def status() -> dict:
    return {"state": "idle", "active_tasks": 0, "mode": "evidence-viewer",
            "message": "No live agent run is active. The dashboard shows recorded evidence."}
