import json
import sys

import httpx
import trio
from holehe.core import get_functions, import_submodules, launch_module


class _Args:
    def __init__(self, no_password_recovery: bool):
        self.nopasswordrecovery = no_password_recovery


async def scan(email: str, timeout: int, no_password_recovery: bool) -> list[dict]:
    modules = import_submodules("holehe.modules")
    websites = get_functions(modules, _Args(no_password_recovery))
    client = httpx.AsyncClient(timeout=timeout)
    out = []
    async with trio.open_nursery() as nursery:
        for website in websites:
            nursery.start_soon(launch_module, website, email, client, out)
    await client.aclose()
    return sorted(out, key=lambda i: i["name"])


if __name__ == "__main__":
    email = sys.argv[1]
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    no_password_recovery = "-NP" in sys.argv[3:]
    results = trio.run(scan, email, timeout, no_password_recovery)
    print(json.dumps(results))
