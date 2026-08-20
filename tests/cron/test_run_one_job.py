"""Characterization + unit tests for the `run_one_job` shared helper (Phase 4A).

`tick`'s per-job body (`_process_job`) is the execute → save → deliver → mark
sequence that fires ONE due job. Phase 4A extracts it into a module-level
`run_one_job(job, *, adapters=None, loop=None, verbose=False)` so the external
Chronos provider's `fire_due` can reuse the IDENTICAL body — no duplicated
correctness.

The first test characterizes the sequence as driven through `tick()` (proving
the extraction didn't change `tick`'s behavior); the rest unit-test the
extracted helper directly.
"""
import asyncio
import threading
from types import SimpleNamespace

import cron.scheduler as s
import pytest


@pytest.fixture
def gateway_loop():
    loop = asyncio.new_event_loop()
    loop_ready = threading.Event()

    def run_loop():
        asyncio.set_event_loop(loop)
        loop_ready.set()
        loop.run_forever()

    loop_thread = threading.Thread(target=run_loop, daemon=True)
    loop_thread.start()
    assert loop_ready.wait(timeout=2)
    try:
        yield loop
    finally:
        loop.call_soon_threadsafe(loop.stop)
        loop_thread.join(timeout=2)
        loop.close()


class _LoopBoundMattermostAdapter:
    splits_long_messages = True

    def __init__(self, gateway_loop, outcomes=(True,)):
        self.gateway_loop = gateway_loop
        self.outcomes = iter(outcomes)
        self.sends = []

    async def send(self, chat_id, content, metadata=None):
        if asyncio.get_running_loop() is not self.gateway_loop:
            raise RuntimeError("Timeout context manager should be used inside a task")
        self.sends.append((chat_id, content, metadata))
        outcome = next(self.outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        return SimpleNamespace(
            success=bool(outcome),
            message_id="mattermost-post-1" if outcome else None,
            error=None if outcome else "Mattermost rejected post",
        )


def _patch_mattermost_run(monkeypatch, gateway_loop, adapter):
    from gateway.config import GatewayConfig, Platform, PlatformConfig

    runner = SimpleNamespace(
        adapters={Platform.MATTERMOST: adapter},
        _gateway_loop=gateway_loop,
    )
    config = GatewayConfig(
        platforms={
            Platform.MATTERMOST: PlatformConfig(
                enabled=True,
                token="fake-token",
                extra={"url": "https://mattermost.invalid"},
            )
        }
    )
    marked = []

    monkeypatch.setattr("gateway.run._gateway_runner_ref", lambda: runner)
    monkeypatch.setattr("gateway.config.load_gateway_config", lambda: config)
    monkeypatch.setattr(s, "load_config", lambda: {"cron": {"wrap_response": False}})
    monkeypatch.setattr(s, "claim_dispatch", lambda _job_id: True)
    monkeypatch.setattr(
        s, "create_execution", lambda _job_id, source: {"id": "execution-1"}
    )
    monkeypatch.setattr(s, "mark_execution_running", lambda _execution_id: None)
    monkeypatch.setattr(
        s,
        "run_job",
        lambda _job, *, defer_agent_teardown=None: (
            True,
            "agent output",
            "cron result",
            None,
        ),
    )
    monkeypatch.setattr(s, "save_job_output", lambda _job_id, _output: "/tmp/out")
    monkeypatch.setattr(s, "_is_interrupted", lambda _job_id: False)
    monkeypatch.setattr(s, "_consume_interrupted_flag", lambda _job_id: False)
    monkeypatch.setattr(
        s,
        "mark_job_run",
        lambda job_id, success, error=None, delivery_error=None: marked.append(
            (job_id, success, error, delivery_error)
        ),
    )
    monkeypatch.setattr(s, "finish_execution", lambda *args, **kwargs: None)
    return runner, marked


def _patch_pipeline(monkeypatch, *, success=True, output="out", final="final response",
                    error=None, silent_marker_in=None):
    """Patch the job pipeline primitives and record the call order."""
    calls = []

    def fake_run_job(job, *, defer_agent_teardown=None):
        calls.append(("run_job", job["id"]))
        fr = final if silent_marker_in is None else silent_marker_in
        return (success, output, fr, error)

    def fake_save(jid, out):
        calls.append(("save", jid))
        return f"/tmp/{jid}.txt"

    def fake_deliver(job, content, adapters=None, loop=None):
        calls.append(("deliver", job["id"]))
        return None

    def fake_mark(jid, ok, err=None, delivery_error=None):
        calls.append(("mark", jid, ok))

    monkeypatch.setattr(s, "run_job", fake_run_job)
    monkeypatch.setattr(s, "save_job_output", fake_save)
    monkeypatch.setattr(s, "_deliver_result", fake_deliver)
    monkeypatch.setattr(s, "mark_job_run", fake_mark)
    return calls


def test_tick_process_job_sequence(monkeypatch):
    """Characterization: a single due job driven through tick() runs the
    sequence run_job → save → deliver → mark, in that order."""
    calls = _patch_pipeline(monkeypatch)
    monkeypatch.setattr(s, "get_due_jobs", lambda: [{"id": "j1", "name": "t"}])
    monkeypatch.setattr(s, "advance_next_runs", lambda ids: 1)

    s.tick(verbose=False, sync=True)

    assert [c[0] for c in calls] == ["run_job", "save", "deliver", "mark"]
    assert calls[-1] == ("mark", "j1", True)


def test_run_one_job_success_sequence(monkeypatch):
    """The extracted helper runs the same execute→save→deliver→mark sequence
    for a successful job."""
    calls = _patch_pipeline(monkeypatch)

    ok = s.run_one_job({"id": "j2", "name": "t"})

    assert ok is True
    assert [c[0] for c in calls] == ["run_job", "save", "deliver", "mark"]
    assert calls[-1] == ("mark", "j2", True)


@pytest.mark.parametrize(
    ("deliver", "expected_channel"),
    [
        ("mattermost:explicit-channel", "explicit-channel"),
        ("mattermost", "home-channel"),
    ],
)
def test_manual_mattermost_delivery_uses_live_gateway_loop(
    monkeypatch, gateway_loop, deliver, expected_channel
):
    """A manual run must not await a live adapter on asyncio.run's loop."""
    adapter = _LoopBoundMattermostAdapter(gateway_loop)
    _, marked = _patch_mattermost_run(monkeypatch, gateway_loop, adapter)
    if deliver == "mattermost":
        monkeypatch.setenv("MATTERMOST_HOME_CHANNEL", "home-channel")

    assert s.run_one_job(
        {
            "id": "manual-mattermost",
            "name": "Manual Mattermost",
            "deliver": deliver,
        }
    )

    assert marked == [("manual-mattermost", True, None, None)]
    assert adapter.sends and adapter.sends[0][0] == expected_channel


def test_scheduled_mattermost_delivery_uses_supplied_gateway_loop(
    monkeypatch, gateway_loop
):
    """Scheduled fires retain the existing adapters+loop live-router path."""
    adapter = _LoopBoundMattermostAdapter(gateway_loop)
    runner, marked = _patch_mattermost_run(monkeypatch, gateway_loop, adapter)

    assert s.run_one_job(
        {
            "id": "scheduled-mattermost",
            "name": "Scheduled Mattermost",
            "deliver": "mattermost:scheduled-channel",
        },
        adapters=runner.adapters,
        loop=gateway_loop,
    )

    assert marked == [("scheduled-mattermost", True, None, None)]
    assert adapter.sends and adapter.sends[0][0] == "scheduled-channel"


def test_mattermost_delivery_failure_does_not_overwrite_agent_success(
    monkeypatch, gateway_loop
):
    """Delivery failure is separate from a successful agent execution."""
    adapter = _LoopBoundMattermostAdapter(gateway_loop, outcomes=(False,))
    _, marked = _patch_mattermost_run(monkeypatch, gateway_loop, adapter)

    assert s.run_one_job(
        {
            "id": "failed-mattermost-delivery",
            "name": "Failed Mattermost Delivery",
            "deliver": "mattermost:channel-1",
        }
    )

    assert marked[0][:3] == ("failed-mattermost-delivery", True, None)
    assert "Mattermost rejected post" in marked[0][3]


def test_run_one_job_installs_secret_scope_under_multiplex(monkeypatch, tmp_path):
    """Regression: under profile isolation (multiplex active), run_one_job must
    execute run_job inside a profile secret scope so credential reads
    (resolve_runtime_provider -> get_secret) don't fail-close with
    UnscopedSecretError, and must tear the scope down afterward.

    Behavior contract: a scope is present during run_job and absent after,
    regardless of the concrete secret values.
    """
    from agent import secret_scope as ss

    # Point cron's home resolution at a profile whose .env carries a secret.
    (tmp_path / ".env").write_text("OPENROUTER_BASE_URL=https://openrouter.ai/api/v1\n")
    monkeypatch.setattr(s, "_get_hermes_home", lambda: tmp_path)

    scope_during_run = {}

    def fake_run_job(job, *, defer_agent_teardown=None):
        # This is where resolve_runtime_provider() would read a secret. Prove a
        # scope is installed and the profile's secret resolves without raising.
        scope_during_run["scope"] = ss.current_secret_scope()
        scope_during_run["base_url"] = ss.get_secret("OPENROUTER_BASE_URL")
        return (True, "out", "final", None)

    monkeypatch.setattr(s, "run_job", fake_run_job)
    monkeypatch.setattr(s, "save_job_output", lambda jid, out: f"/tmp/{jid}.txt")
    monkeypatch.setattr(s, "_deliver_result", lambda *a, **k: None)
    monkeypatch.setattr(s, "mark_job_run", lambda *a, **k: None)

    ss.set_multiplex_active(True)
    try:
        ok = s.run_one_job({"id": "j7", "name": "t"})
    finally:
        ss.set_multiplex_active(False)

    assert ok is True
    # Scope was installed during run_job and the profile secret resolved.
    assert scope_during_run["scope"] is not None
    assert scope_during_run["base_url"] == "https://openrouter.ai/api/v1"
    # And it was torn down after run_one_job returned (no leak).
    assert ss.current_secret_scope() is None
