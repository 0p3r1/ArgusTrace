import csv
from pathlib import Path

import pytest

from argustrace.core.models import Status
from argustrace.plugins import maigret_plugin
from argustrace.plugins._docker_runner import DockerRunResult
from argustrace.plugins.maigret_plugin import MaigretPlugin, generate_report


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
    profile = {"fullname": "Alice", "image": "https://example.com/a.jpg"}
    site_extras = {"GitHub": {"profile": profile}}
    findings = plugin._parse_csv("alice", csv_path, site_extras)

    by_source = {f.source: f for f in findings}
    assert by_source["maigret:GitHub"].evidence["profile"] == profile
    assert "profile" not in by_source["maigret:Spotify"].evidence


def test_parse_csv_merges_related_ids_for_matching_site(tmp_path: Path):
    csv_path = tmp_path / "report_alice.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["username", "name", "url_main", "url_user", "exists", "http_status", "error_reason"])
        writer.writerow(["alice", "Wikipedia", "https://wikipedia.org/", "https://wikipedia.org/wiki/Alice", "Claimed", "200", ""])

    plugin = MaigretPlugin()
    related = {"usernames": {"Alicia": "username"}, "links": ["https://example.com/alicia"]}
    findings = plugin._parse_csv("alice", csv_path, {"Wikipedia": {"related_ids": related}})

    assert findings[0].evidence["related_ids"] == related


def test_parse_site_extras_reads_ndjson_and_keeps_only_nonempty_ids(tmp_path: Path):
    json_path = tmp_path / "report_alice_ndjson.json"
    json_path.write_text(
        '{"sitename": "GitHub", "status": {"ids": {"fullname": "Alice"}}}\n'
        '{"sitename": "GitHubGist", "status": {"ids": {}}}\n'
    )

    plugin = MaigretPlugin()
    extras = plugin._parse_site_extras("alice", json_path)

    assert extras == {"GitHub": {"profile": {"fullname": "Alice"}}}


def test_parse_site_extras_drops_exact_self_match_but_keeps_other_casing(tmp_path: Path):
    json_path = tmp_path / "report_alice_ndjson.json"
    json_path.write_text(
        '{"sitename": "SelfOnly", "status": {"ids": {}}, "ids_usernames": {"alice": "username"}, "ids_links": []}\n'
        '{"sitename": "DifferentCase", "status": {"ids": {}}, "ids_usernames": {"Alice": "username"}, "ids_links": []}\n'
        '{"sitename": "WithLinks", "status": {"ids": {}}, "ids_usernames": {}, "ids_links": ["https://example.com/alice2"]}\n'
    )

    plugin = MaigretPlugin()
    extras = plugin._parse_site_extras("alice", json_path)

    assert "SelfOnly" not in extras
    assert extras["DifferentCase"]["related_ids"]["usernames"] == {"Alice": "username"}
    assert extras["WithLinks"]["related_ids"]["links"] == ["https://example.com/alice2"]


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


def test_build_args_exclude_tags():
    plugin = MaigretPlugin()
    args = plugin._build_args("alice", {"exclude_tags": "adult,dating"})
    assert args[args.index("--exclude-tags") + 1] == "adult,dating"


async def test_generate_report_rejects_invalid_entity_without_touching_docker():
    with pytest.raises(ValueError, match="invalid entity"):
        await generate_report("not a valid username!", "html")


async def test_generate_report_rejects_unsupported_format_without_touching_docker():
    with pytest.raises(ValueError, match="unsupported report format"):
        await generate_report("alice", "pdf")


def test_build_args_ignores_blank_exclude_tags():
    plugin = MaigretPlugin()
    args = plugin._build_args("alice", {"exclude_tags": "   "})
    assert "--exclude-tags" not in args


def test_build_args_enrich_off_by_default():
    plugin = MaigretPlugin()
    args = plugin._build_args("alice", None)
    assert "--enrich" not in args


def test_build_args_enrich_flag():
    plugin = MaigretPlugin()
    args = plugin._build_args("alice", {"enrich": True})
    assert "--enrich" in args


async def test_run_still_returns_findings_when_maigret_exits_nonzero_after_writing_report(monkeypatch):
    # Verified against the real pinned image: Maigret can exit non-zero
    # *after* successfully writing its CSV/JSON reports, because it then
    # tries to update its own site-database cache under site-packages —
    # blocked by our --read-only hardening, unrelated to the scan itself.
    # A crash at that stage must not discard an otherwise-successful run.
    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None):
        host_path, _container_path = volume
        csv_path = Path(host_path) / "report_alice.csv"
        with csv_path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["username", "name", "url_main", "url_user", "exists", "http_status", "error_reason"])
            writer.writerow(["alice", "GitHub", "https://github.com/", "https://github.com/alice", "Claimed", "200", ""])
        return DockerRunResult(
            ok=True, returncode=1, stdout=b"", stderr=b"OSError: Read-only file system", error=None,
        )

    monkeypatch.setattr(maigret_plugin, "run_hardened", fake_run_hardened)

    plugin = MaigretPlugin()
    findings = await plugin.run("alice")

    assert len(findings) == 1
    assert findings[0].status == Status.FOUND
    assert findings[0].source == "maigret:GitHub"


async def test_run_is_still_an_error_when_nonzero_exit_and_no_report_written(monkeypatch):
    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None):
        return DockerRunResult(
            ok=True, returncode=1, stdout=b"", stderr=b"some real crash before writing anything", error=None,
        )

    monkeypatch.setattr(maigret_plugin, "run_hardened", fake_run_hardened)

    plugin = MaigretPlugin()
    findings = await plugin.run("alice")

    assert len(findings) == 1
    assert findings[0].status == Status.ERROR
    assert "docker run failed" in findings[0].evidence["reason"]
