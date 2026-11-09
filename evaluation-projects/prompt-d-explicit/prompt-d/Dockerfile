FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git nodejs && rm -rf /var/lib/apt/lists/* \
 && useradd -m agent
WORKDIR /app
COPY . /app
RUN chown -R agent /app
USER agent
CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-t", "."]
