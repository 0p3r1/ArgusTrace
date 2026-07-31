from argustrace.core.models import Status
from argustrace.plugins.theharvester_plugin import TheHarvesterPlugin


async def test_invalid_entity_returns_error_without_touching_docker():
    plugin = TheHarvesterPlugin()
    findings = await plugin.run("not a domain!")

    assert len(findings) == 1
    assert findings[0].status == Status.ERROR
    assert "invalid entity" in findings[0].evidence["reason"]


def test_empty_report_is_not_found():
    plugin = TheHarvesterPlugin()
    findings = plugin._parse_report("example.com", {"cmd": "-d example.com -b rapiddns", "hosts": [], "shodan": []})

    assert len(findings) == 1
    assert findings[0].status == Status.NOT_FOUND


def test_parse_report_splits_host_name_and_resolved_target():
    plugin = TheHarvesterPlugin()
    data = {
        "cmd": "-d example.com -b rapiddns",
        "hosts": ["api.example.com:api.example.com.edgekey.net", "www.example.com:1.2.3.4"],
    }

    findings = plugin._parse_report("example.com", data)

    assert len(findings) == 2
    assert all(f.status == Status.FOUND for f in findings)
    by_source = {f.source: f for f in findings}
    assert by_source["theharvester:hosts:api.example.com"].evidence["resolved"] == ["api.example.com.edgekey.net"]
    assert by_source["theharvester:hosts:www.example.com"].evidence["resolved"] == ["1.2.3.4"]
    assert by_source["theharvester:hosts:api.example.com"].url == "https://api.example.com"


def test_parse_report_merges_multiple_records_for_the_same_host():
    plugin = TheHarvesterPlugin()
    data = {
        "cmd": "-d example.com -b rapiddns",
        "hosts": ["dual.example.com:1.2.3.4", "dual.example.com:::1"],
    }

    findings = plugin._parse_report("example.com", data)

    assert len(findings) == 1
    assert findings[0].source == "theharvester:hosts:dual.example.com"
    assert findings[0].evidence["resolved"] == ["1.2.3.4", "::1"]


def test_parse_report_ignores_cmd_key():
    plugin = TheHarvesterPlugin()
    data = {"cmd": "-d example.com -b rapiddns", "emails": ["contact@example.com"]}

    findings = plugin._parse_report("example.com", data)

    assert len(findings) == 1
    assert findings[0].source == "theharvester:emails:contact@example.com"


def test_build_args_defaults():
    plugin = TheHarvesterPlugin()
    args = plugin._build_args("example.com", None)
    assert args[args.index("-b") + 1] == "rapiddns"
    assert args[args.index("-l") + 1] == "500"


def test_build_args_custom_limit_clamped():
    plugin = TheHarvesterPlugin()
    args = plugin._build_args("example.com", {"limit": 5000})
    assert args[args.index("-l") + 1] == "1000"


def test_build_args_custom_sources_filtered_to_known_free_ones():
    plugin = TheHarvesterPlugin()
    args = plugin._build_args("example.com", {"sources": ["otx", "hackertarget", "shodan"]})
    assert args[args.index("-b") + 1] == "otx,hackertarget"


def test_build_args_falls_back_to_preset_when_sources_all_invalid():
    plugin = TheHarvesterPlugin()
    args = plugin._build_args("example.com", {"sources": ["shodan", "hunter"]})
    assert args[args.index("-b") + 1] == "rapiddns"
