import asyncio
import base64
import binascii
import ipaddress
import json
import re
import socket
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from argustrace.core.models import Finding, Status
from argustrace.plugins._docker_runner import run_hardened

IMAGE = "argustrace-exiftool:1.0"
RUN_TIMEOUT_S = 30

# Matches the entrypoint's own --max-filesize and the frontend's pre-check
# (ImageEntityInput.jsx) — enforced again here since the plugin is the only
# place that's actually trustworthy.
MAX_BYTES = 20 * 1024 * 1024

DATA_URI_PATTERN = re.compile(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$", re.DOTALL)


def _is_jpeg(b: bytes) -> bool:
    return b[:3] == b"\xff\xd8\xff"


def _is_png(b: bytes) -> bool:
    return b[:8] == b"\x89PNG\r\n\x1a\n"


def _is_tiff(b: bytes) -> bool:
    return b[:4] in (b"II*\x00", b"MM\x00*")


def _is_webp(b: bytes) -> bool:
    return b[:4] == b"RIFF" and b[8:12] == b"WEBP"


def _is_heic(b: bytes) -> bool:
    return b[4:8] == b"ftyp" and b[8:12] in (
        b"heic", b"heix", b"hevc", b"heim", b"heis", b"hevm", b"hevs", b"mif1", b"msf1",
    )


# A cheap check that the bytes actually look like the claimed type, without
# ever parsing the image itself — content is only handed to exiftool, and
# only inside the hardened, read-only container.
MAGIC_CHECKS = {
    "image/jpeg": _is_jpeg,
    "image/png": _is_png,
    "image/tiff": _is_tiff,
    "image/webp": _is_webp,
    "image/heic": _is_heic,
    "image/heif": _is_heic,
}

# Describe our own temp file (written moments ago, on our own filesystem),
# not the original image — showing them would be misleading, not informative.
LOCAL_FILE_KEYS = {
    "SourceFile", "FileName", "Directory", "FilePermissions",
    "FileInodeChangeDate", "FileAccessDate", "FileModifyDate", "ExifToolVersion",
}
# Present for every file exiftool can even open, image or not — not
# meaningful "found evidence" by themselves.
BASELINE_KEYS = LOCAL_FILE_KEYS | {"FileSize", "FileType", "FileTypeExtension", "MIMEType", "Error", "Warning"}


class ExifPlugin:
    name = "exif"
    supported_entities = ["image"]

    async def run(self, entity: str, options: dict | None = None) -> list[Finding]:
        entity = (entity or "").strip()
        data_match = DATA_URI_PATTERN.match(entity)

        with tempfile.TemporaryDirectory() as tmpdir:
            if data_match:
                error = self._prepare_upload(tmpdir, data_match)
                if error:
                    return [self._error(entity, error)]
                args = ["--file"]
            elif entity.startswith(("http://", "https://")):
                error = await self._validate_url(entity)
                if error:
                    return [self._error(entity, error)]
                args = ["--url", entity]
            else:
                return [self._error(
                    entity, "invalid entity: expected an http(s) image URL or an uploaded image file",
                )]

            result = await run_hardened(IMAGE, args, volume=(tmpdir, "/output"), timeout_s=RUN_TIMEOUT_S)
            if not result.ok:
                return [self._error(entity, result.error)]
            if result.returncode != 0:
                return [self._error(entity, f"exiftool failed: {result.stderr.decode(errors='replace')[:300]}")]

            return self._parse_output(entity, result.stdout.decode(errors="replace"))

    def _prepare_upload(self, tmpdir: str, match: re.Match) -> str | None:
        mime, b64_data = match.group(1), match.group(2)
        check = MAGIC_CHECKS.get(mime)
        if check is None:
            return f"unsupported image type: {mime}"
        try:
            raw = base64.b64decode(b64_data, validate=True)
        except binascii.Error:
            return "invalid entity: could not decode the uploaded file"
        if len(raw) > MAX_BYTES:
            return f"file too large: {len(raw)} bytes (max {MAX_BYTES})"
        if not raw or not check(raw):
            return f"file content doesn't look like a valid {mime} image"
        (Path(tmpdir) / "input").write_bytes(raw)
        return None

    async def _validate_url(self, url: str) -> str | None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return "invalid entity: not a valid http(s) URL"

        # Resolve and check every returned address before letting the
        # container's curl anywhere near it — SSRF guard, same pattern as
        # ip_plugin.py's is_global check. The container also has no --network
        # restriction, so this host-side check is the real gate, not curl's
        # own behavior (it doesn't follow redirects either, for the same reason).
        try:
            addrs = await asyncio.get_running_loop().getaddrinfo(parsed.hostname, None)
        except socket.gaierror:
            return f"could not resolve host: {parsed.hostname}"
        for _family, _type, _proto, _canonname, sockaddr in addrs:
            try:
                ip = ipaddress.ip_address(sockaddr[0])
            except ValueError:
                return "could not validate the resolved address"
            if not ip.is_global:
                return "invalid entity: URL resolves to a private/internal address, not allowed"
        return None

    def _parse_output(self, entity: str, stdout: str) -> list[Finding]:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return [self._error(entity, "exiftool produced unparseable output")]
        if not data:
            return [self._error(entity, "exiftool produced no output")]
        tags = data[0]

        if tags.get("Error"):
            return [self._error(entity, f"not a readable image: {tags['Error']}")]

        meaningful = {k: v for k, v in tags.items() if k not in BASELINE_KEYS and v not in (None, "", [])}
        if not meaningful:
            return [Finding(
                entity=entity, entity_type="image", source="exiftool",
                status=Status.NOT_FOUND, evidence={"reason": "no embedded metadata found in this image"},
            )]

        return [Finding(
            entity=entity, entity_type="image", source="exiftool",
            status=Status.FOUND, evidence=self._build_evidence(tags, meaningful),
        )]

    def _build_evidence(self, tags: dict, meaningful: dict) -> dict:
        evidence = dict(meaningful)

        lat, lon = tags.get("GPSLatitude"), tags.get("GPSLongitude")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            evidence["coordinates"] = f"{lat},{lon}"

        camera = " ".join(p for p in (tags.get("Make"), tags.get("Model")) if p)
        date = tags.get("DateTimeOriginal") or tags.get("CreateDate")
        headline_parts = [p for p in (camera, date) if p]
        if "coordinates" in evidence:
            headline_parts.append("GPS location embedded")
        if headline_parts:
            evidence["headline"] = " · ".join(headline_parts)

        return evidence

    def _error(self, entity: str, reason: str) -> Finding:
        return Finding(
            entity=entity, entity_type="image", source="exiftool", status=Status.ERROR, evidence={"reason": reason},
        )
