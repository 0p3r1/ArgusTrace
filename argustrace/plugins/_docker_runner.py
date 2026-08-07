import asyncio
import os
import tempfile
import weakref
from dataclasses import dataclass
from pathlib import Path

from argustrace.settings import SETTINGS

# Shared hardening applied to every plugin that shells out to Docker: no
# capabilities, no privilege escalation, read-only rootfs, bounded resources.
# Deliberately not configurable — see argustrace/settings.py.
HARDENING_FLAGS = [
    "--cap-drop=ALL",
    "--security-opt=no-new-privileges",
    "--read-only",
    "--tmpfs", "/tmp",
    "--memory=512m",
    "--cpus=1",
    "--pids-limit=256",
]

# How long to wait for `docker kill` to reap a timed-out container before
# giving up on it; the client is killed either way.
KILL_TIMEOUT_S = 10

# One semaphore per event loop rather than a module-level one: asyncio
# primitives bind to the loop that first uses them, and a single instance
# would break the moment a second loop appeared (every async test gets its
# own). Weak keys so a finished loop doesn't keep its semaphore alive.
_slots_by_loop: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def _concurrency_slot() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    slot = _slots_by_loop.get(loop)
    if slot is None:
        slot = asyncio.Semaphore(SETTINGS.max_concurrent_runs)
        _slots_by_loop[loop] = slot
    return slot


@dataclass
class DockerRunResult:
    ok: bool  # False means the run never completed (docker missing, timeout)
    returncode: int | None
    stdout: bytes
    stderr: bytes
    error: str | None


def _write_env_file(directory: str, env: dict[str, str]) -> str:
    """Write an --env-file so secrets never reach the host command line.

    Values passed as `-e KEY=value` are part of the `docker run` argv and so
    are visible in `ps` to every local user for the container's lifetime —
    which defeats the point for things like Toutatis's session cookie. Docker
    reads this file itself; the values never appear in any process listing.
    """
    path = Path(directory) / "env"
    # 0600 before anything is written; the enclosing TemporaryDirectory is
    # already 0700, this makes the intent explicit rather than incidental.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        for key, value in env.items():
            if "\n" in value or "\n" in key:
                # docker's env-file format is strictly one KEY=value per
                # line, so an embedded newline would inject a second entry.
                raise ValueError(f"environment value for {key!r} must not contain a newline")
            handle.write(f"{key}={value}\n")
    return str(path)


async def _kill_container(cidfile: Path) -> None:
    """Stop the container a timed-out run left behind.

    Killing the `docker run` client does not stop the container: the daemon
    keeps it running to completion, so a timed-out scan would carry on
    burning CPU and network long after the plugin reported failure. The
    cidfile gives us the id to kill; `--rm` still reaps it afterwards.
    """
    try:
        cid = cidfile.read_text().strip()
    except OSError:
        return  # container never started; nothing to reap
    if not cid:
        return
    try:
        killer = await asyncio.create_subprocess_exec(
            "docker", "kill", cid,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return
    try:
        await asyncio.wait_for(killer.wait(), timeout=KILL_TIMEOUT_S)
    except TimeoutError:
        killer.kill()
        await killer.wait()


async def run_hardened(
    image: str,
    args: list[str],
    timeout_s: int,
    volume: tuple[str, str] | None = None,
    env: dict[str, str] | None = None,
    network: str | None = None,
) -> DockerRunResult:
    # Scaled here rather than in each plugin: one place, and every caller
    # (including future ones) gets it without having to remember. The scale
    # can only lengthen, so this cannot pull a timeout below the one a
    # container applies to itself.
    # No floor needed: the scale is clamped to >= 1.0 in settings, so this
    # can only ever lengthen the deadline it was given.
    timeout_s = round(timeout_s * SETTINGS.timeout_scale)

    async with _concurrency_slot():
        # Holds the cidfile and, when needed, the env-file. Both must outlive
        # the run and neither may leak the secret beyond it.
        with tempfile.TemporaryDirectory(prefix="argustrace-run-") as rundir:
            cidfile = Path(rundir) / "cid"  # docker refuses to overwrite it

            cmd = ["docker", "run", "--rm", "--cidfile", str(cidfile), *HARDENING_FLAGS]
            if network is not None:
                # Extra isolation for plugins that don't need network at all
                # for a given call (e.g. exiftool reading an already-local
                # uploaded file): even a fully compromised process inside the
                # container has nowhere to reach out to. Not the default
                # because most plugins do need network to reach the tool/site
                # they're checking.
                cmd += [f"--network={network}"]
            if volume is not None:
                host_path, container_path = volume
                cmd += ["-v", f"{host_path}:{container_path}"]
            if env:
                try:
                    cmd += ["--env-file", _write_env_file(rundir, env)]
                except ValueError as e:
                    return DockerRunResult(
                        ok=False, returncode=None, stdout=b"", stderr=b"", error=str(e),
                    )
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
                await _kill_container(cidfile)
                proc.kill()
                await proc.wait()
                return DockerRunResult(
                    ok=False, returncode=None, stdout=b"", stderr=b"",
                    error=f"docker run timed out after {timeout_s}s",
                )

            return DockerRunResult(
                ok=True, returncode=proc.returncode, stdout=stdout, stderr=stderr, error=None,
            )
