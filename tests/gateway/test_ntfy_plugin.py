"""Tests for the ntfy platform-plugin adapter.

Loaded via the ``_plugin_adapter_loader`` helper so this lives under
``plugin_adapter_ntfy`` in ``sys.modules`` and cannot collide with
sibling platform-plugin tests on the same xdist worker.

Most tests target the adapter class directly. The plugin-shape tests
(``register()``, ``_env_enablement``, ``_standalone_send``, registry
presence) replace the core-file grep tests from the original PR — the
ntfy adapter no longer modifies ``gateway/config.py``, ``gateway/run.py``,
``cron/scheduler.py``, ``toolsets.py``, etc.  Everything routes through
the ``platform_registry``.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import PlatformConfig
from tests.gateway._plugin_adapter_loader import load_plugin_adapter

_ntfy = load_plugin_adapter("ntfy")

NtfyAdapter = _ntfy.NtfyAdapter
check_requirements = _ntfy.check_requirements
validate_config = _ntfy.validate_config
is_connected = _ntfy.is_connected
register = _ntfy.register
_env_enablement = _ntfy._env_enablement
_standalone_send = _ntfy._standalone_send
DEFAULT_SERVER = _ntfy.DEFAULT_SERVER
DEDUP_WINDOW_SECONDS = _ntfy.DEDUP_WINDOW_SECONDS
DEDUP_MAX_SIZE = _ntfy.DEDUP_MAX_SIZE
MAX_MESSAGE_LENGTH = _ntfy.MAX_MESSAGE_LENGTH
_APPROVAL_RESPONSE_PREFIX = _ntfy._APPROVAL_RESPONSE_PREFIX


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# 1. Platform enum (plugin-discovered, not bundled)
# ---------------------------------------------------------------------------


def test_platform_enum_resolves_via_plugin_scan():
    """The plugin filesystem scan should expose Platform("ntfy")."""
    from gateway.config import Platform
    p = Platform("ntfy")
    assert p.value == "ntfy"
    # Identity stability — repeated lookups return the same pseudo-member
    assert Platform("ntfy") is p


# ---------------------------------------------------------------------------
# 2. check_requirements / validate_config / is_connected
# ---------------------------------------------------------------------------


class TestNtfyRequirements:

    def test_returns_false_when_httpx_unavailable(self, monkeypatch):
        monkeypatch.setenv("NTFY_TOPIC", "hermes-test")
        monkeypatch.setattr(_ntfy, "HTTPX_AVAILABLE", False)
        assert check_requirements() is False

    def test_topic_is_not_a_dependency_requirement(self, monkeypatch):
        monkeypatch.setattr(_ntfy, "HTTPX_AVAILABLE", True)
        monkeypatch.delenv("NTFY_TOPIC", raising=False)
        assert check_requirements() is True

    def test_returns_true_when_topic_set_via_env(self, monkeypatch):
        monkeypatch.setattr(_ntfy, "HTTPX_AVAILABLE", True)
        monkeypatch.setenv("NTFY_TOPIC", "hermes-test")
        assert check_requirements() is True

    def test_validate_config_requires_topic(self, monkeypatch):
        monkeypatch.delenv("NTFY_TOPIC", raising=False)
        assert validate_config(PlatformConfig(enabled=True, extra={})) is False
        assert validate_config(
            PlatformConfig(enabled=True, extra={"topic": "t"})
        ) is True

    def test_is_connected_from_extra(self, monkeypatch):
        monkeypatch.delenv("NTFY_TOPIC", raising=False)
        assert is_connected(PlatformConfig(enabled=True, extra={"topic": "t"})) is True
        assert is_connected(PlatformConfig(enabled=True, extra={})) is False

    def test_is_connected_from_env(self, monkeypatch):
        monkeypatch.setenv("NTFY_TOPIC", "env-topic")
        assert is_connected(PlatformConfig(enabled=True, extra={})) is True

    def test_registry_creates_adapter_with_config_only_topic(self, monkeypatch):
        from gateway.platform_registry import PlatformEntry, PlatformRegistry

        monkeypatch.setattr(_ntfy, "HTTPX_AVAILABLE", True)
        monkeypatch.delenv("NTFY_TOPIC", raising=False)
        ctx = MagicMock()
        register(ctx)
        entry = PlatformEntry(
            source="plugin",
            **ctx.register_platform.call_args.kwargs,
        )
        registry = PlatformRegistry()
        registry.register(entry)

        config = PlatformConfig(enabled=True, extra={"topic": "config-topic"})
        adapter = registry.create_adapter("ntfy", config)

        assert isinstance(adapter, NtfyAdapter)
        assert adapter._topic == "config-topic"

# ---------------------------------------------------------------------------
# 3. Adapter init
# ---------------------------------------------------------------------------


class TestNtfyAdapterInit:


    def test_topic_read_from_env(self, monkeypatch):
        monkeypatch.setenv("NTFY_TOPIC", "env-topic")
        config = PlatformConfig(enabled=True, extra={})
        adapter = NtfyAdapter(config)
        assert adapter._topic == "env-topic"


    def test_publish_topic_uses_extra_value(self):
        config = PlatformConfig(
            enabled=True,
            extra={"topic": "hermes-in", "publish_topic": "hermes-out"},
        )
        adapter = NtfyAdapter(config)
        assert adapter._publish_topic == "hermes-out"


    def test_token_read_from_env(self, monkeypatch):
        monkeypatch.setenv("NTFY_TOKEN", "env-token")
        config = PlatformConfig(enabled=True, extra={"topic": "t"})
        adapter = NtfyAdapter(config)
        assert adapter._token == "env-token"


# ---------------------------------------------------------------------------
# 4. Auth headers
# ---------------------------------------------------------------------------


class TestAuthHeaders:

    def _make_adapter(self, token=""):
        config = PlatformConfig(enabled=True, extra={"topic": "t", "token": token})
        return NtfyAdapter(config)

    def test_no_token_returns_empty_dict(self):
        adapter = self._make_adapter(token="")
        assert adapter._auth_headers() == {}

    def test_bearer_token_for_plain_token(self):
        adapter = self._make_adapter(token="myapitoken")
        headers = adapter._auth_headers()
        assert headers["Authorization"] == "Bearer myapitoken"


# ---------------------------------------------------------------------------
# 5. Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:

    def _make_adapter(self):
        return NtfyAdapter(PlatformConfig(enabled=True, extra={"topic": "t"}))

    def test_first_message_not_duplicate(self):
        adapter = self._make_adapter()
        assert adapter._is_duplicate("msg-1") is False

    def test_second_occurrence_is_duplicate(self):
        adapter = self._make_adapter()
        adapter._is_duplicate("msg-1")
        assert adapter._is_duplicate("msg-1") is True


# ---------------------------------------------------------------------------
# 6. connect() / disconnect()
# ---------------------------------------------------------------------------


class TestConnect:


    def test_connect_starts_stream_task(self, monkeypatch):
        monkeypatch.setattr(_ntfy, "HTTPX_AVAILABLE", True)
        config = PlatformConfig(enabled=True, extra={"topic": "hermes-test"})
        adapter = NtfyAdapter(config)

        with patch.object(adapter, "_run_stream", new_callable=AsyncMock):
            with patch.object(_ntfy, "httpx") as mock_httpx:
                mock_httpx.AsyncClient.return_value = MagicMock()
                result = _run(adapter.connect())

        assert result is True
        assert adapter._stream_task is not None
        adapter._stream_task.cancel()
        try:
            _run(adapter._stream_task)
        except (asyncio.CancelledError, Exception):
            pass


    def test_disconnect_cancels_stream_task(self):
        adapter = NtfyAdapter(PlatformConfig(enabled=True, extra={"topic": "t"}))

        async def _hang():
            await asyncio.sleep(0.2)

        loop = asyncio.get_event_loop()
        adapter._stream_task = loop.create_task(_hang())
        adapter._http_client = AsyncMock()
        adapter._running = True

        _run(adapter.disconnect())
        assert adapter._stream_task is None


# ---------------------------------------------------------------------------
# 7. send()
# ---------------------------------------------------------------------------


class TestSend:

    def _make_adapter(self, topic="hermes-in", publish_topic="", token="", markdown=False):
        extra: dict = {"topic": topic, "token": token}
        if publish_topic:
            extra["publish_topic"] = publish_topic
        if markdown:
            extra["markdown"] = True
        return NtfyAdapter(PlatformConfig(enabled=True, extra=extra))


    def test_send_posts_to_publish_topic(self):
        adapter = self._make_adapter(topic="hermes-in", publish_topic="hermes-out")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "abc123"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._http_client = mock_client

        result = _run(adapter.send("hermes-in", "Hello ntfy!"))
        assert result.success is True
        assert result.message_id == "abc123"

        posted_url = mock_client.post.call_args[0][0]
        assert posted_url.endswith("/hermes-out")

    def test_send_falls_back_to_subscribe_topic(self):
        adapter = self._make_adapter(topic="hermes-in")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._http_client = mock_client

        result = _run(adapter.send("hermes-in", "Hello!"))
        assert result.success is True
        posted_url = mock_client.post.call_args[0][0]
        assert posted_url.endswith("/hermes-in")

    def test_send_uses_metadata_publish_topic(self):
        adapter = self._make_adapter(topic="hermes-in")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._http_client = mock_client

        result = _run(adapter.send(
            "hermes-in", "Hi!", metadata={"publish_topic": "override-out"}
        ))
        assert result.success is True
        posted_url = mock_client.post.call_args[0][0]
        assert posted_url.endswith("/override-out")


    def test_send_handles_timeout(self):
        adapter = self._make_adapter(topic="hermes-in")

        class _FakeTimeout(Exception):
            pass

        fake_httpx = MagicMock()
        fake_httpx.TimeoutException = _FakeTimeout

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=_FakeTimeout("timed out"))
        adapter._http_client = mock_client

        with patch.object(_ntfy, "httpx", fake_httpx):
            result = _run(adapter.send("hermes-in", "Hello!"))

        assert result.success is False
        assert "timeout" in result.error.lower()


    def test_get_chat_info_returns_dict(self):
        adapter = NtfyAdapter(PlatformConfig(enabled=True, extra={"topic": "t"}))
        info = _run(adapter.get_chat_info("hermes-in"))
        assert info["name"] == "hermes-in"
        assert info["type"] == "dm"


# ---------------------------------------------------------------------------
# 8. Inbound message processing (identity invariant — security-critical)
# ---------------------------------------------------------------------------


class TestOnMessage:

    def _make_adapter(self):
        return NtfyAdapter(PlatformConfig(enabled=True, extra={"topic": "hermes-in"}))

    def test_message_dispatched_to_handler(self):
        adapter = self._make_adapter()
        calls = []

        async def handler(event):
            calls.append(event)

        adapter.set_message_handler(handler)

        event = {
            "id": "evt-001",
            "event": "message",
            "topic": "hermes-in",
            "message": "Hello from ntfy",
            "time": 1700000000,
        }
        _run(adapter._on_message(event))
        assert len(calls) == 1
        assert calls[0].text == "Hello from ntfy"

    def test_empty_message_skipped(self):
        adapter = self._make_adapter()
        calls = []

        async def handler(event):
            calls.append(event)

        adapter.set_message_handler(handler)
        _run(adapter._on_message({
            "id": "x", "event": "message", "topic": "t", "message": "", "time": None
        }))
        assert calls == []

    def test_duplicate_message_skipped(self):
        adapter = self._make_adapter()
        calls = []

        async def handler(event):
            calls.append(event)

        adapter.set_message_handler(handler)
        event = {"id": "dup-1", "event": "message", "topic": "hermes-in", "message": "hi", "time": None}
        _run(adapter._on_message(event))
        _run(adapter._on_message(event))
        assert len(calls) == 1

    def test_own_tagged_message_skipped(self):
        """An incoming event carrying the adapter's echo tag is the agent's
        own reply echoed back by ntfy — it must not be dispatched, otherwise
        the agent replies to itself forever (issue #34447)."""
        adapter = self._make_adapter()
        calls = []

        async def handler(event):
            calls.append(event)

        adapter.set_message_handler(handler)
        _run(adapter._on_message({
            "id": "echo-1",
            "event": "message",
            "topic": "hermes-in",
            "message": "my own reply",
            "tags": [_ntfy._ECHO_TAG],
            "time": None,
        }))
        assert calls == []


# ---------------------------------------------------------------------------
# 9. _env_enablement() — env-only auto-config
# ---------------------------------------------------------------------------


class TestEnvEnablement:

    def test_returns_none_without_topic(self, monkeypatch):
        monkeypatch.delenv("NTFY_TOPIC", raising=False)
        assert _env_enablement() is None


    def test_markdown_truthy_values(self, monkeypatch):
        monkeypatch.setenv("NTFY_TOPIC", "hermes-in")
        for val in ("true", "1", "yes", "TRUE"):
            monkeypatch.setenv("NTFY_MARKDOWN", val)
            assert _env_enablement()["markdown"] is True


    def test_home_channel_override(self, monkeypatch):
        monkeypatch.setenv("NTFY_TOPIC", "hermes-in")
        monkeypatch.setenv("NTFY_HOME_CHANNEL", "alerts")
        monkeypatch.setenv("NTFY_HOME_CHANNEL_NAME", "Alerts Channel")
        seed = _env_enablement()
        assert seed["home_channel"]["chat_id"] == "alerts"
        assert seed["home_channel"]["name"] == "Alerts Channel"


# ---------------------------------------------------------------------------
# 10. _standalone_send() — out-of-process cron delivery
# ---------------------------------------------------------------------------


class TestStandaloneSend:

    def test_errors_without_topic(self, monkeypatch):
        monkeypatch.delenv("NTFY_TOPIC", raising=False)
        monkeypatch.delenv("NTFY_PUBLISH_TOPIC", raising=False)
        pconfig = MagicMock()
        pconfig.extra = {}
        result = _run(_standalone_send(pconfig, "", "hello"))
        assert "error" in result
        assert "NTFY_TOPIC" in result["error"]


    def test_emits_echo_tag_header(self, monkeypatch):
        """Out-of-process cron / send_message deliveries also carry the echo
        tag, so a gateway subscribed to the same topic skips them too."""
        monkeypatch.setenv("NTFY_TOPIC", "hermes-in")
        pconfig = MagicMock()
        pconfig.extra = {"topic": "hermes-in"}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "id-99"}
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(_ntfy, "httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_client
            _run(_standalone_send(pconfig, "hermes-in", "hi"))

        headers = mock_client.post.call_args[1]["headers"]
        assert headers.get("X-Tags") == _ntfy._ECHO_TAG


# ---------------------------------------------------------------------------
# 11. register() — plugin-side metadata
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 12. Robustness — token hygiene + fatal-state propagation
# ---------------------------------------------------------------------------


class TestTokenHygiene:
    """``_build_auth_header`` must strip pasted-token whitespace; pasted
    tokens often carry trailing newlines that break the Authorization line."""

    def test_trailing_whitespace_stripped(self):
        assert _ntfy._build_auth_header("  tok123  ") == {"Authorization": "Bearer tok123"}


    def test_whitespace_only_returns_empty(self):
        assert _ntfy._build_auth_header("   \n  ") == {}


class TestFatalErrorPropagation:
    """When the stream hits 401/404, the adapter must transition to the
    ``fatal`` state via ``_set_fatal_error`` so the gateway's runtime
    status reflects reality instead of staying 'connected'."""

    def test_401_sets_fatal_unauthorized(self):
        adapter = NtfyAdapter(PlatformConfig(enabled=True, extra={"topic": "t"}))
        adapter._http_client = MagicMock()

        # Mock the streaming response
        mock_response = MagicMock()
        mock_response.status_code = 401
        # async-context-manager flavor for httpx.stream
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        adapter._http_client.stream = MagicMock(return_value=mock_cm)

        fake_httpx = MagicMock()
        fake_httpx.Timeout = MagicMock()
        with patch.object(_ntfy, "httpx", fake_httpx):
            with pytest.raises(_ntfy._FatalStreamError):
                _run(adapter._consume_stream("https://ntfy.example/t/json", {}))

        assert adapter.has_fatal_error is True
        assert adapter._fatal_error_code == "ntfy_unauthorized"
        assert adapter._fatal_error_retryable is False


class TestTruncateHelper:
    """``_truncate_body`` is shared between adapter.send() (inline truncation
    today, may migrate) and ``_standalone_send``. It must cap to
    MAX_MESSAGE_LENGTH and return bytes."""

    def test_short_message_passes_through(self):
        assert _ntfy._truncate_body("hi", context="test") == b"hi"


    def test_unicode_message_encoded(self):
        result = _ntfy._truncate_body("héllo 🔔", context="test")
        assert result == "héllo 🔔".encode("utf-8")


# ---------------------------------------------------------------------------
# 13. Cross-platform dangerous-command approvals
# ---------------------------------------------------------------------------


class TestApprovalNotifications:
    def _make_adapter(self, *, expiry=60):
        config = PlatformConfig(
            enabled=True,
            extra={
                "server": "https://ntfy.example.com",
                "topic": "hermes-responses",
                "publish_topic": "hermes-alerts",
                "approval_notifications": True,
                "approval_expiry_seconds": expiry,
                "token": "secret-publish-token",
            },
        )
        adapter = NtfyAdapter(config)
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"id": "approval-notification-id"}
        adapter._http_client = MagicMock()
        adapter._http_client.post = AsyncMock(return_value=response)
        return adapter

    def _send(self, adapter, **kwargs):
        values = {
            "command": "rm -rf ./build",
            "description": "recursive deletion",
            "session_key": "mattermost:channel:thread-42",
        }
        values.update(kwargs)
        return _run(adapter.send_exec_approval(**values))

    def _action_token(self, adapter, label):
        payload = adapter._http_client.post.call_args.kwargs["json"]
        action = next(item for item in payload["actions"] if item["label"] == label)
        assert action["body"].startswith(_APPROVAL_RESPONSE_PREFIX)
        return action["body"][len(_APPROVAL_RESPONSE_PREFIX):]

    def test_notification_uses_native_actions_without_credentials(self):
        adapter = self._make_adapter()
        result = self._send(
            adapter,
            open_url="https://mattermost.example.com/_redirect/pl/post-9",
        )

        assert result.success is True
        call = adapter._http_client.post.call_args
        assert call.args[0] == "https://ntfy.example.com"
        payload = call.kwargs["json"]
        assert payload["topic"] == "hermes-alerts"
        assert [action["label"] for action in payload["actions"]] == [
            "Approve once", "Deny", "Open thread",
        ]
        assert payload["actions"][0]["action"] == "http"
        assert payload["actions"][0]["method"] == "POST"
        assert payload["actions"][0]["url"] == "https://ntfy.example.com/hermes-responses"
        assert payload["actions"][2] == {
            "action": "view",
            "label": "Open thread",
            "url": "https://mattermost.example.com/_redirect/pl/post-9",
            "clear": False,
        }
        serialized = str(payload["actions"])
        assert "secret-publish-token" not in serialized
        assert "mattermost:channel:thread-42" not in serialized
        assert "Authorization" not in serialized

    def test_approve_resolves_exact_original_session_once(self):
        adapter = self._make_adapter()
        self._send(adapter)
        token = self._action_token(adapter, "Approve once")

        with patch("tools.approval.resolve_gateway_approval", return_value=1) as resolve:
            assert adapter._handle_approval_response(
                f"{_APPROVAL_RESPONSE_PREFIX}{token}"
            ) is True

        resolve.assert_called_once_with("mattermost:channel:thread-42", "once")

    def test_deny_resolves_exact_original_session(self):
        adapter = self._make_adapter()
        self._send(adapter, session_key="discord:dm:user-7")
        token = self._action_token(adapter, "Deny")

        with patch("tools.approval.resolve_gateway_approval", return_value=1) as resolve:
            assert adapter._handle_approval_response(
                f"{_APPROVAL_RESPONSE_PREFIX}{token}"
            ) is True

        resolve.assert_called_once_with("discord:dm:user-7", "deny")

    def test_unknown_and_reused_ids_are_rejected(self):
        adapter = self._make_adapter()
        self._send(adapter)
        token = self._action_token(adapter, "Approve once")

        with patch("tools.approval.resolve_gateway_approval", return_value=1) as resolve:
            assert adapter._handle_approval_response(
                f"{_APPROVAL_RESPONSE_PREFIX}unknown"
            ) is False
            assert adapter._handle_approval_response(
                f"{_APPROVAL_RESPONSE_PREFIX}{token}"
            ) is True
            assert adapter._handle_approval_response(
                f"{_APPROVAL_RESPONSE_PREFIX}{token}"
            ) is False

        resolve.assert_called_once()

    def test_expired_id_is_rejected_without_resolution(self):
        adapter = self._make_adapter(expiry=1)
        self._send(adapter)
        token = self._action_token(adapter, "Approve once")
        request = next(iter(adapter._pending_approvals.values()))
        request["expires_at"] = 0

        with patch("tools.approval.resolve_gateway_approval") as resolve:
            assert adapter._handle_approval_response(
                f"{_APPROVAL_RESPONSE_PREFIX}{token}"
            ) is False
        resolve.assert_not_called()

    def test_response_is_intercepted_before_normal_message_handling(self):
        adapter = self._make_adapter()
        self._send(adapter)
        token = self._action_token(adapter, "Approve once")
        normal_messages = []

        async def handler(event):
            normal_messages.append(event)

        adapter.set_message_handler(handler)
        with patch("tools.approval.resolve_gateway_approval", return_value=1) as resolve:
            _run(adapter._on_message({
                "id": "ntfy-action-response",
                "event": "message",
                "topic": "hermes-responses",
                "message": f"{_APPROVAL_RESPONSE_PREFIX}{token}",
            }))

        resolve.assert_called_once_with("mattermost:channel:thread-42", "once")
        assert normal_messages == []

    def test_pending_state_is_bounded(self, monkeypatch):
        monkeypatch.setattr(_ntfy, "_MAX_PENDING_APPROVALS", 2)
        adapter = self._make_adapter()
        for index in range(3):
            self._send(adapter, session_key=f"session-{index}")
        assert len(adapter._pending_approvals) == 2
        assert len(adapter._approval_tokens) == 4


class TestApprovalFanoutGating:
    def test_requires_explicit_enablement_and_skips_ntfy_origins(self):
        from gateway.config import Platform
        from gateway.run import _ntfy_approval_fanout_adapter

        adapter = NtfyAdapter(PlatformConfig(
            enabled=True,
            extra={"topic": "approvals", "approval_notifications": False},
        ))
        runner = MagicMock()
        runner._authorization_adapter.return_value = adapter
        source = SimpleNamespace(platform=Platform.TELEGRAM, profile="work")

        assert _ntfy_approval_fanout_adapter(runner, source) is None
        adapter.approval_notifications_enabled = True
        assert _ntfy_approval_fanout_adapter(runner, source) is adapter
        runner._authorization_adapter.assert_called_with(Platform("ntfy"), "work")

        ntfy_source = SimpleNamespace(platform=Platform("ntfy"), profile="work")
        assert _ntfy_approval_fanout_adapter(runner, ntfy_source) is None

    def test_mattermost_permalink_uses_current_post_without_lookup(self):
        from gateway.config import Platform
        from gateway.run import _mattermost_approval_permalink

        source = SimpleNamespace(
            platform=Platform.MATTERMOST,
            message_id="source-post",
            thread_id="thread-root",
        )
        adapter = SimpleNamespace(_base_url="https://mattermost.example.com/")
        assert _mattermost_approval_permalink(source, adapter, "latest-post") == (
            "https://mattermost.example.com/_redirect/pl/latest-post"
        )
