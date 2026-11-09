FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
ENV EVAL_PROJECTS_DIR=/data/evaluation-projects
EXPOSE 8001
HEALTHCHECK --interval=15s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8001/health')"
# Non-root, read-only data mount (see docker-compose.yml)
RUN useradd -m app && chown -R app /srv
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
