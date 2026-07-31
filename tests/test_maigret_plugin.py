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
    findings = plugin._parse_csv("alice", csv_path, {})

    by_source = {f.source: f for f in findings}
    assert len(findings) == 3
    assert by_source["maigret:GitHub"].status == Status.FOUND
    assert by_source["maigret:Spotify"].status == Status.NOT_FOUND
    assert by_source["maigret:Reddit"].status == Status.ERROR
    assert by_source["maigret:Reddit"].evidence["error_reason"] == "Access denied"
    assert "profile" not in by_source["maigret:GitHub"].evidence


def test_parse_csv_merges_extracted_profile_for_matching_site(tmp_path: Path):
    csv_path = tmp_path / "report_alice.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["username", "name", "url_main", "url_user", "exists", "http_status", "error_reason"])
        writer.writerow(["alice", "GitHub", "https://github.com/", "https://github.com/alice", "Claimed", "200", ""])
        writer.writerow(["alice", "Spotify", "https://open.spotify.com/", "https://open.spotify.com/user/alice", "Available", "404", ""])

    plugin = MaigretPlugin()
    profiles = {"GitHub": {"fullname": "Alice", "image": "https://example.com/a.jpg"}}
    findings = plugin._parse_csv("alice", csv_path, profiles)

    by_source = {f.source: f for f in findings}
    assert by_source["maigret:GitHub"].evidence["profile"] == profiles["GitHub"]
    assert "profile" not in by_source["maigret:Spotify"].evidence


def test_parse_profiles_reads_ndjson_and_keeps_only_nonempty_ids(tmp_path: Path):
    json_path = tmp_path / "report_alice_ndjson.json"
    json_path.write_text(
        '{"sitename": "GitHub", "status": {"ids": {"fullname": "Alice"}}}\n'
        '{"sitename": "GitHubGist", "status": {"ids": {}}}\n'
    )

    plugin = MaigretPlugin()
    profiles = plugin._parse_profiles(json_path)

    assert profiles == {"GitHub": {"fullname": "Alice"}}


def test_build_args_defaults():
    plugin = MaigretPlugin()
    args = plugin._build_args("alice", None)
    assert args[args.index("--timeout") + 1] == "30"
    assert args[args.index("--retries") + 1] == "0"
    assert args[args.index("--json") + 1] == "ndjson"
    assert "--tags" not in args


def test_build_args_custom_values():
    plugin = MaigretPlugin()
    args = plugin._build_args("alice", {"timeout": 45, "retries": 2, "tags": "photo,gaming"})
    assert args[args.index("--timeout") + 1] == "45"
    assert args[args.index("--retries") + 1] == "2"
    assert args[args.index("--tags") + 1] == "photo,gaming"


def test_build_args_clamps_out_of_range_values():
    plugin = MaigretPlugin()
    args = plugin._build_args("alice", {"timeout": 999, "retries": 99})
    assert args[args.index("--timeout") + 1] == "60"
    assert args[args.index("--retries") + 1] == "3"


def test_build_args_ignores_blank_tags():
    plugin = MaigretPlugin()
    args = plugin._build_args("alice", {"tags": "   "})
    assert "--tags" not in args
