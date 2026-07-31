from argustrace.core.models import Finding, Status


class MockPlugin:
    name = "mock"
    supported_entities = ["email", "username"]

    async def run(self, entity: str, options: dict | None = None) -> list[Finding]:
        return [
            Finding(
                entity=entity,
                entity_type="username",
                source="mock",
                status=Status.FOUND,
                url="https://example.com/" + entity,
                evidence={"note": "hardcoded match"},
            ),
            Finding(
                entity=entity,
                entity_type="username",
                source="mock",
                status=Status.NOT_FOUND,
            ),
        ]
