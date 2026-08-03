# PyPI's latest published release (1.31) predates a real API cleanup on
# GitHub (structured error dicts, proper status-code handling) — verified by
# actually running 1.31 and hitting a crash the newer source doesn't have.
# No git tags exist for this repo, so pin to the exact verified commit.
FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git clone https://github.com/megadose/toutatis.git . \
    && git checkout d99967155e59966a560877148273ca0ff9f28508 \
    && pip install --no-cache-dir .

COPY docker/toutatis/toutatis_json.py /toutatis_json.py

RUN useradd --create-home --uid 1000 toutatis
USER toutatis
WORKDIR /home/toutatis

ENTRYPOINT ["python3", "/toutatis_json.py"]
