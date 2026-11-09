"""Runs the real Prompt A test suites and records the results as JSON evidence.
Usage: python scripts/run_evidence.py   (from evaluation-projects/prompt-a-website)"""
import json, re, subprocess, sys, datetime, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / 'source'
now = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')

def run(cmd):
    t = now(); p = subprocess.run(cmd, cwd=SRC, capture_output=True, text=True)
    return t, p.returncode, p.stdout + p.stderr

suites = []
t, rc, out = run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
cases = [{'name': m.group(1), 'class': m.group(2), 'status': 'passed' if m.group(3) == 'ok' else 'failed'}
         for m in re.finditer(r'^(\w+) \(([\w.]+)\) \.\.\. (\w+)', out, re.M)]
suites.append({'id': 'python-unittest', 'title': 'Python unittest (static + Playwright browser)',
               'command': 'python -m unittest discover -s tests -v', 'ran_at': t, 'exit_code': rc, 'cases': cases,
               'output_tail': out.strip().splitlines()[-6:]})
t, rc, out = run(['node', '--test', 'tests/validation.test.js'])
cases = [{'name': m.group(2).strip(), 'class': 'validation.test.js', 'status': 'passed' if m.group(1) == 'ok' else 'failed'}
         for m in re.finditer(r'^(ok|not ok) \d+ - (.+)$', out, re.M)]
suites.append({'id': 'node-test', 'title': 'Node test runner (validation + rendering logic)',
               'command': 'node --test tests/validation.test.js', 'ran_at': t, 'exit_code': rc, 'cases': cases,
               'output_tail': [l for l in out.splitlines() if l.startswith('# ')][:8]})
res = {'generated_at': now(), 'suites': suites,
       'totals': {'passed': sum(c['status'] == 'passed' for s in suites for c in s['cases']),
                  'failed': sum(c['status'] == 'failed' for s in suites for c in s['cases'])}}
(ROOT / 'reports' / 'test-results.json').write_text(json.dumps(res, indent=2))
print(res['totals'])
