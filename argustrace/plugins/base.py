from typing import Protocol

from argustrace.core.models import Finding


class Plugin(Protocol):
    name: str
    supported_entities: list[str]

    async def run(self, entity: str, options: dict | None = None) -> list[Finding]:
        ...
