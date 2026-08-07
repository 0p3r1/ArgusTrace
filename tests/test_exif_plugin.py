import base64
import json

from argustrace.core.models import Status
from argustrace.plugins import exif_plugin
from argustrace.plugins._docker_runner import DockerRunResult
from argustrace.plugins.exif_plugin import DATA_URI_PATTERN, MAX_BYTES, ExifPlugin

# A minimal, valid 1x1 JPEG (SOI + APP0/JFIF + a few segments + EOI) — no
# longer load-bearing for validation (the plugin doesn't gate on content
# anymore), just realistic-looking bytes for the "upload succeeds" tests.
TINY_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300"
    + "ff" * 64
    + "ffc0000b08000100010101110002110103010101ffc4001f00"
    + "00" * 16
    + "ffda0008010100003f00d2cfffd9"
)


def _data_uri(mime: str, raw: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


async def test_blank_entity_is_error_without_touching_docker():
    plugin = ExifPlugin()
    findings = await plugin.run("")

    assert len(findings) == 1
    assert findings[0].status == Status.ERROR
    assert "invalid entity" in findings[0].evidence["reason"]


async def test_non_url_non_data_uri_entity_is_error():
    plugin = ExifPlugin()
    findings = await plugin.run("just some text")

    assert findings[0].status == Status.ERROR
    assert "invalid entity" in findings[0].evidence["reason"]


async def test_localhost_url_is_rejected_as_ssrf_risk():
    plugin = ExifPlugin()
    findings = await plugin.run("http://localhost/image.jpg")

    assert findings[0].status == Status.ERROR
    assert "private/internal" in findings[0].evidence["reason"]


async def test_ftp_scheme_is_rejected():
    plugin = ExifPlugin()
    error, resolve_spec = await plugin._validate_url("ftp://example.com/image.jpg")

    assert error is not None
    assert "not a valid http(s) URL" in error
    assert resolve_spec is None


async def test_validated_url_returns_a_pin_for_the_address_it_checked():
    """The container must not resolve the hostname a second time.

    Validating host-side and then handing curl a *hostname* leaves the guard
    defeatable by DNS rebinding: a short-TTL record can answer with a public
    address for our lookup and an internal one for curl's. The returned
    host:port:ip pin removes the second resolution entirely.
    """
    plugin = ExifPlugin()
    error, resolve_spec = await plugin._validate_url("https://example.com/a.jpg")

    assert error is None
    # host:port:address — split from the left, since an IPv6 address is
    # bracketed but still full of colons.
    host, port, address = resolve_spec.split(":", 2)
    assert host == "example.com"
    assert port == "443"
    assert address  # whatever example.com resolves to, it is pinned explicitly


async def test_ip_literal_host_needs_no_pin():
    """There is no DNS lookup to rebind when the URL already carries an
    address, and a bracketed IPv6 literal would make the pin ambiguous."""
    plugin = ExifPlugin()
    error, resolve_spec = await plugin._validate_url("https://1.1.1.1/a.jpg")

    assert error is None
    assert resolve_spec == ""


async def test_explicit_port_is_carried_into_the_pin():
    plugin = ExifPlugin()
    error, resolve_spec = await plugin._validate_url("http://example.com:8080/a.jpg")

    assert error is None
    assert resolve_spec.startswith("example.com:8080:")


async def test_run_passes_the_resolve_pin_to_the_container(monkeypatch):
    calls = []

    async def fake_run_hardened(image, args, timeout_s, **kwargs):
        calls.append(args)
        return DockerRunResult(ok=True, returncode=0, stdout=b"[]", stderr=b"", error=None)

    monkeypatch.setattr(exif_plugin, "run_hardened", fake_run_hardened)
    await ExifPlugin().run("https://example.com/a.jpg")

    args = calls[0]
    assert args[0] == "--url"
    assert args[1] == "https://example.com/a.jpg"
    assert args[2].startswith("example.com:443:")


async def test_unresolvable_host_is_error():
    plugin = ExifPlugin()
    findings = await plugin.run("http://this-host-does-not-exist.invalid/x.jpg")

    assert findings[0].status == Status.ERROR
    assert "could not resolve" in findings[0].evidence["reason"]


def test_prepare_upload_accepts_any_declared_mime(tmp_path):
    # No allowlist anymore — a RAW/video/whatever mime is accepted just the
    # same, since real safety comes from the sandbox, not guessing the format.
    plugin = ExifPlugin()
    match = DATA_URI_PATTERN.match(_data_uri("image/x-canon-cr2", TINY_JPEG))

    error = plugin._prepare_upload(str(tmp_path), match)

    assert error is None
    assert (tmp_path / "input").read_bytes() == TINY_JPEG


def test_prepare_upload_accepts_blank_mime(tmp_path):
    # Browsers commonly report an empty type for formats they don't
    # recognize (most RAW files) — must not be treated as invalid.
    plugin = ExifPlugin()
    match = DATA_URI_PATTERN.match(f"data:;base64,{base64.b64encode(TINY_JPEG).decode()}")

    error = plugin._prepare_upload(str(tmp_path), match)

    assert error is None


def test_prepare_upload_rejects_empty_payload(tmp_path):
    plugin = ExifPlugin()
    match = DATA_URI_PATTERN.match(_data_uri("image/jpeg", b""))

    error = plugin._prepare_upload(str(tmp_path), match)

    assert error is not None
    assert "empty" in error


def test_prepare_upload_rejects_oversized_payload(tmp_path):
    plugin = ExifPlugin()
    huge = b"0" * (MAX_BYTES + 1)
    match = DATA_URI_PATTERN.match(_data_uri("image/jpeg", huge))

    error = plugin._prepare_upload(str(tmp_path), match)

    assert error is not None
    assert "too large" in error


def test_oversized_payload_is_rejected_before_being_decoded(tmp_path, monkeypatch):
    """Decoding to find out how big it is materialises the whole payload in
    memory, which is exactly what the limit exists to prevent."""
    plugin = ExifPlugin()
    match = DATA_URI_PATTERN.match(_data_uri("image/jpeg", b"0" * (MAX_BYTES + 1)))

    def explode(*_args, **_kwargs):
        raise AssertionError("payload was decoded before its size was checked")

    monkeypatch.setattr(exif_plugin.base64, "b64decode", explode)
    error = plugin._prepare_upload(str(tmp_path), match)

    assert error is not None
    assert "too large" in error


async def test_upload_findings_do_not_echo_the_data_uri_back(monkeypatch):
    """Repeating the submitted data URI in every Finding turned a 100 MB
    upload into a ~133 MB response."""
    async def fake_run_hardened(image, args, timeout_s, **kwargs):
        return DockerRunResult(ok=True, returncode=0, stdout=b"[]", stderr=b"", error=None)

    monkeypatch.setattr(exif_plugin, "run_hardened", fake_run_hardened)
    data_uri = _data_uri("image/jpeg", TINY_JPEG)
    findings = await ExifPlugin().run(data_uri)

    assert findings, "expected a finding"
    for finding in findings:
        assert finding.entity != data_uri
        assert "base64" not in finding.entity
        assert finding.entity.startswith("upload:")
        assert "image/jpeg" in finding.entity


async def test_overlong_plain_entity_is_truncated_in_findings(monkeypatch):
    findings = await ExifPlugin().run("x" * 5000)

    assert findings[0].status == Status.ERROR
    assert len(findings[0].entity) <= exif_plugin.MAX_LABEL_CHARS + 1


def test_prepare_upload_writes_file_for_valid_jpeg(tmp_path):
    plugin = ExifPlugin()
    match = DATA_URI_PATTERN.match(_data_uri("image/jpeg", TINY_JPEG))

    error = plugin._prepare_upload(str(tmp_path), match)

    assert error is None
    assert (tmp_path / "input").read_bytes() == TINY_JPEG


def test_data_uri_pattern_rejects_non_data_uri():
    assert DATA_URI_PATTERN.match("https://example.com/a.jpg") is None


async def test_run_disables_network_for_uploaded_file(monkeypatch):
    captured = {}

    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        captured["network"] = network
        return DockerRunResult(ok=True, returncode=0, stdout=b"[{}]", stderr=b"", error=None)

    monkeypatch.setattr(exif_plugin, "run_hardened", fake_run_hardened)

    plugin = ExifPlugin()
    await plugin.run(_data_uri("image/jpeg", TINY_JPEG))

    assert captured["network"] == "none"


async def test_run_keeps_default_network_for_url(monkeypatch):
    captured = {}

    async def fake_run_hardened(image, args, timeout_s, volume=None, env=None, network=None):
        captured["network"] = network
        return DockerRunResult(ok=True, returncode=0, stdout=b"[{}]", stderr=b"", error=None)

    monkeypatch.setattr(exif_plugin, "run_hardened", fake_run_hardened)

    plugin = ExifPlugin()
    await plugin.run("https://upload.wikimedia.org/wikipedia/commons/a/a7/ant.jpg")

    assert captured["network"] is None


def test_parse_output_error_tag_is_error():
    plugin = ExifPlugin()
    stdout = json.dumps([{"SourceFile": "/output/input", "Error": "Unknown file type"}])

    findings = plugin._parse_output("http://example.com/a.jpg", stdout)

    assert findings[0].status == Status.ERROR
    assert "Unknown file type" in findings[0].evidence["reason"]


def test_parse_output_baseline_only_is_not_found():
    plugin = ExifPlugin()
    stdout = json.dumps([{
        "SourceFile": "/output/input", "FileName": "input", "FileSize": 1234,
        "FileType": "JPEG", "FileTypeExtension": "JPG", "MIMEType": "image/jpeg",
        "ExifToolVersion": 12.8,
    }])

    findings = plugin._parse_output("http://example.com/a.jpg", stdout)

    assert findings[0].status == Status.NOT_FOUND


def test_parse_output_with_metadata_is_found_with_headline_and_coordinates():
    plugin = ExifPlugin()
    stdout = json.dumps([{
        "SourceFile": "/output/input", "FileSize": 1234, "FileType": "JPEG", "MIMEType": "image/jpeg",
        "Make": "Canon", "Model": "EOS 400D", "DateTimeOriginal": "2009:01:19 15:08:20",
        "GPSLatitude": 48.72, "GPSLongitude": 2.26,
    }])

    findings = plugin._parse_output("http://example.com/a.jpg", stdout)

    assert findings[0].status == Status.FOUND
    assert findings[0].evidence["coordinates"] == "48.72,2.26"
    assert findings[0].evidence["headline"] == "Canon EOS 400D · 2009:01:19 15:08:20 · GPS location embedded"
    assert findings[0].evidence["Make"] == "Canon"
    assert "SourceFile" not in findings[0].evidence
    assert "ExifToolVersion" not in findings[0].evidence


def test_parse_output_non_json_is_error():
    plugin = ExifPlugin()
    findings = plugin._parse_output("http://example.com/a.jpg", "not json")

    assert findings[0].status == Status.ERROR
