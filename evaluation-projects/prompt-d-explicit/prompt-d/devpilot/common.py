import json, subprocess, urllib.request, urllib.error


def run_cmd(cmd, timeout=20, cwd=None):
    """Run a command; never raises. Returns (returncode, stdout, stderr). rc=127 if missing, 124 on timeout."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"{cmd[0]}: not found"
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"


def http_get(url, headers=None, timeout=8):
    """Returns (status, headers_dict, body). status=0 when the network is unreachable."""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")
    except Exception as e:  # DNS failure, proxy deny, timeout ...
        return 0, {}, str(e)


def extract_json(text):
    """Parse a JSON object from an LLM reply, tolerating ``` fences and prose."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        a, b = t.find("{"), t.rfind("}")
        if a >= 0 and b > a:
            return json.loads(t[a:b + 1])
        raise
