"""Exports the real local Git history of ./source to reports/git.json (the nested .git is not
committed into the parent repo, so this file is the persisted record)."""
import json, subprocess, pathlib, datetime
ROOT = pathlib.Path(__file__).resolve().parents[1]; SRC = ROOT / 'source'
g = lambda *a: subprocess.run(['git', *a], cwd=SRC, capture_output=True, text=True, check=True).stdout.strip()
commits = [dict(zip(('hash', 'author', 'date', 'subject'), l.split('\x1f')))
           for l in g('log', '--format=%h\x1f%an\x1f%aI\x1f%s', 'main..HEAD').splitlines()]
base = g('log', '--format=%h\x1f%an\x1f%aI\x1f%s', '-1', 'main').split('\x1f')
out = {
  'exported_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
  'repository_url': 'https://github.com/LTID-rep/ltid-ai-competition-website',
  'base_branch': 'main', 'base_branch_verified': False,
  'dev_branch': g('rev-parse', '--abbrev-ref', 'HEAD'),
  'baseline_commit': dict(zip(('hash', 'author', 'date', 'subject'), base)),
  'commits': commits,
  'push': {'status': 'not_pushed', 'reason': 'No valid GitHub credentials (GH_TOKEN invalid); remote not accessible.'},
  'draft_pr': {'status': 'not_created', 'url': None, 'reason': 'Requires a pushed branch.'},
}
(ROOT / 'reports' / 'git.json').write_text(json.dumps(out, indent=2)); print(out['dev_branch'], len(commits), 'commit(s)')
