import base64
import json

from argustrace.core.models import Status
from argustrace.plugins.exif_plugin import DATA_URI_PATTERN, MAX_BYTES, ExifPlugin

# A minimal, valid 1x1 JPEG (SOI + APP0/JFIF + a few segments + EOI) — real
# magic bytes so the plugin's own signature check passes, no fixture file needed.
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
    error = await plugin._validate_url("ftp://example.com/image.jpg")

    assert error is not None
    assert "not a valid http(s) URL" in error


async def test_unresolvable_host_is_error():
    plugin = ExifPlugin()
    findings = await plugin.run("http://this-host-does-not-exist.invalid/x.jpg")

    assert findings[0].status == Status.ERROR
    assert "could not resolve" in findings[0].evidence["reason"]


def test_prepare_upload_rejects_wrong_magic_bytes():
    plugin = ExifPlugin()
    match = DATA_URI_PATTERN.match(_data_uri("image/jpeg", b"not actually a jpeg"))

    error = plugin._prepare_upload("/tmp", match)

    assert error is not None
    assert "doesn't look like a valid" in error


def test_prepare_upload_rejects_unsupported_mime():
    plugin = ExifPlugin()
    match = DATA_URI_PATTERN.match(_data_uri("image/svg+xml", TINY_JPEG))

    error = plugin._prepare_upload("/tmp", match)

    assert error is not None
    assert "unsupported image type" in error


def test_prepare_upload_rejects_oversized_payload(tmp_path):
    plugin = ExifPlugin()
    huge = b"\xff\xd8\xff" + b"0" * (MAX_BYTES + 1)
    match = DATA_URI_PATTERN.match(_data_uri("image/jpeg", huge))

    error = plugin._prepare_upload(str(tmp_path), match)

    assert error is not None
    assert "too large" in error


def test_prepare_upload_writes_file_for_valid_jpeg(tmp_path):
    plugin = ExifPlugin()
    match = DATA_URI_PATTERN.match(_data_uri("image/jpeg", TINY_JPEG))

    error = plugin._prepare_upload(str(tmp_path), match)

    assert error is None
    assert (tmp_path / "input").read_bytes() == TINY_JPEG


def test_data_uri_pattern_rejects_non_data_uri():
    plugin = ExifPlugin()
    assert DATA_URI_PATTERN.match("https://example.com/a.jpg") is None


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
