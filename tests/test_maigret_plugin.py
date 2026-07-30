import csv
from pathlib import Path

from argustrace.core.models import Status
from argustrace.plugins.maigret_plugin import MaigretPlugin


async def test_invalid_entity_returns_error_without_touching_docker():
    plugin = MaigretPlugin()
    findings = await plugin.run("not a valid username!")

    assert len(findings) == 1
    assert findings[0].status == Status.ERROR
    assert "invalid entity" in findings[0].evidence["reason"]


def test_parse_csv_maps_every_maigret_status(tmp_path: Path):
    csv_path = tmp_path / "report_alice.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["username", "name", "url_main", "url_user", "exists", "http_status", "error_reason"])
        writer.writerow(["alice", "GitHub", "https://github.com/", "https://github.com/alice", "Claimed", "200", ""])
        writer.writerow(["alice", "Spotify", "https://open.spotify.com/", "https://open.spotify.com/user/alice", "Available", "404", ""])
        writer.writerow(["alice", "Reddit", "https://www.reddit.com/", "https://www.reddit.com/user/alice", "Unknown", "403", "Access denied"])

    plugin = MaigretPlugin()
    findings = plugin._parse_csv("alice", csv_path)

    by_source = {f.source: f for f in findings}
    assert len(findings) == 3
    assert by_source["maigret:GitHub"].status == Status.FOUND
    assert by_source["maigret:Spotify"].status == Status.NOT_FOUND
    assert by_source["maigret:Reddit"].status == Status.ERROR
    assert by_source["maigret:Reddit"].evidence["error_reason"] == "Access denied"
