FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

RUN pip install --no-cache-dir ignorant==1.2

COPY docker/ignorant/ignorant_json.py /ignorant_json.py

RUN useradd --create-home --uid 1000 ignorant
USER ignorant
WORKDIR /home/ignorant

ENTRYPOINT ["python3", "/ignorant_json.py"]
