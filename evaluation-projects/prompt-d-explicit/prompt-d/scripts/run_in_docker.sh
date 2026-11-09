#!/usr/bin/env bash
# Sandboxed run: no network, no capabilities, read-only root FS, no secrets passed in.
set -euo pipefail
docker build -t devpilot .
docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges --read-only \
  --tmpfs /tmp --tmpfs /app/out --pids-limit 256 --memory 512m devpilot "${@:-python -m unittest discover -s tests -t .}"
