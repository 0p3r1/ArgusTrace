import csv
from pathlib import Path

from argustrace.core.models import Status
from argustrace.plugins.holehe_plugin import HolehePlugin


async def test_invalid_entity_returns_error_without_touching_docker():
    plugin = HolehePlugin()
    findings = await plugin.run("not-an-email")

    assert len(findings) == 1
    assert findings[0].status == Status.ERROR
    assert "invalid entity" in findings[0].evidence["reason"]


def test_parse_csv_maps_ratelimit_and_exists_onto_status(tmp_path: Path):
    csv_path = tmp_path / "holehe_123_alice@example.com_results.csv"
    fieldnames = ["name", "domain", "method", "frequent_rate_limit", "rateLimit", "exists", "emailrecovery", "phoneNumber", "others"]
    rows = [
        {"name": "github", "domain": "github.com", "method": "login", "frequent_rate_limit": "False",
         "rateLimit": "True", "exists": "False", "emailrecovery": "", "phoneNumber": "", "others": ""},
        {"name": "adobe", "domain": "adobe.com", "method": "password recovery", "frequent_rate_limit": "False",
         "rateLimit": "False", "exists": "True", "emailrecovery": "", "phoneNumber": "", "others": ""},
        {"name": "amazon", "domain": "amazon.com", "method": "login", "frequent_rate_limit": "False",
         "rateLimit": "False", "exists": "False", "emailrecovery": "", "phoneNumber": "", "others": ""},
    ]
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    plugin = HolehePlugin()
    findings = plugin._parse_csv("alice@example.com", csv_path)

    by_source = {f.source: f for f in findings}
    assert len(findings) == 3
    # rateLimit=True takes priority over exists, regardless of its value.
    assert by_source["holehe:github"].status == Status.ERROR
    assert by_source["holehe:adobe"].status == Status.FOUND
    assert by_source["holehe:amazon"].status == Status.NOT_FOUND


def test_build_args_no_password_recovery_off_by_default():
    plugin = HolehePlugin()
    args = plugin._build_args("alice@example.com", {})
    assert "-NP" not in args


def test_build_args_no_password_recovery_flag():
    plugin = HolehePlugin()
    args = plugin._build_args("alice@example.com", {"no_password_recovery": True})
    assert "-NP" in args
