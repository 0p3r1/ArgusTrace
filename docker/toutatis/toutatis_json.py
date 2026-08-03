import json
import os
import sys

from toutatis.core import advanced_lookup, getInfo

# Session cookie travels via env var, never argv (argv is visible to anyone
# who can list processes on the host for as long as the container runs;
# env vars still require a deliberate `docker inspect`/`/proc` read, a
# meaningfully smaller exposure window for a credential this sensitive).


def scan(username: str, session_id: str) -> dict:
    # toutatis's own error handling doesn't cover every real response shape
    # Instagram can send back (verified directly: a rate-limit response body
    # missing the keys it expects raises an uncaught KeyError, not a clean
    # error dict) — never let that crash surface as a bare traceback.
    try:
        profile = getInfo(username, session_id, searchType="username")
    except Exception as e:
        profile = {"user": None, "error": f"toutatis crashed: {e}"}

    try:
        lookup = advanced_lookup(username)
    except Exception as e:
        lookup = {"user": None, "error": f"toutatis crashed: {e}"}

    return {"profile": profile, "lookup": lookup}


if __name__ == "__main__":
    username = sys.argv[1]
    session_id = os.environ.get("IG_SESSIONID", "")
    print(json.dumps(scan(username, session_id)))
