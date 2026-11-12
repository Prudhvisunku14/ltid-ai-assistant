"""LLM backends: OpenAI GPT (real) and a scripted Mock (offline demo / tests)."""
from __future__ import annotations
import importlib.util
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any, Protocol


class LLM(Protocol):
    name: str
    def complete_json(self, task: str, system: str, user: str) -> dict[str, Any]: ...


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return json.loads(text)


class OpenAILLM:
    """Calls the OpenAI Chat Completions API using only the standard library."""

    def __init__(self, api_key: str | None = None, model: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set (or use --llm mock for the offline demo)")
        self.model = model or os.environ.get("DEVBOT_MODEL", "gpt-4o-mini")
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.name = f"openai:{self.model}"

    def complete_json(self, task: str, system: str, user: str) -> dict[str, Any]:
        body = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.load(resp)
        return _parse_json(data["choices"][0]["message"]["content"])


class MockLLM:
    """Deterministic stand-in for GPT. Replays a SCRIPT dict: task -> response (or list of responses)."""

    def __init__(self, script: dict[str, Any]):
        self.script = {k: (list(v) if isinstance(v, list) else v) for k, v in script.items()}
        self.name = "mock (scripted, offline)"
        self.calls: list[str] = []

    @classmethod
    def from_file(cls, path: str | Path) -> "MockLLM":
        spec = importlib.util.spec_from_file_location("mock_script", str(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return cls(mod.SCRIPT)

    def complete_json(self, task: str, system: str, user: str) -> dict[str, Any]:
        self.calls.append(task)
        if task not in self.script:
            raise RuntimeError(f"MockLLM has no scripted response for task {task!r}")
        r = self.script[task]
        if isinstance(r, list):
            if not r:
                raise RuntimeError(f"MockLLM ran out of scripted responses for {task!r}")
            return r.pop(0)
        return r
