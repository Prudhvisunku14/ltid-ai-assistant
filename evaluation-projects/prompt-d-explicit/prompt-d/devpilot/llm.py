"""LLM access. OpenAI via plain HTTPS (no SDK) plus a scripted stand-in for tests/demos."""
import json, os, urllib.request


class LLMUnavailable(Exception):
    pass


class OpenAILLM:
    def __init__(self, model=None, api_key=None, timeout=120):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model or os.environ.get("DEVPILOT_MODEL", "gpt-4o")
        self.timeout = timeout
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}  # measured, not estimated

    def complete(self, system, user):
        if not self.api_key:
            raise LLMUnavailable("OPENAI_API_KEY is not set")
        body = json.dumps({"model": self.model, "messages": [
            {"role": "system", "content": system}, {"role": "user", "content": user}]}).encode()
        req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=body, headers={
            "Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read())
        except Exception as e:
            raise LLMUnavailable(f"OpenAI request failed: {e}")
        u = data.get("usage", {})
        self.usage["prompt_tokens"] += u.get("prompt_tokens", 0)
        self.usage["completion_tokens"] += u.get("completion_tokens", 0)
        self.usage["calls"] += 1
        return data["choices"][0]["message"]["content"]


class ScriptedLLM:
    """Returns pre-written replies in order. Used ONLY for tests and the labelled offline demo."""
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def complete(self, system, user):
        self.calls.append((system, user))
        if not self.replies:
            raise LLMUnavailable("scripted LLM exhausted")
        return self.replies.pop(0)
