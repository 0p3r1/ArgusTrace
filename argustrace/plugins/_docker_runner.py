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
    volume: tuple[str, str],
    timeout_s: int,
) -> DockerRunResult:
    host_path, container_path = volume
    cmd = [
        "docker", "run", "--rm",
        *HARDENING_FLAGS,
        "-v", f"{host_path}:{container_path}",
        image,
        *args,
    ]

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
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return DockerRunResult(
            ok=False, returncode=None, stdout=b"", stderr=b"",
            error=f"docker run timed out after {timeout_s}s",
        )

    return DockerRunResult(ok=True, returncode=proc.returncode, stdout=stdout, stderr=stderr, error=None)
