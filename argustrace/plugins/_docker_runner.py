import asyncio
from dataclasses import dataclass

# Shared hardening applied to every plugin that shells out to Docker: no
# capabilities, no privilege escalation, read-only rootfs, bounded resources.
HARDENING_FLAGS = [
    "--cap-drop=ALL",
    "--security-opt=no-new-privileges",
    "--read-only",
    "--tmpfs", "/tmp",
    "--memory=512m",
    "--cpus=1",
    "--pids-limit=256",
]


@dataclass
class DockerRunResult:
    ok: bool  # False means the run never completed (docker missing, timeout)
    returncode: int | None
    stdout: bytes
    stderr: bytes
    error: str | None


async def run_hardened(
    image: str,
    args: list[str],
    timeout_s: int,
    volume: tuple[str, str] | None = None,
    env: dict[str, str] | None = None,
    network: str | None = None,
) -> DockerRunResult:
    cmd = ["docker", "run", "--rm", *HARDENING_FLAGS]
    if network is not None:
        # Extra isolation for plugins that don't need network at all for a
        # given call (e.g. exiftool reading an already-local uploaded file):
        # even a fully compromised process inside the container has nowhere
        # to reach out to. Not the default because most plugins do need
        # network to reach the tool/site they're checking.
        cmd += [f"--network={network}"]
    if volume is not None:
        host_path, container_path = volume
        cmd += ["-v", f"{host_path}:{container_path}"]
    for key, value in (env or {}).items():
        cmd += ["-e", f"{key}={value}"]
    cmd += [image, *args]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return DockerRunResult(
            ok=False, returncode=None, stdout=b"", stderr=b"",
            error="docker executable not found on host",
        )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return DockerRunResult(
            ok=False, returncode=None, stdout=b"", stderr=b"",
            error=f"docker run timed out after {timeout_s}s",
        )

    return DockerRunResult(ok=True, returncode=proc.returncode, stdout=stdout, stderr=stderr, error=None)
