"""Tests for the shared hardened `docker run` helper.

This file guards the sandbox itself: every plugin's isolation comes from the
flags assembled here, and until now nothing verified they actually reach the
command line. A silently dropped `--cap-drop=ALL` would leave every tool
running with full capabilities and no test would notice.

No Docker is involved — `create_subprocess_exec` is stubbed and the assertions
are about the argv that would have been executed.
"""

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from argustrace.plugins import _docker_runner
from argustrace.plugins._docker_runner import HARDENING_FLAGS, run_hardened


class FakeProcess:
    def __init__(self, stdout=b"", stderr=b"", returncode=0, hang=False):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self._hang = hang
        self.killed = False

    async def communicate(self):
        if self._hang:
            await asyncio.Event().wait()  # never resolves
        return self._stdout, self._stderr

    def kill(self):
        self.killed = True

    async def wait(self):
        return self.returncode


@pytest.fixture
def spy_exec(monkeypatch):
    """Capture the argv `run_hardened` would execute."""
    captured = {}

    def install(process=None, raises=None):
        async def _fake_exec(*cmd, **kwargs):
            captured["cmd"] = list(cmd)
            if raises is not None:
                raise raises
            return process if process is not None else FakeProcess()

        monkeypatch.setattr(_docker_runner.asyncio, "create_subprocess_exec", _fake_exec)
        return captured

    return install


async def test_every_hardening_flag_reaches_the_command_line(spy_exec):
    captured = spy_exec()
    await run_hardened("some-image:1.0", ["--arg"], timeout_s=10)

    cmd = captured["cmd"]
    for flag in HARDENING_FLAGS:
        assert flag in cmd, f"{flag!r} missing — the sandbox is weaker than it claims"


async def test_container_is_removed_and_image_and_args_are_last(spy_exec):
    captured = spy_exec()
    await run_hardened("some-image:1.0", ["a", "b"], timeout_s=10)

    cmd = captured["cmd"]
    assert cmd[:3] == ["docker", "run", "--rm"]
    # The image must come after every flag, otherwise docker parses our
    # hardening flags as arguments to the containerised tool.
    assert cmd[-3:] == ["some-image:1.0", "a", "b"]


async def test_optional_isolation_knobs_are_absent_by_default(spy_exec):
    captured = spy_exec()
    await run_hardened("img", [], timeout_s=10)

    cmd = captured["cmd"]
    assert "-v" not in cmd
    assert "-e" not in cmd
    assert not any(c.startswith("--network") for c in cmd)


async def test_volume_and_network_are_passed_when_given(spy_exec):
    captured = spy_exec()
    await run_hardened(
        "img", [], timeout_s=10,
        volume=("/host/dir", "/output"),
        network="none",
    )

    cmd = captured["cmd"]
    assert cmd[cmd.index("-v") + 1] == "/host/dir:/output"
    assert "--network=none" in cmd


async def test_environment_is_passed_by_file_never_on_the_command_line(monkeypatch):
    """Toutatis' session cookie goes through here.

    `-e KEY=value` puts the value in the host `docker run` argv, where any
    local user can read it out of `ps` for the container's lifetime. An
    env-file is read by docker itself and never reaches a process listing.
    """
    seen = {}

    async def _fake_exec(*cmd, **kwargs):
        seen["cmd"] = list(cmd)
        env_file = Path(cmd[cmd.index("--env-file") + 1])
        seen["env_file_contents"] = env_file.read_text()
        seen["env_file_mode"] = env_file.stat().st_mode & 0o777
        return FakeProcess()

    monkeypatch.setattr(_docker_runner.asyncio, "create_subprocess_exec", _fake_exec)
    await run_hardened("img", [], timeout_s=10, env={"IG_SESSIONID": "s3cret-cookie"})

    assert "-e" not in seen["cmd"]
    assert not any("s3cret-cookie" in part for part in seen["cmd"])
    assert seen["env_file_contents"] == "IG_SESSIONID=s3cret-cookie\n"
    assert seen["env_file_mode"] == 0o600


async def test_environment_value_with_a_newline_is_rejected(spy_exec):
    """One KEY=value per line, so an embedded newline would inject a second
    variable into the container."""
    spy_exec()
    result = await run_hardened("img", [], timeout_s=10, env={"K": "a\nEVIL=1"})

    assert result.ok is False
    assert "newline" in result.error


async def test_no_env_file_when_no_environment_is_given(spy_exec):
    captured = spy_exec()
    await run_hardened("img", [], timeout_s=10)

    assert "--env-file" not in captured["cmd"]


async def test_missing_docker_is_reported_as_not_ok(spy_exec):
    spy_exec(raises=FileNotFoundError())
    result = await run_hardened("img", [], timeout_s=10)

    # ok=False is what makes plugins report ERROR rather than guessing a
    # negative result — the tri-state invariant depends on it.
    assert result.ok is False
    assert result.returncode is None
    assert "docker executable not found" in result.error


async def test_timeout_is_reported_as_not_ok_and_kills_the_client(spy_exec):
    process = FakeProcess(hang=True)
    spy_exec(process=process)

    result = await run_hardened("img", [], timeout_s=0)

    assert result.ok is False
    assert result.returncode is None
    assert "timed out" in result.error
    assert process.killed is True


async def test_run_records_a_container_id_so_it_can_be_reaped(spy_exec):
    captured = spy_exec()
    await run_hardened("img", [], timeout_s=10)

    assert "--cidfile" in captured["cmd"]


async def test_timeout_kills_the_container_not_only_the_docker_client(monkeypatch):
    """Killing the `docker run` client leaves the container running.

    The daemon carries the container through to completion, so before this a
    timed-out scan kept burning CPU and network for minutes after the plugin
    had already reported failure.
    """
    commands = []
    hung = FakeProcess(hang=True)

    async def _fake_exec(*cmd, **kwargs):
        commands.append(list(cmd))
        if cmd[:2] == ("docker", "run"):
            # Stand in for docker recording the id it just started.
            Path(cmd[cmd.index("--cidfile") + 1]).write_text("deadbeefcafe\n")
            return hung
        return FakeProcess()

    monkeypatch.setattr(_docker_runner.asyncio, "create_subprocess_exec", _fake_exec)
    result = await run_hardened("img", [], timeout_s=0)

    assert result.ok is False
    kills = [c for c in commands if c[:2] == ["docker", "kill"]]
    assert kills == [["docker", "kill", "deadbeefcafe"]]
    assert hung.killed is True


async def test_timeout_before_the_container_started_is_survivable(spy_exec):
    """No cidfile written means docker never got as far as a container."""
    spy_exec(process=FakeProcess(hang=True))
    result = await run_hardened("img", [], timeout_s=0)

    assert result.ok is False
    assert "timed out" in result.error


async def test_successful_run_returns_streams_and_returncode(spy_exec):
    spy_exec(process=FakeProcess(stdout=b"out", stderr=b"err", returncode=0))
    result = await run_hardened("img", [], timeout_s=10)

    assert result.ok is True
    assert result.returncode == 0
    assert result.stdout == b"out"
    assert result.stderr == b"err"
    assert result.error is None


async def test_concurrent_runs_are_capped(monkeypatch):
    """Every container is allowed 512 MB, so without a ceiling N simultaneous
    requests means N x 512 MB and N full scans competing for the network."""
    monkeypatch.setattr(
        _docker_runner, "SETTINGS", replace(_docker_runner.SETTINGS, max_concurrent_runs=2),
    )
    _docker_runner._slots_by_loop.clear()

    state = {"live": 0, "peak": 0}

    class CountingProcess(FakeProcess):
        async def communicate(self):
            state["live"] += 1
            state["peak"] = max(state["peak"], state["live"])
            await asyncio.sleep(0.01)  # hold the slot long enough to overlap
            state["live"] -= 1
            return b"", b""

    async def _fake_exec(*cmd, **kwargs):
        return CountingProcess()

    monkeypatch.setattr(_docker_runner.asyncio, "create_subprocess_exec", _fake_exec)
    await asyncio.gather(*(run_hardened("img", [], timeout_s=10) for _ in range(6)))

    assert state["peak"] <= 2, f"{state['peak']} containers ran at once, cap is 2"


async def test_nonzero_exit_still_counts_as_a_completed_run(spy_exec):
    """ok=True means "the run completed"; the plugin decides what a non-zero
    exit means for its own tool (Maigret exits non-zero after a good scan)."""
    spy_exec(process=FakeProcess(stdout=b"", stderr=b"boom", returncode=1))
    result = await run_hardened("img", [], timeout_s=10)

    assert result.ok is True
    assert result.returncode == 1


async def test_timeout_scale_lengthens_the_deadline(monkeypatch, spy_exec):
    """One knob instead of ~24 environment variables, applied centrally so
    every caller gets it without having to remember."""
    monkeypatch.setattr(
        _docker_runner, "SETTINGS", replace(_docker_runner.SETTINGS, timeout_scale=3.0),
    )
    spy_exec(process=FakeProcess(stdout=b"ok"))

    captured = {}
    real_wait_for = _docker_runner.asyncio.wait_for

    async def spy_wait_for(awaitable, timeout):
        captured["timeout"] = timeout
        return await real_wait_for(awaitable, timeout)

    monkeypatch.setattr(_docker_runner.asyncio, "wait_for", spy_wait_for)
    await run_hardened("img", [], timeout_s=10)

    assert captured["timeout"] == 30


def test_timeout_scale_is_clamped_so_it_can_never_shorten_a_timeout(monkeypatch):
    """Several plugins must outlast the timeout their container applies to
    itself, so a scale below 1 would resurrect exactly the bug
    test_registry_consistency.py guards against."""
    from argustrace import settings

    monkeypatch.setenv("ARGUSTRACE_TIMEOUT_SCALE", "0.1")
    assert settings.load().timeout_scale == 1.0

    monkeypatch.setenv("ARGUSTRACE_TIMEOUT_SCALE", "2.5")
    assert settings.load().timeout_scale == 2.5

    monkeypatch.setenv("ARGUSTRACE_TIMEOUT_SCALE", "not-a-number")
    assert settings.load().timeout_scale == 1.0
