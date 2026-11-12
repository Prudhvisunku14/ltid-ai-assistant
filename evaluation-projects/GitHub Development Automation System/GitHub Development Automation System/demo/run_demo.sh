#!/usr/bin/env bash
# End-to-end demo on a fictional repo. Works offline (scripted "GPT"). Needs: python3 (3.9+), git.
set -euo pipefail
cd "$(dirname "$0")/.."
WORK="${1:-/tmp/devbot_demo}"
rm -rf "$WORK"; mkdir -p "$WORK"
python3 demo/make_demo_repo.py "$WORK/bookshop-api"
REQ="Add a 10% bulk discount to calculate_total for orders of 10 or more books, and add tests"

echo; echo "############ PART 1: DRY-RUN (default) - repo must stay untouched ############"
python3 -m devbot run --repo "$WORK/bookshop-api" --request "$REQ" --llm mock --yes --out-dir "$WORK/out"
git -C "$WORK/bookshop-api" branch --list; git -C "$WORK/bookshop-api" status --short

echo; echo "############ PART 2: LIVE - real branch + commit + local draft PR ############"
python3 -m devbot run --repo "$WORK/bookshop-api" --request "$REQ" --llm mock --yes --live --out-dir "$WORK/out"
git -C "$WORK/bookshop-api" branch --list; git -C "$WORK/bookshop-api" log --oneline -3
echo "main branch untouched / not merged:"; git -C "$WORK/bookshop-api" log main --oneline
ls "$WORK/out"
