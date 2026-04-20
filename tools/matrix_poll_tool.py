"""send_matrix_poll — send an MSC3381 poll to a Matrix room.

Mirrors the per-call adapter pattern that send_message uses for Matrix
media: loads the Matrix PlatformConfig, instantiates a short-lived
MatrixAdapter, connects, sends the poll, disconnects. mautrix handles
E2EE automatically for encrypted rooms.

Why a dedicated tool instead of extending send_message:
    Polls are not free-text messages; they have structured answers and
    options (kind, max_selections, thread). A distinct schema keeps the
    model from conflating "send a message" with "start a poll", and
    keeps send_message's schema narrow.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)


SEND_MATRIX_POLL_SCHEMA = {
    "name": "send_matrix_poll",
    "description": (
        "Start a poll in a Matrix room (MSC3381). "
        "Encrypts automatically when the room is E2EE. "
        "Use send_message(action='list') to discover room IDs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "room_id": {
                "type": "string",
                "description": "Matrix room ID, e.g. '!abc123:matrix.org'. "
                "To resolve a friendly channel name, call send_message(action='list') first.",
            },
            "question": {
                "type": "string",
                "description": "The poll question.",
            },
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "description": "Answer choices (at least two).",
            },
            "kind": {
                "type": "string",
                "enum": ["disclosed", "undisclosed"],
                "description": "'disclosed' (default): votes visible while open. "
                "'undisclosed': results hidden until the poll closes.",
            },
            "max_selections": {
                "type": "integer",
                "minimum": 1,
                "description": "Max answers a voter may pick. Default 1.",
            },
            "thread_id": {
                "type": "string",
                "description": "Optional Matrix event ID to anchor the poll as a thread reply.",
            },
        },
        "required": ["room_id", "question", "options"],
    },
}


def _error(msg: str) -> str:
    return json.dumps({"error": msg})


def _check_send_matrix_poll() -> bool:
    """Available when Matrix is configured and the gateway is running (or
    we're already inside a gateway session)."""
    try:
        from gateway.session_context import get_session_env

        platform = get_session_env("HERMES_SESSION_PLATFORM", "")
        if platform == "matrix":
            return True
    except Exception:
        pass
    try:
        from gateway.status import is_gateway_running

        if not is_gateway_running():
            return False
    except Exception:
        return False

    # Only surface the tool if Matrix dependencies are importable.
    try:
        from gateway.platforms.matrix import check_matrix_requirements  # noqa: F401
    except Exception:
        return False
    return True


async def _send_poll_via_adapter(args: dict) -> dict:
    try:
        from gateway.config import Platform, load_gateway_config
        from gateway.platforms.matrix import MatrixAdapter
    except ImportError as exc:
        return {
            "error": (
                "Matrix dependencies not installed. "
                "Run: pip install 'mautrix[encryption]' "
                f"(detail: {exc})"
            )
        }

    try:
        config = load_gateway_config()
    except Exception as exc:
        return {"error": f"Failed to load gateway config: {exc}"}

    pconfig = config.platforms.get(Platform.MATRIX)
    if pconfig is None or not pconfig.enabled:
        return {"error": "Matrix platform not configured or disabled"}

    # Polls go through a dedicated "Hermes Polls" device so short-lived
    # send processes reuse a stable token/device instead of password-
    # logging-in and minting a ghost device on every invocation. See
    # MATRIX_POLL_ACCESS_TOKEN / MATRIX_POLL_DEVICE_ID in ~/.hermes/.env.
    poll_token = os.getenv("MATRIX_POLL_ACCESS_TOKEN")
    poll_device = os.getenv("MATRIX_POLL_DEVICE_ID")
    if not poll_token:
        return {
            "error": (
                "send_matrix_poll requires MATRIX_POLL_ACCESS_TOKEN in "
                "~/.hermes/.env (a token bound to a dedicated 'Hermes Polls' "
                "device). Without it every invocation would mint a new ghost "
                "device on the account."
            )
        }

    # Override the main (gateway) credentials with the poll-specific ones
    # so this adapter connects as the 'Hermes Polls' device, not the bot's
    # primary device. This is a local mutation of the loaded pconfig; the
    # running gateway has its own in-memory copy and is unaffected.
    pconfig.token = poll_token
    if poll_device:
        pconfig.extra["device_id"] = poll_device

    # Isolated crypto store for the polls device. The mautrix crypto
    # schema keys crypto_account by account_id alone, so two adapters for
    # the same user but different devices will clobber each other's olm
    # state if they share a store. Point the polls adapter at its own
    # directory.
    from pathlib import Path as _Path

    _hermes_home = _Path.home() / ".hermes"
    pconfig.extra["store_dir"] = str(_hermes_home / "platforms" / "matrix-polls" / "store")

    adapter = MatrixAdapter(pconfig)
    try:
        connected = await adapter.connect()
        if not connected:
            return {"error": "Matrix adapter failed to connect"}

        result = await adapter.send_poll(
            args["room_id"],
            args["question"],
            list(args["options"]),
            kind=args.get("kind", "disclosed"),
            max_selections=int(args.get("max_selections", 1)),
            thread_id=args.get("thread_id"),
        )
    except Exception as exc:
        logger.exception("send_matrix_poll failed")
        return {"error": f"send_matrix_poll failed: {exc}"}
    finally:
        try:
            await adapter.disconnect()
        except Exception:
            pass

    if not result.success:
        return {"error": f"Matrix poll send failed: {result.error}"}

    return {
        "success": True,
        "platform": "matrix",
        "room_id": args["room_id"],
        "event_id": result.message_id,
    }


def send_matrix_poll_tool(args, **kw) -> str:
    """Handler entry point (sync wrapper — registry bridges async internally
    only when is_async is set; we return JSON from a sync orchestrator)."""
    room_id = (args.get("room_id") or "").strip()
    question = (args.get("question") or "").strip()
    options = args.get("options") or []

    if not room_id:
        return _error("room_id is required (e.g. '!abc:matrix.org')")
    if not question:
        return _error("question is required")
    if not isinstance(options, list) or len(options) < 2:
        return _error("options must be a list of at least two strings")
    if not all(isinstance(o, str) and o.strip() for o in options):
        return _error("every option must be a non-empty string")

    max_selections = int(args.get("max_selections", 1) or 1)
    if max_selections < 1 or max_selections > len(options):
        return _error(f"max_selections must be between 1 and {len(options)}")

    kind = (args.get("kind") or "disclosed").strip()
    if kind not in ("disclosed", "undisclosed"):
        return _error("kind must be 'disclosed' or 'undisclosed'")

    from model_tools import _run_async

    result = _run_async(
        _send_poll_via_adapter(
            {
                "room_id": room_id,
                "question": question,
                "options": options,
                "kind": kind,
                "max_selections": max_selections,
                "thread_id": (args.get("thread_id") or None),
            }
        )
    )
    return json.dumps(result)


from tools.registry import registry  # noqa: E402

registry.register(
    name="send_matrix_poll",
    toolset="messaging",
    schema=SEND_MATRIX_POLL_SCHEMA,
    handler=send_matrix_poll_tool,
    check_fn=_check_send_matrix_poll,
    emoji="📊",
)
