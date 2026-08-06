"""Shared fixtures for the plugin test suite.

`run_hardened` is the single choke point every plugin goes through to reach
Docker, so nearly every plugin test has to stub it. Doing that per-file meant
repeating its exact signature — `(image, args, timeout_s, volume=None,
env=None, network=None)` — around forty times, so adding one parameter to
`run_hardened` broke every test file at once with no single place to fix it.

The fake here takes `**kwargs` instead: a new parameter shows up in
`DockerCall.extra` and no existing test notices. Nothing else about the
tests' behaviour changes — they still never touch Docker.
"""

from dataclasses import dataclass, field

import pytest

from argustrace.plugins._docker_runner import DockerRunResult


def make_docker_result(
    stdout: bytes = b"",
    *,
    returncode: int | None = 0,
    ok: bool = True,
    stderr: bytes = b"",
    error: str | None = None,
) -> DockerRunResult:
    """Build a DockerRunResult with the defaults of a successful run.

    `ok=False` means the run never completed (docker missing, timed out) and
    carries an `error` instead of a returncode — the distinction plugins rely
    on to report ERROR rather than guessing a negative result.
    """
    return DockerRunResult(ok=ok, returncode=returncode, stdout=stdout, stderr=stderr, error=error)


@dataclass
class DockerCall:
    """One recorded invocation of the stubbed `run_hardened`."""

    image: str
    args: list[str]
    timeout_s: int
    volume: tuple[str, str] | None = None
    env: dict[str, str] | None = None
    network: str | None = None
    # Anything `run_hardened` grows later, so a new parameter never breaks a
    # test that doesn't care about it.
    extra: dict = field(default_factory=dict)

    def flag_value(self, flag: str) -> str | None:
        """The argv value following `flag`, or None if the flag is absent."""
        return self.args[self.args.index(flag) + 1] if flag in self.args else None


@pytest.fixture
def docker_result():
    """Factory for DockerRunResult, so tests don't import the dataclass."""
    return make_docker_result


@pytest.fixture
def fake_docker(monkeypatch):
    """Stub `run_hardened` in a plugin module and record every call.

    Usage:
        calls = fake_docker(crtsh_plugin, docker_result(b"[]"))
        calls = fake_docker(mod, first_result, second_result)   # one per call
        calls = fake_docker(mod, side_effect=lambda call: ...)  # e.g. write
                                                               # into call.volume
    Results are consumed in order; the last one repeats once exhausted, which
    is what a "every attempt fails" retry test wants.
    """

    def install(module, *results, side_effect=None):
        calls: list[DockerCall] = []
        queue = list(results)

        async def _fake(image, args, timeout_s, **kwargs):
            known = ("volume", "env", "network")
            call = DockerCall(
                image=image,
                args=list(args),
                timeout_s=timeout_s,
                volume=kwargs.get("volume"),
                env=kwargs.get("env"),
                network=kwargs.get("network"),
                extra={k: v for k, v in kwargs.items() if k not in known},
            )
            calls.append(call)

            if side_effect is not None:
                produced = side_effect(call)
                if produced is not None:
                    return produced
            if not queue:
                return make_docker_result()
            return queue.pop(0) if len(queue) > 1 else queue[0]

        monkeypatch.setattr(module, "run_hardened", _fake)
        return calls

    return install


@pytest.fixture
def no_sleep(monkeypatch):
    """Make a module's `asyncio.sleep` instant.

    Retry loops (crt.sh, IP, VATComply) wait seconds between attempts; without
    this a handful of exhausted-retry tests add several real seconds to the
    suite for no coverage.
    """

    def install(module):
        async def _instant(_seconds):
            return None

        monkeypatch.setattr(module.asyncio, "sleep", _instant)

    return install
