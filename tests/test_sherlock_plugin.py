import csv
from pathlib import Path

from argustrace.core.models import Status
from argustrace.plugins.sherlock_plugin import SherlockPlugin


async def test_invalid_entity_returns_error_without_touching_docker():
    plugin = SherlockPlugin()
    findings = await plugin.run("not a valid username!")

    assert len(findings) == 1
    assert findings[0].status == Status.ERROR
    assert "invalid entity" in findings[0].evidence["reason"]


def test_parse_csv_maps_every_sherlock_status(tmp_path: Path):
    csv_path = tmp_path / "alice.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["username", "name", "url_main", "url_user", "exists", "http_status", "response_time_s"])
        writer.writerow(["alice", "GitHub", "https://github.com/", "https://github.com/alice", "Claimed", "200", "0.1"])
        writer.writerow(["alice", "SomeSite", "https://somesite.com/", "", "Available", "200", "0.2"])
        writer.writerow(["alice", "Flaky", "https://flaky.com/", "", "Unknown", "?", ""])
        writer.writerow(["alice", "Blocked", "https://blocked.com/", "", "WAF", "403", "0.3"])
        writer.writerow(["alice", "BadFormat", "https://badformat.com/", "", "Illegal", "", ""])

    plugin = SherlockPlugin()
    findings = plugin._parse_csv("alice", csv_path)

    by_source = {f.source: f for f in findings}
    assert len(findings) == 4  # "Illegal" row is dropped
    assert by_source["sherlock:GitHub"].status == Status.FOUND
    assert by_source["sherlock:GitHub"].url == "https://github.com/alice"
    assert by_source["sherlock:SomeSite"].status == Status.NOT_FOUND
    assert by_source["sherlock:Flaky"].status == Status.ERROR
    assert by_source["sherlock:Blocked"].status == Status.ERROR
