"""BlueBubbles iMessage platform adapter.

Uses the local BlueBubbles macOS server for outbound REST sends and inbound
webhooks.  Supports text messaging, media attachments (images, voice, video,
documents), tapback reactions, typing indicators, and read receipts.

Architecture based on PR #5869 (benjaminsehl) with inbound attachment
downloading from PR #4588 (YuhangLin).
"""

import asyncio
import json
import logging
import os
import re
import uuid
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
    cache_image_from_bytes,
    cache_audio_from_bytes,
    cache_document_from_bytes,
)
from gateway.platforms.helpers import compile_mention_patterns, strip_markdown
from hermes_constants import get_hermes_home
from utils import atomic_json_write

from .media_cache import ext_for_mime

# Historical BlueBubbles mime→ext maps, preserved verbatim as overrides for
# the shared dispatch in gateway.platforms.media_cache. Both maps are
# CLOSED: unlisted mimes fall back to .jpg / .mp3 (never mimetypes).
_BLUEBUBBLES_IMAGE_EXT_OVERRIDES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/heic": ".jpg",  # preserves historical bluebubbles mapping
    "image/heif": ".jpg",  # preserves historical bluebubbles mapping
    "image/tiff": ".jpg",  # preserves historical bluebubbles mapping
}
_BLUEBUBBLES_AUDIO_EXT_OVERRIDES = {
    "audio/mp3": ".mp3",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/x-caf": ".mp3",  # preserves historical bluebubbles mapping
    "audio/mp4": ".m4a",
    "audio/aac": ".m4a",  # preserves historical bluebubbles mapping (shared table says .aac)
}

from agent.secret_scope import UnscopedSecretError as _UnscopedSecretError
from agent.secret_scope import get_secret as _scoped_get_secret


def _get_scoped_secret(name, default=None):
    """Scope-aware credential read with the default-profile startup fallback.

    Secondary profiles construct their adapters under a profile secret
    scope -- the scope is authoritative and a scoped miss returns ``default``
    (no cross-profile borrow from ``os.environ``, which may hold another
    profile's value). The DEFAULT profile's adapter constructs and sends
    *unscoped* under multiplexing, where a bare ``get_secret`` would raise
    ``UnscopedSecretError`` and crash this path; there ``os.environ`` is that
    profile's own value, so fall back to it. Same pattern as the Slack
    ``SLACK_APP_TOKEN`` read (#59739) and
    ``gateway/platforms/whatsapp_common.py::_get_wsecret``.
    """
    try:
        val = _scoped_get_secret(name, default)
    except _UnscopedSecretError:
        val = os.getenv(name)
    return val if val is not None else default


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_WEBHOOK_HOST = "127.0.0.1"
# BlueBubbles webhook events are small JSON/form payloads; attachments come
# through the REST API, not the webhook. 1 MiB is generous headroom while
# keeping oversized/chunked bodies from being buffered unbounded.
_WEBHOOK_MAX_BODY_BYTES = 1_048_576
DEFAULT_WEBHOOK_PORT = 8645
DEFAULT_WEBHOOK_PATH = "/bluebubbles-webhook"
MAX_TEXT_LENGTH = 4000

# BlueBubbles/iMessage does not expose a stable bot mention identity like
# Slack (<@U...>), Telegram (@botname), or Matrix (MXID). When users opt into
# group mention gating without custom aliases, use conservative Hermes wake
# words so `require_mention: true` is a one-line enablement path.
DEFAULT_MENTION_PATTERNS = [
    r"(?<![\w@])@?hermes\s+agent\b[,:\-]?",
    r"(?<![\w@])@?hermes\b[,:\-]?",
]

# Tapback reaction codes (BlueBubbles associatedMessageType values)
_TAPBACK_ADDED = {
    2000: "love", 2001: "like", 2002: "dislike",
    2003: "laugh", 2004: "emphasize", 2005: "question",
}
_TAPBACK_REMOVED = {
    3000: "love", 3001: "like", 3002: "dislike",
    3003: "laugh", 3004: "emphasize", 3005: "question",
}

# Webhook event types that carry user messages
_MESSAGE_EVENTS = {"new-message", "message", "updated-message"}

# Log redaction patterns
_PHONE_RE = re.compile(r"\+?\d{7,15}")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")

_GUID_CACHE_SIZE = 500  # LRU cap for resolved chat-GUID lookups
_MESSAGE_DEDUPE_SIZE = 1000
_POLL_DEFAULT_INTERVAL_SECONDS = 5.0
_POLL_QUERY_LIMIT = 100
_POLL_MAX_PAGES = 10
_POLL_STATE_FILENAME = "bluebubbles_poll.json"


def _redact(text: str) -> str:
    """Redact phone numbers and emails from log output."""
    text = _PHONE_RE.sub("[REDACTED]", text)
    text = _EMAIL_RE.sub("[REDACTED]", text)
    return text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def check_bluebubbles_requirements() -> bool:
    try:
        import aiohttp  # noqa: F401
        import httpx  # noqa: F401
    except ImportError:
        return False
    return True


def _normalize_server_url(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if not re.match(r"^https?://", value, flags=re.I):
        value = f"http://{value}"
    return value.rstrip("/")





# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class BlueBubblesAdapter(BasePlatformAdapter):
    platform = Platform.BLUEBUBBLES
    SUPPORTS_MESSAGE_EDITING = False
    MAX_MESSAGE_LENGTH = MAX_TEXT_LENGTH
    splits_long_messages = True  # send() chunks via truncate_message(MAX_MESSAGE_LENGTH)

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform.BLUEBUBBLES)
        extra = config.extra or {}
        self.server_url = _normalize_server_url(
            extra.get("server_url") or os.getenv("BLUEBUBBLES_SERVER_URL", "")
        )
        self.password = extra.get("password") or _get_scoped_secret("BLUEBUBBLES_PASSWORD", "")
        self.webhook_host = (
            extra.get("webhook_host")
            or os.getenv("BLUEBUBBLES_WEBHOOK_HOST", DEFAULT_WEBHOOK_HOST)
        )
        self.webhook_port = int(
            extra.get("webhook_port")
            or os.getenv("BLUEBUBBLES_WEBHOOK_PORT", str(DEFAULT_WEBHOOK_PORT))
        )
        self.webhook_path = (
            extra.get("webhook_path")
            or os.getenv("BLUEBUBBLES_WEBHOOK_PATH", DEFAULT_WEBHOOK_PATH)
        )
        if not str(self.webhook_path).startswith("/"):
            self.webhook_path = f"/{self.webhook_path}"
        self.send_read_receipts = bool(extra.get("send_read_receipts", True))
        _require_mention = extra.get("require_mention")
        if _require_mention is None:
            _require_mention = os.getenv("BLUEBUBBLES_REQUIRE_MENTION")
        self.require_mention = str(_require_mention).strip().lower() in {"true", "1", "yes", "on"}
        self._mention_patterns = self._compile_mention_patterns(
            extra["mention_patterns"]
            if "mention_patterns" in extra
            else os.getenv("BLUEBUBBLES_MENTION_PATTERNS")
        )
        self.client: Optional[httpx.AsyncClient] = None
        self._runner = None
        self._private_api_enabled: Optional[bool] = None
        self._helper_connected: bool = False
        self._guid_cache: OrderedDict[str, str] = OrderedDict()
        raw_poll_interval = extra.get(
            "poll_interval_seconds",
            extra.get("poll_interval", _POLL_DEFAULT_INTERVAL_SECONDS),
        )
        if extra.get("poll_enabled") is False:
            raw_poll_interval = 0
        try:
            self.poll_interval_seconds = max(0.0, float(raw_poll_interval))
        except (TypeError, ValueError):
            logger.warning(
                "[bluebubbles] invalid polling interval; using %.1f seconds",
                _POLL_DEFAULT_INTERVAL_SECONDS,
            )
            self.poll_interval_seconds = _POLL_DEFAULT_INTERVAL_SECONDS
        # Capture the active profile home while the adapter is constructed.
        # A multiplexed gateway may later run other tasks under another
        # context-local profile override.
        self._poll_state_path = (
            get_hermes_home() / "state" / _POLL_STATE_FILENAME
        )
        self._poll_task: Optional[asyncio.Task] = None
        self._seen_message_ids: OrderedDict[str, None] = OrderedDict()
        self._inflight_message_ids: Dict[str, set[str]] = {}

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    def _api_url(self, path: str) -> str:
        sep = "&" if "?" in path else "?"
        return f"{self.server_url}{path}{sep}password={quote(self.password, safe='')}"

    @staticmethod
    def _compile_mention_patterns(raw: Any) -> List[re.Pattern]:
        """Compile group-mention wake words from config/env.

        ``raw`` is a list (from config or env JSON), a string (raw env var:
        JSON list, or comma/newline-separated), or None (use Hermes defaults).
        """
        return compile_mention_patterns(
            raw,
            log_prefix="bluebubbles",
            defaults=DEFAULT_MENTION_PATTERNS,
            logger_=logger,
        )

    def _message_matches_mention_patterns(self, text: str) -> bool:
        if not text or not self._mention_patterns:
            return False
        return any(pattern.search(text) for pattern in self._mention_patterns)

    def _clean_mention_text(self, text: str) -> str:
        """Strip a leading BlueBubbles wake word before dispatch.

        Custom mention patterns are regular expressions, so stripping only a
        leading match avoids deleting ordinary words later in the prompt.
        """
        if not text:
            return text
        for pattern in self._mention_patterns:
            match = pattern.match(text.lstrip())
            if match:
                cleaned = text.lstrip()[match.end():].lstrip(" ,:-")
                return cleaned or text
        return text

    async def _api_get(self, path: str) -> Dict[str, Any]:
        assert self.client is not None
        res = await self.client.get(self._api_url(path))
        res.raise_for_status()
        return res.json()

    async def _api_post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        assert self.client is not None
        res = await self.client.post(self._api_url(path), json=payload)
        res.raise_for_status()
        return res.json()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        if not self.server_url or not self.password:
            logger.error(
                "[bluebubbles] BLUEBUBBLES_SERVER_URL and BLUEBUBBLES_PASSWORD are required"
            )
            return False
        from aiohttp import web

        # Tighter keepalive so idle CLOSE_WAIT drains promptly (#18451).
        from gateway.platforms._http_client_limits import platform_httpx_limits
        self.client = httpx.AsyncClient(timeout=30.0, limits=platform_httpx_limits())
        try:
            await self._api_get("/api/v1/ping")
            info = await self._api_get("/api/v1/server/info")
            server_data = (info or {}).get("data", {})
            self._private_api_enabled = bool(server_data.get("private_api"))
            self._helper_connected = bool(server_data.get("helper_connected"))
            logger.info(
                "[bluebubbles] connected to %s (private_api=%s, helper=%s)",
                self.server_url,
                self._private_api_enabled,
                self._helper_connected,
            )
        except Exception as exc:
            logger.error(
                "[bluebubbles] cannot reach server at %s: %s", self.server_url, exc
            )
            if self.client:
                await self.client.aclose()
                self.client = None
            return False

        # Explicit body cap: BlueBubbles webhook events are small JSON (or
        # form-encoded) payloads. client_max_size makes aiohttp enforce the
        # cap on every read path — including chunked requests that carry no
        # Content-Length (same pattern as webhook.py / raft, #58536/#58902).
        app = web.Application(client_max_size=_WEBHOOK_MAX_BODY_BYTES)
        app.router.add_get("/health", lambda _: web.Response(text="ok"))
        app.router.add_post(self.webhook_path, self._handle_webhook)
        # The webhook auth value is carried in the query string because the
        # BlueBubbles webhook API cannot send custom headers. Do not let
        # aiohttp access logs write that request target to agent.log.
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.webhook_host, self.webhook_port)
        await site.start()
        self._mark_connected()
        logger.info(
            "[bluebubbles] webhook listening on http://%s:%s%s",
            self.webhook_host,
            self.webhook_port,
            self.webhook_path,
        )

        # Register webhook with BlueBubbles server
        # This is required for the server to know where to send events
        await self._register_webhook()

        if self.poll_interval_seconds > 0:
            self._poll_task = asyncio.create_task(
                self._poll_messages_loop(), name="bluebubbles-message-poll"
            )

        return True

    async def disconnect(self) -> None:
        poll_task = self._poll_task
        self._poll_task = None
        if poll_task:
            poll_task.cancel()
            await asyncio.gather(poll_task, return_exceptions=True)

        # Unregister webhook before cleaning up
        await self._unregister_webhook()

        if self.client:
            await self.client.aclose()
            self.client = None
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        self._mark_disconnected()

    # ------------------------------------------------------------------
    # Inbound polling fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _record_rowid(record: Dict[str, Any]) -> Optional[int]:
        # BlueBubbles' serializer exposes the Messages database ROWID as
        # ``originalROWID``. Keep the other spellings for webhook/version
        # compatibility and for installations using an API-compatible server.
        for key in ("originalROWID", "ROWID", "rowid", "id"):
            value = record.get(key)
            if isinstance(value, bool):
                continue
            try:
                if value is not None:
                    return int(value)
            except (TypeError, ValueError):
                continue
        return None

    def _record_dedupe_keys(self, record: Dict[str, Any]) -> set[str]:
        keys: set[str] = set()
        guid = self._value(record.get("guid"), record.get("messageGuid"))
        if guid:
            keys.add(f"guid:{guid}")
        rowid = self._record_rowid(record)
        if rowid is not None:
            keys.add(f"rowid:{rowid}")
        return keys

    def _remember_message_keys(self, keys: set[str]) -> None:
        for key in keys:
            self._seen_message_ids[key] = None
            self._seen_message_ids.move_to_end(key)
        while len(self._seen_message_ids) > _MESSAGE_DEDUPE_SIZE:
            self._seen_message_ids.popitem(last=False)

    def _claim_message(
        self, record: Dict[str, Any]
    ) -> tuple[Optional[set[str]], bool]:
        keys = self._record_dedupe_keys(record)
        seen = keys.intersection(self._seen_message_ids)
        if seen:
            # Learn every alias supplied by this copy. This matters when a
            # webhook contains only a GUID but the query record later adds a
            # ROWID (or vice versa).
            self._remember_message_keys(keys)
            return None, False

        inflight_claim = next(
            (
                self._inflight_message_ids[key]
                for key in keys
                if key in self._inflight_message_ids
            ),
            None,
        )
        if inflight_claim is not None:
            # Share the mutable claim so the original processor remembers any
            # GUID/ROWID alias discovered by the racing delivery.
            inflight_claim.update(keys)
            for key in keys:
                self._inflight_message_ids[key] = inflight_claim
            return None, False

        if not keys:
            return None, True
        claim = set(keys)
        for key in claim:
            self._inflight_message_ids[key] = claim
        return claim, True

    def _finish_message_claim(
        self, claim: Optional[set[str]], *, remember: bool
    ) -> None:
        if claim is None:
            return
        for key in claim:
            if self._inflight_message_ids.get(key) is claim:
                self._inflight_message_ids.pop(key, None)
        if remember:
            self._remember_message_keys(claim)

    def _load_poll_mark(self) -> Optional[Dict[str, Any]]:
        try:
            data = json.loads(self._poll_state_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return None
            rowid = data.get("rowid")
            guid = data.get("guid")
            if rowid is not None:
                rowid = int(rowid)
            if rowid is None and not isinstance(guid, str):
                return None
            return {"rowid": rowid, "guid": guid if isinstance(guid, str) else None}
        except (OSError, ValueError, TypeError):
            return None

    def _persist_poll_mark(self, record: Dict[str, Any]) -> bool:
        rowid = self._record_rowid(record)
        guid = self._value(record.get("guid"), record.get("messageGuid"))
        if rowid is None and not guid:
            return False
        return self._persist_poll_mark_values(rowid=rowid, guid=guid)

    def _persist_poll_mark_values(
        self, *, rowid: Optional[int], guid: Optional[str]
    ) -> bool:
        try:
            atomic_json_write(
                self._poll_state_path,
                {"rowid": rowid, "guid": guid},
                indent=None,
                separators=(",", ":"),
            )
            return True
        except OSError as exc:
            logger.warning(
                "[bluebubbles] could not persist polling checkpoint (%s)",
                type(exc).__name__,
            )
            return False

    @staticmethod
    def _record_at_or_before_mark(
        record: Dict[str, Any], mark: Dict[str, Any]
    ) -> bool:
        rowid = BlueBubblesAdapter._record_rowid(record)
        mark_rowid = mark.get("rowid")
        if rowid is not None and mark_rowid is not None:
            return rowid <= mark_rowid
        guid = record.get("guid") or record.get("messageGuid")
        return bool(guid and mark.get("guid") and guid == mark["guid"])

    async def _query_message_page(self, offset: int) -> List[Dict[str, Any]]:
        response = await self._api_post(
            "/api/v1/message/query",
            {
                "limit": _POLL_QUERY_LIMIT,
                "offset": offset,
                "sort": "DESC",
                # These are TypeORM relation names accepted by BlueBubbles'
                # query API. The serialized response fields are plural
                # (``chats``/``attachments``), but the requested relations are
                # singular.
                "with": ["chat", "attachment", "handle"],
            },
        )
        records = response.get("data") if isinstance(response, dict) else None
        if not isinstance(records, list):
            raise ValueError("message query response did not contain a record list")
        if any(not isinstance(record, dict) for record in records):
            raise ValueError("message query response contained an invalid record")
        return records

    async def _poll_messages_once(self) -> None:
        mark = self._load_poll_mark()
        first_page = await self._query_message_page(0)
        if not first_page:
            if mark is None:
                # Record an explicit empty baseline. Otherwise the first
                # message arriving after an empty first install would be
                # mistaken for pre-existing history and silently skipped.
                self._persist_poll_mark_values(rowid=0, guid=None)
            return

        newest_record = first_page[0]
        if mark is None:
            # A missing or unreadable checkpoint is treated as a first install:
            # seed from the newest current record and never replay history.
            self._persist_poll_mark(newest_record)
            return

        new_records: List[Dict[str, Any]] = []
        page = first_page
        complete = False
        for page_number in range(_POLL_MAX_PAGES):
            for record in page:
                if self._record_at_or_before_mark(record, mark):
                    complete = True
                    break
                new_records.append(record)
            if complete or len(page) < _POLL_QUERY_LIMIT:
                complete = True
                break
            if page_number + 1 >= _POLL_MAX_PAGES:
                break
            page = await self._query_message_page((page_number + 1) * _POLL_QUERY_LIMIT)

        if not complete:
            logger.warning(
                "[bluebubbles] polling catch-up exceeded the bounded query window; checkpoint unchanged"
            )
            return

        # Query results are newest-first. Dispatch oldest-first so messages in
        # the same chat retain their original ordering.
        for record in reversed(new_records):
            try:
                await self._process_inbound_payload(
                    {"type": "new-message", "data": record}
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Treat a malformed/poison record as intentionally ignored.
                # Logging only the exception class avoids leaking message data.
                logger.warning(
                    "[bluebubbles] ignored polling record after processing error (%s)",
                    type(exc).__name__,
                )
            # The full query window was fetched successfully before dispatch
            # began, so it is safe to advance one record at a time. This keeps
            # accepted and intentionally ignored records from replaying if
            # cancellation lands partway through the oldest-first batch.
            self._persist_poll_mark(record)

    async def _poll_messages_loop(self) -> None:
        while True:
            try:
                await self._poll_messages_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # httpx exceptions can include the authenticated query URL, so
                # never interpolate the exception text here.
                logger.warning(
                    "[bluebubbles] message query failed (%s); will retry",
                    type(exc).__name__,
                )
            await asyncio.sleep(self.poll_interval_seconds)

    @property
    def _webhook_url(self) -> str:
        """Compute the external webhook URL for BlueBubbles registration."""
        host = self.webhook_host
        if host in {"0.0.0.0", "127.0.0.1", "localhost", "::"}:
            host = "localhost"
        return f"http://{host}:{self.webhook_port}{self.webhook_path}"

    @property
    def _webhook_register_url(self) -> str:
        """Webhook URL registered with BlueBubbles, including the password as
        a query param so inbound webhook POSTs carry credentials.

        BlueBubbles posts events to the exact URL registered via
        ``/api/v1/webhook``. Its webhook registration API does not support
        custom headers, so embedding the password in the URL is the only
        way to authenticate inbound webhooks without disabling auth.
        """
        base = self._webhook_url
        if self.password:
            return f"{base}?password={quote(self.password, safe='')}"
        return base

    @property
    def _webhook_register_url_for_log(self) -> str:
        """Webhook registration URL safe for logs."""
        base = self._webhook_url
        if self.password:
            return f"{base}?password=***"
        return base

    async def _find_registered_webhooks(self, url: str) -> list:
        """Return list of BB webhook entries matching *url*."""
        try:
            res = await self._api_get("/api/v1/webhook")
            data = res.get("data")
            if isinstance(data, list):
                return [wh for wh in data if wh.get("url") == url]
        except Exception:
            pass
        return []

    async def _register_webhook(self) -> bool:
        """Register this webhook URL with the BlueBubbles server.

        BlueBubbles requires webhooks to be registered via API before
        it will send events.  Checks for an existing registration first
        to avoid duplicates (e.g. after a crash without clean shutdown).
        """
        if not self.client:
            return False

        webhook_url = self._webhook_register_url

        # Crash resilience — reuse an existing registration if present
        existing = await self._find_registered_webhooks(webhook_url)
        if existing:
            logger.info(
                "[bluebubbles] webhook already registered: %s",
                self._webhook_register_url_for_log,
            )
            return True

        payload = {
            "url": webhook_url,
            "events": ["new-message", "updated-message"],
        }

        try:
            res = await self._api_post("/api/v1/webhook", payload)
            status = res.get("status", 0)
            if 200 <= status < 300:
                logger.info(
                    "[bluebubbles] webhook registered with server: %s",
                    self._webhook_register_url_for_log,
                )
                return True
            else:
                logger.warning(
                    "[bluebubbles] webhook registration returned status %s: %s",
                    status,
                    res.get("message"),
                )
                return False
        except Exception as exc:
            logger.warning(
                "[bluebubbles] failed to register webhook with server: %s",
                exc,
            )
            return False

    async def _unregister_webhook(self) -> bool:
        """Unregister this webhook URL from the BlueBubbles server.

        Removes *all* matching registrations to clean up any duplicates
        left by prior crashes.
        """
        if not self.client:
            return False

        webhook_url = self._webhook_register_url
        removed = False

        try:
            for wh in await self._find_registered_webhooks(webhook_url):
                wh_id = wh.get("id")
                if wh_id:
                    res = await self.client.delete(
                        self._api_url(f"/api/v1/webhook/{wh_id}")
                    )
                    res.raise_for_status()
                    removed = True
            if removed:
                logger.info(
                    "[bluebubbles] webhook unregistered: %s",
                    self._webhook_register_url_for_log,
                )
        except Exception as exc:
            logger.debug(
                "[bluebubbles] failed to unregister webhook (non-critical): %s",
                exc,
            )
        return removed

    # ------------------------------------------------------------------
    # Chat GUID resolution
    # ------------------------------------------------------------------

    async def _resolve_chat_guid(self, target: str) -> Optional[str]:
        """Resolve an email/phone to a BlueBubbles chat GUID.

        If *target* already contains a semicolon (raw GUID format like
        ``iMessage;-;user@example.com``), it is returned as-is.  Otherwise
        the adapter queries the BlueBubbles chat list and matches strictly
        on ``chatIdentifier`` / ``identifier``.

        Participant membership is intentionally NOT used as a fallback:
        the same contact can appear in a 1:1 DM and in any number of group
        chats, so a participant match would let an outbound DM reply leak
        into a group thread (see #24157). When no exact chat identity
        matches, return ``None`` and let the caller create a fresh DM
        explicitly via ``_create_chat_for_handle``.
        """
        target = (target or "").strip()
        if not target:
            return None
        # Already a raw GUID
        if ";" in target:
            return target
        if target in self._guid_cache:
            self._guid_cache.move_to_end(target)
            return self._guid_cache[target]
        try:
            payload = await self._api_post(
                "/api/v1/chat/query",
                {"limit": 100, "offset": 0},
            )
            for chat in payload.get("data", []) or []:
                guid = chat.get("guid") or chat.get("chatGuid")
                identifier = chat.get("chatIdentifier") or chat.get("identifier")
                if identifier == target:
                    if guid:
                        self._guid_cache[target] = guid
                        while len(self._guid_cache) > _GUID_CACHE_SIZE:
                            self._guid_cache.popitem(last=False)
                    return guid
        except Exception:
            pass
        return None

    async def _create_chat_for_handle(
        self, address: str, message: str
    ) -> SendResult:
        """Create a new chat by sending the first message to *address*."""
        payload = {
            "addresses": [address],
            "message": message,
            "tempGuid": f"temp-{datetime.utcnow().timestamp()}",
        }
        try:
            res = await self._api_post("/api/v1/chat/new", payload)
            data = res.get("data") or {}
            msg_id = data.get("guid") or data.get("messageGuid") or "ok"
            return SendResult(success=True, message_id=str(msg_id), raw_response=res)
        except Exception as exc:
            return SendResult(success=False, error=str(exc))

    # ------------------------------------------------------------------
    # Text sending
    # ------------------------------------------------------------------

    @staticmethod
    def truncate_message(content: str, max_length: int = MAX_TEXT_LENGTH) -> List[str]:
        # Use the base splitter but skip pagination indicators — iMessage
        # bubbles flow naturally without "(1/3)" suffixes.
        chunks = BasePlatformAdapter.truncate_message(content, max_length)
        return [re.sub(r"\s*\(\d+/\d+\)$", "", c) for c in chunks]

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        text = self.format_message(content)
        if not text:
            return SendResult(success=False, error="BlueBubbles send requires text")
        # Split on paragraph breaks first (double newlines) so each thought
        # becomes its own iMessage bubble, then truncate any that are still
        # too long.
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        chunks: List[str] = []
        for para in (paragraphs or [text]):
            if len(para) <= self.MAX_MESSAGE_LENGTH:
                chunks.append(para)
            else:
                chunks.extend(self.truncate_message(para, max_length=self.MAX_MESSAGE_LENGTH))
        last = SendResult(success=True)
        for chunk in chunks:
            guid = await self._resolve_chat_guid(chat_id)
            if not guid:
                # If the target looks like an address, try creating a new chat
                if self._private_api_enabled and (
                    "@" in chat_id or re.match(r"^\+\d+", chat_id)
                ):
                    return await self._create_chat_for_handle(chat_id, chunk)
                return SendResult(
                    success=False,
                    error=f"BlueBubbles chat not found for target: {chat_id}",
                )
            payload: Dict[str, Any] = {
                "chatGuid": guid,
                "tempGuid": f"temp-{datetime.utcnow().timestamp()}",
                "message": chunk,
            }
            if reply_to and self._private_api_enabled and self._helper_connected:
                payload["method"] = "private-api"
                payload["selectedMessageGuid"] = reply_to
                payload["partIndex"] = 0
            try:
                res = await self._api_post("/api/v1/message/text", payload)
                data = res.get("data") or {}
                msg_id = data.get("guid") or data.get("messageGuid") or "ok"
                last = SendResult(
                    success=True, message_id=str(msg_id), raw_response=res
                )
            except Exception as exc:
                return SendResult(success=False, error=str(exc))
        return last

    # ------------------------------------------------------------------
    # Media sending (outbound)
    # ------------------------------------------------------------------

    async def _send_attachment(
        self,
        chat_id: str,
        file_path: str,
        filename: Optional[str] = None,
        caption: Optional[str] = None,
        is_audio_message: bool = False,
    ) -> SendResult:
        """Send a file attachment via BlueBubbles multipart upload."""
        if not self.client:
            return SendResult(success=False, error="Not connected")
        if not os.path.isfile(file_path):
            return SendResult(success=False, error=f"File not found: {file_path}")

        guid = await self._resolve_chat_guid(chat_id)
        if not guid:
            return SendResult(success=False, error=f"Chat not found: {chat_id}")

        fname = filename or os.path.basename(file_path)
        try:
            with open(file_path, "rb") as f:
                files = {"attachment": (fname, f, "application/octet-stream")}
                data: Dict[str, str] = {
                    "chatGuid": guid,
                    "name": fname,
                    "tempGuid": uuid.uuid4().hex,
                }
                if is_audio_message:
                    data["isAudioMessage"] = "true"
                res = await self.client.post(
                    self._api_url("/api/v1/message/attachment"),
                    files=files,
                    data=data,
                    timeout=120,
                )
                res.raise_for_status()
                result = res.json()

            if caption:
                await self.send(chat_id, caption)

            if result.get("status") == 200:
                rdata = result.get("data") or {}
                msg_id = rdata.get("guid") if isinstance(rdata, dict) else None
                return SendResult(
                    success=True, message_id=msg_id, raw_response=result
                )
            return SendResult(
                success=False,
                error=result.get("message", "Attachment upload failed"),
            )
        except Exception as e:
            return SendResult(success=False, error=str(e))

    async def send_image(
        self,
        chat_id: str,
        image_url: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        try:
            from gateway.platforms.base import cache_image_from_url

            local_path = await cache_image_from_url(image_url)
            return await self._send_attachment(chat_id, local_path, caption=caption)
        except Exception:
            return await super().send_image(chat_id, image_url, caption, reply_to)

    async def send_image_file(
        self,
        chat_id: str,
        image_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        return await self._send_attachment(chat_id, image_path, caption=caption)

    async def send_voice(
        self,
        chat_id: str,
        audio_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        return await self._send_attachment(
            chat_id, audio_path, caption=caption, is_audio_message=True
        )

    async def send_video(
        self,
        chat_id: str,
        video_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        return await self._send_attachment(chat_id, video_path, caption=caption)

    async def send_document(
        self,
        chat_id: str,
        file_path: str,
        caption: Optional[str] = None,
        file_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        return await self._send_attachment(
            chat_id, file_path, filename=file_name, caption=caption
        )

    async def send_animation(
        self,
        chat_id: str,
        animation_url: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        return await self.send_image(
            chat_id, animation_url, caption, reply_to, metadata
        )

    # ------------------------------------------------------------------
    # Typing indicators
    # ------------------------------------------------------------------

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        if not self._private_api_enabled or not self._helper_connected or not self.client:
            return
        try:
            guid = await self._resolve_chat_guid(chat_id)
            if guid:
                encoded = quote(guid, safe="")
                await self.client.post(
                    self._api_url(f"/api/v1/chat/{encoded}/typing"), timeout=5
                )
        except Exception:
            pass

    async def stop_typing(self, chat_id: str) -> None:
        if not self._private_api_enabled or not self._helper_connected or not self.client:
            return
        try:
            guid = await self._resolve_chat_guid(chat_id)
            if guid:
                encoded = quote(guid, safe="")
                await self.client.delete(
                    self._api_url(f"/api/v1/chat/{encoded}/typing"), timeout=5
                )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Read receipts
    # ------------------------------------------------------------------

    async def mark_read(self, chat_id: str) -> bool:
        if not self._private_api_enabled or not self._helper_connected or not self.client:
            return False
        try:
            guid = await self._resolve_chat_guid(chat_id)
            if guid:
                encoded = quote(guid, safe="")
                await self.client.post(
                    self._api_url(f"/api/v1/chat/{encoded}/read"), timeout=5
                )
                return True
        except Exception:
            pass
        return False

    # ------------------------------------------------------------------
    # Tapback reactions
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Chat info
    # ------------------------------------------------------------------

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        is_group = ";+;" in (chat_id or "")
        info: Dict[str, Any] = {
            "name": chat_id,
            "type": "group" if is_group else "dm",
        }
        try:
            guid = await self._resolve_chat_guid(chat_id)
            if guid:
                encoded = quote(guid, safe="")
                res = await self._api_get(
                    f"/api/v1/chat/{encoded}?with=participants"
                )
                data = (res or {}).get("data", {})
                display_name = (
                    data.get("displayName")
                    or data.get("chatIdentifier")
                    or chat_id
                )
                participants = []
                for p in data.get("participants", []) or []:
                    addr = (p.get("address") or "").strip()
                    if addr:
                        participants.append(addr)
                info["name"] = display_name
                if participants:
                    info["participants"] = participants
        except Exception:
            pass
        return info

    def format_message(self, content: str) -> str:
        return strip_markdown(content)

    # ------------------------------------------------------------------
    # Inbound attachment downloading (from #4588)
    # ------------------------------------------------------------------

    async def _download_attachment(
        self, att_guid: str, att_meta: Dict[str, Any]
    ) -> Optional[str]:
        """Download an attachment from BlueBubbles and cache it locally.

        Returns the local file path on success, None on failure.
        """
        if not self.client:
            return None
        try:
            encoded = quote(att_guid, safe="")
            resp = await self.client.get(
                self._api_url(f"/api/v1/attachment/{encoded}/download"),
                timeout=60,
                follow_redirects=True,
            )
            resp.raise_for_status()
            data = resp.content

            mime = (att_meta.get("mimeType") or "").lower()
            transfer_name = att_meta.get("transferName", "")

            if mime.startswith("image/"):
                ext = ext_for_mime(
                    mime,
                    overrides=_BLUEBUBBLES_IMAGE_EXT_OVERRIDES,
                    # Historical map was closed: any unlisted image mime
                    # fell back to .jpg without consulting mimetypes.
                    use_defaults=False,
                    use_mimetypes=False,
                    fallback=".jpg",
                ) or ".jpg"
                return cache_image_from_bytes(data, ext)

            if mime.startswith("audio/"):
                ext = ext_for_mime(
                    mime,
                    overrides=_BLUEBUBBLES_AUDIO_EXT_OVERRIDES,
                    # Historical map was closed: any unlisted audio mime
                    # fell back to .mp3 without consulting mimetypes.
                    use_defaults=False,
                    use_mimetypes=False,
                    fallback=".mp3",
                ) or ".mp3"
                return cache_audio_from_bytes(data, ext)

            # Videos, documents, and everything else
            filename = transfer_name or f"file_{uuid.uuid4().hex[:8]}"
            return cache_document_from_bytes(data, filename)

        except Exception as exc:
            # httpx exceptions may include the authenticated download URL.
            # Polling reaches this same helper, so never interpolate the URL,
            # attachment GUID, credentials, or message-related values here.
            logger.warning(
                "[bluebubbles] failed to download attachment (%s)",
                type(exc).__name__,
            )
            return None

    # ------------------------------------------------------------------
    # Webhook handling
    # ------------------------------------------------------------------

    def _extract_payload_record(
        self, payload: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        data = payload.get("data")
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    return item
        if isinstance(payload.get("message"), dict):
            return payload.get("message")
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _value(*candidates: Any) -> Optional[str]:
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None

    async def _handle_webhook(self, request):
        from aiohttp import web

        token = (
            request.query.get("password")
            or request.query.get("guid")
            or request.headers.get("x-password")
            or request.headers.get("x-guid")
            or request.headers.get("x-bluebubbles-guid")
        )
        if token != self.password:
            return web.json_response({"error": "unauthorized"}, status=401)
        try:
            raw = await request.read()
            body = raw.decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
            except Exception:
                from urllib.parse import parse_qs

                form = parse_qs(body)
                payload_str = (
                    form.get("payload")
                    or form.get("data")
                    or form.get("message")
                    or [""]
                )[0]
                payload = json.loads(payload_str) if payload_str else {}
        except Exception as exc:
            logger.error("[bluebubbles] webhook parse error: %s", exc)
            return web.json_response({"error": "invalid payload"}, status=400)

        event_type = self._value(payload.get("type"), payload.get("event")) or ""
        # Only process message events; silently acknowledge everything else
        if event_type and event_type not in _MESSAGE_EVENTS:
            return web.Response(text="ok")

        result = await self._process_inbound_payload(payload)
        if result == "invalid":
            return web.json_response({"error": "missing message fields"}, status=400)
        return web.Response(text="ok")

    async def _process_inbound_payload(self, payload: Dict[str, Any]) -> str:
        """Normalize and dispatch one webhook or polled message payload.

        Returns ``accepted``, ``ignored``, or ``invalid``. Both inbound sources
        use this method so authorization and session dispatch remain on the
        established :class:`MessageEvent` path.
        """
        record = self._extract_payload_record(payload) or {}
        claim, claimed = self._claim_message(record)
        if not claimed:
            return "ignored"
        remember_claim = False
        try:
            result = await self._normalize_and_dispatch_record(payload, record)
            # Accepted and intentionally ignored records must not reappear on
            # the other inbound path. Invalid records remain retryable because
            # an attachment download may have failed transiently.
            remember_claim = result != "invalid"
            return result
        finally:
            self._finish_message_claim(claim, remember=remember_claim)

    async def _normalize_and_dispatch_record(
        self, payload: Dict[str, Any], record: Dict[str, Any]
    ) -> str:
        is_from_me = bool(
            record.get("isFromMe")
            or record.get("fromMe")
            or record.get("is_from_me")
        )
        if is_from_me:
            return "ignored"

        # Skip tapbacks and system records delivered as messages.
        assoc_type = record.get("associatedMessageType")
        if isinstance(assoc_type, int) and assoc_type in {
            **_TAPBACK_ADDED,
            **_TAPBACK_REMOVED,
        }:
            return "ignored"
        item_type = record.get("itemType", record.get("item_type", 0))
        group_action_type = record.get(
            "groupActionType", record.get("group_action_type", 0)
        )
        if (
            bool(
                record.get("isSystemMessage")
                or record.get("is_system_message")
                or record.get("isServiceMessage")
                or record.get("is_service_message")
            )
            or item_type not in (None, 0, "0")
            or group_action_type not in (None, 0, "0")
        ):
            return "ignored"

        text = (
            self._value(
                record.get("text"), record.get("message"), record.get("body")
            )
            or ""
        )

        # --- Inbound attachment handling ---
        attachments = record.get("attachments") or []
        if not isinstance(attachments, list):
            attachments = []
        media_urls: List[str] = []
        media_types: List[str] = []
        msg_type = MessageType.TEXT

        for att in attachments:
            if not isinstance(att, dict):
                continue
            att_guid = att.get("guid", "")
            if not att_guid:
                continue
            cached = await self._download_attachment(att_guid, att)
            if cached:
                mime = (att.get("mimeType") or "").lower()
                media_urls.append(cached)
                media_types.append(mime)
                if mime.startswith("image/"):
                    msg_type = MessageType.PHOTO
                elif mime.startswith("audio/") or (att.get("uti") or "").endswith(
                    "caf"
                ):
                    msg_type = MessageType.VOICE
                elif mime.startswith("video/"):
                    msg_type = MessageType.VIDEO
                else:
                    msg_type = MessageType.DOCUMENT

        # With multiple attachments, prefer PHOTO if any images present
        if len(media_urls) > 1:
            mime_prefixes = {(m or "").split("/")[0] for m in media_types}
            if "image" in mime_prefixes:
                msg_type = MessageType.PHOTO

        if not text and media_urls:
            text = "(attachment)"
        # --- End attachment handling ---

        chat_guid = self._value(
            record.get("chatGuid"),
            payload.get("chatGuid"),
            record.get("chat_guid"),
            payload.get("chat_guid"),
            payload.get("guid"),
        )
        # Fallback: BlueBubbles v1.9+ webhook payloads omit top-level chatGuid;
        # the chat GUID is nested under data.chats[0].guid instead.
        if not chat_guid:
            _chats = record.get("chats") or []
            if _chats and isinstance(_chats[0], dict):
                chat_guid = _chats[0].get("guid") or _chats[0].get("chatGuid")
        chat_identifier = self._value(
            record.get("chatIdentifier"),
            record.get("identifier"),
            payload.get("chatIdentifier"),
            payload.get("identifier"),
        )
        sender = (
            self._value(
                record.get("handle", {}).get("address")
                if isinstance(record.get("handle"), dict)
                else None,
                record.get("sender"),
                record.get("from"),
                record.get("address"),
            )
            or chat_identifier
            or chat_guid
        )
        if not (chat_guid or chat_identifier) and sender:
            chat_identifier = sender
        if not sender or not (chat_guid or chat_identifier) or not text:
            return "invalid"

        session_chat_id = chat_guid or chat_identifier
        is_group = bool(record.get("isGroup")) or (";+;" in (chat_guid or ""))
        if is_group and self.require_mention:
            if not self._message_matches_mention_patterns(text):
                logger.debug(
                    "[bluebubbles] ignoring group message (require_mention=true, no mention pattern matched)"
                )
                return "ignored"
            text = self._clean_mention_text(text)
        source = self.build_source(
            chat_id=session_chat_id,
            chat_name=chat_identifier or sender,
            chat_type="group" if is_group else "dm",
            user_id=sender,
            user_name=sender,
            chat_id_alt=chat_identifier,
        )
        event = MessageEvent(
            text=text,
            message_type=msg_type,
            source=source,
            raw_message=payload,
            message_id=self._value(
                record.get("guid"),
                record.get("messageGuid"),
                record.get("id"),
            ),
            reply_to_message_id=self._value(
                record.get("threadOriginatorGuid"),
                record.get("associatedMessageGuid"),
            ),
            media_urls=media_urls,
            media_types=media_types,
        )
        task = asyncio.create_task(self.handle_message(event))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        # Fire-and-forget read receipt
        if self.send_read_receipts and session_chat_id:
            asyncio.create_task(self.mark_read(session_chat_id))

        return "accepted"
