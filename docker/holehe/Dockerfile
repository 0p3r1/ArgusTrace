FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

RUN pip install --no-cache-dir holehe==1.61

# holehe's own CLI (maincore()) unconditionally calls check_update() on
# every invocation — a live PyPI request that, if a newer version exists,
# shells out to `pip install --upgrade holehe` and exits before scanning
# anything. That means every run phones home regardless, and the day
# upstream ships 1.62 this image starts failing closed until someone
# notices and re-pins. holehe_json.py bypasses maincore() entirely and
# drives the same module functions directly (same pattern already used
# for ignorant, which has the identical problem upstream).
COPY docker/holehe/holehe_json.py /holehe_json.py

RUN useradd --create-home --uid 1000 holehe
USER holehe
WORKDIR /home/holehe

ENTRYPOINT ["python3", "/holehe_json.py"]
