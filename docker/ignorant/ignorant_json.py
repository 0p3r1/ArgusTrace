import json
import sys

import httpx
import trio
from ignorant.core import get_functions, import_submodules, launch_module


async def scan(country_code: str, phone: str, timeout: int) -> list[dict]:
    modules = import_submodules("ignorant.modules")
    websites = get_functions(modules)
    client = httpx.AsyncClient(timeout=timeout)
    out = []
    async with trio.open_nursery() as nursery:
        for website in websites:
            nursery.start_soon(launch_module, website, phone, country_code, client, out)
    await client.aclose()
    return sorted(out, key=lambda i: i["name"])


if __name__ == "__main__":
    country_code, phone = sys.argv[1], sys.argv[2]
    timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    results = trio.run(scan, country_code, phone, timeout)
    print(json.dumps(results))
