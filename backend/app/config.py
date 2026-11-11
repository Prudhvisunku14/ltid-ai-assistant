import os
from pathlib import Path

def _root() -> Path:
    env = os.getenv("EVAL_PROJECTS_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "evaluation-projects"

EVAL_ROOT = _root()
PROMPT_A = EVAL_ROOT / "prompt-a-website"
PROMPT_B = EVAL_ROOT / "prompt-b-weather"
PROMPT_D = EVAL_ROOT / "prompt-d-explicit" / "prompt-d"
INVENTORY = EVAL_ROOT / "inventory-system"
PREVIEW_URL = os.getenv("PROMPT_A_PREVIEW_URL", "http://localhost:8000")
PROMPT_B_PREVIEW_URL = os.getenv("PROMPT_B_PREVIEW_URL", "http://localhost:8002")
INVENTORY_PREVIEW_URL = os.getenv("INVENTORY_PREVIEW_URL", "http://localhost:8003")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",") if o.strip()]
OPENAI_CONFIGURED = bool(os.getenv("OPENAI_API_KEY"))
GITHUB_CONFIGURED = bool(os.getenv("GITHUB_TOKEN"))
N8N_CONFIGURED = bool(os.getenv("N8N_WEBHOOK_URL"))
