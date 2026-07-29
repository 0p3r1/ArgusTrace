from argustrace.core.models import Status
from argustrace.plugins.mock_plugin import MockPlugin


def test_mock_plugin_declares_supported_entities():
    plugin = MockPlugin()
    assert plugin.name == "mock"
    assert plugin.supported_entities == ["email", "username"]


async def test_mock_plugin_run_returns_one_found_and_one_not_found():
    plugin = MockPlugin()
    findings = await plugin.run("alice")

    assert len(findings) == 2
    statuses = {f.status for f in findings}
    assert statuses == {Status.FOUND, Status.NOT_FOUND}
    assert all(f.entity == "alice" for f in findings)
