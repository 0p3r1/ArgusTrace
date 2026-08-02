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
RUN_TIMEOUT_S = 60

# Matches the entrypoint's own --max-filesize and the frontend's pre-check
# (ImageEntityInput.jsx) — enforced again here since the plugin is the only
# place that's actually trustworthy. Large enough for RAW camera files and
# short video clips, not just compressed photos.
MAX_BYTES = 100 * 1024 * 1024

# No allowlist of accepted mime/extensions here on purpose: exiftool reads
# 100+ formats (RAW, video, audio, PDF, ...) and hand-maintaining a magic-byte
# signature for each would be a losing game, while a bare prefix/suffix match
# wouldn't actually stop anything a real check wouldn't. The mime segment is
# whatever the browser reported (often blank for formats it doesn't
# recognize, e.g. most RAW files) and is purely descriptive — not a gate.
# Real safety comes from sandboxing the *parser*, not pre-guessing the file:
# every run happens inside the hardened container (--cap-drop=ALL, read-only,
# resource-limited, --rm), and this specific call path additionally gets
# --network=none since a local file read never needs network at all.
DATA_URI_PATTERN = re.compile(r"^data:([a-zA-Z0-9.+-]*/[a-zA-Z0-9.+-]*)?;base64,(.*)$", re.DOTALL)

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
                # A local file read never needs network — drop it entirely,
                # tighter than the network access every other call path gets.
                network = "none"
            elif entity.startswith(("http://", "https://")):
                error = await self._validate_url(entity)
                if error:
                    return [self._error(entity, error)]
                args = ["--url", entity]
                network = None
            else:
                return [self._error(
                    entity, "invalid entity: expected an http(s) image URL or an uploaded image file",
                )]

            result = await run_hardened(
                IMAGE, args, volume=(tmpdir, "/output"), timeout_s=RUN_TIMEOUT_S, network=network,
            )
            if not result.ok:
                return [self._error(entity, result.error)]
            if result.returncode != 0:
                return [self._error(entity, f"exiftool failed: {result.stderr.decode(errors='replace')[:300]}")]

            return self._parse_output(entity, result.stdout.decode(errors="replace"))

    def _prepare_upload(self, tmpdir: str, match: re.Match) -> str | None:
        b64_data = match.group(2)
        try:
            raw = base64.b64decode(b64_data, validate=True)
        except binascii.Error:
            return "invalid entity: could not decode the uploaded file"
        if not raw:
            return "invalid entity: uploaded file is empty"
        if len(raw) > MAX_BYTES:
            return f"file too large: {len(raw)} bytes (max {MAX_BYTES})"
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
