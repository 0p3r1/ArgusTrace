# Mirrors the official Dockerfile (github.com/laramies/theHarvester/Dockerfile)
# but pins to a released tag via git clone and exposes the `theHarvester` CLI
# entrypoint instead of the restfulHarvest REST server.
FROM python:3.14-slim-trixie@sha256:cea0e6040540fb2b965b6e7fb5ffa00871e632eef63719f0ea54bca189ce14a6

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 -s /bin/bash theharvester

WORKDIR /app
RUN git clone --depth 1 --branch 4.11.1 https://github.com/laramies/theHarvester.git .

RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    UV_PROJECT_ENVIRONMENT=/usr/local uv sync --locked --no-dev --no-cache --compile-bytecode

USER theharvester

ENTRYPOINT ["theHarvester"]
