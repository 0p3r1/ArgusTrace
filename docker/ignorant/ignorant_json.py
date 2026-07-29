import json
import sys

import httpx
import trio
from ignorant.core import get_functions, import_submodules, launch_module


async def scan(country_code: str, phone: str) -> list[dict]:
    modules = import_submodules("ignorant.modules")
    websites = get_functions(modules)
    client = httpx.AsyncClient(timeout=10)
    out = []
    async with trio.open_nursery() as nursery:
        for website in websites:
            nursery.start_soon(launch_module, website, phone, country_code, client, out)
    await client.aclose()
    return sorted(out, key=lambda i: i["name"])


if __name__ == "__main__":
    country_code, phone = sys.argv[1], sys.argv[2]
    results = trio.run(scan, country_code, phone)
    print(json.dumps(results))
