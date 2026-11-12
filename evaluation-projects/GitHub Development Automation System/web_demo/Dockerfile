# Runtime image for the devbot web interface: Python + git (devbot drives the git CLI). Nothing else is installed.
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*
