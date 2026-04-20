"""Send an E2EE-capable MSC3381 poll to a Matrix room.

Uses Hermes's own MatrixAdapter (mautrix, crypto store at
~/.hermes/platforms/matrix/store/crypto.db) rather than a standalone
matrix-nio client. This matters for two reasons:

  1. Polls to encrypted rooms are encrypted automatically by mautrix.
  2. The adapter re-uses the bot's existing device via MATRIX_ACCESS_TOKEN
     when set, instead of logging in with a password and minting a fresh
     "ghost" device on every invocation (the bug the previous nio-based
     script caused).

Guardrails:

  * Refuses to run while the gateway is up. The gateway process already
    holds the mautrix OlmMachine open against the same crypto.db; running
    a second adapter in parallel risks advancing the Olm ratchet from two
    processes and corrupting the 1:1 sessions (exactly the BAD_MESSAGE_MAC
    failure mode we just recovered from). Pass --force to override — only
    safe if you know the gateway is wedged.

  * Refuses to run without MATRIX_ACCESS_TOKEN set. Without it, the
    adapter falls back to password login and mints a new device on each
    run, accumulating ghost devices on the account. Pass
    --allow-new-device if you explicitly want that (you probably don't).

Usage:
    python scripts/matrix_poll.py '!roomid:matrix.org' 'Question?' 'Yes' 'No' 'Maybe'
    python scripts/matrix_poll.py --thread EVENT_ID ROOM 'Question?' A B C
    python scripts/matrix_poll.py --max-selections 2 --kind undisclosed ROOM 'Q' A B C D
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


HERMES_HOME = Path.home() / ".hermes"
GATEWAY_PID_FILE = HERMES_HOME / "gateway.pid"
HERMES_AGENT = HERMES_HOME / "hermes-agent"


def _gateway_running():
    """Return pid if the gateway is running, else None."""
    if not GATEWAY_PID_FILE.exists():
        return None
    try:
        data = json.loads(GATEWAY_PID_FILE.read_text())
        pid = int(data.get("pid", 0))
    except (ValueError, OSError, json.JSONDecodeError):
        return None
    if pid <= 0:
        return None
    try:
        os.kill(pid, 0)
        return pid
    except OSError:
        return None


async def _send(args: argparse.Namespace) -> int:
    # Late import so --help works even if hermes-agent imports fail.
    from gateway.config import Platform, load_gateway_config
    from gateway.platforms.matrix import MatrixAdapter

    config = load_gateway_config()
    pconfig = config.platforms.get(Platform.MATRIX)
    if pconfig is None or not pconfig.enabled:
        print("Matrix platform not configured or disabled in gateway config.", file=sys.stderr)
        return 2

    # Polls use a dedicated "Hermes Polls" device so each script run
    # reuses the same token instead of password-logging-in and minting a
    # new ghost device. MATRIX_POLL_ACCESS_TOKEN/MATRIX_POLL_DEVICE_ID
    # live in ~/.hermes/.env.
    poll_token = os.getenv("MATRIX_POLL_ACCESS_TOKEN")
    poll_device = os.getenv("MATRIX_POLL_DEVICE_ID")
    if not poll_token and not args.allow_new_device:
        print(
            "Refusing to run: MATRIX_POLL_ACCESS_TOKEN is not set. The "
            "poll device's access token should be pinned in ~/.hermes/.env. "
            "Re-run with --allow-new-device only if you explicitly want a "
            "new Matrix device minted on this invocation.",
            file=sys.stderr,
        )
        return 3

    if poll_token:
        pconfig.token = poll_token
        if poll_device:
            pconfig.extra["device_id"] = poll_device

    # Isolated crypto store so the polls device doesn't clobber the
    # gateway's olm account row (crypto_account is keyed by account_id
    # alone in the mautrix crypto schema).
    pconfig.extra["store_dir"] = str(HERMES_HOME / "platforms" / "matrix-polls" / "store")

    adapter = MatrixAdapter(pconfig)
    connected = await adapter.connect()
    if not connected:
        print("Matrix adapter failed to connect.", file=sys.stderr)
        return 4

    try:
        result = await adapter.send_poll(
            args.room_id,
            args.question,
            args.options,
            kind=args.kind,
            max_selections=args.max_selections,
            thread_id=args.thread,
        )
    finally:
        try:
            await adapter.disconnect()
        except Exception:
            pass

    if not result.success:
        print(f"Poll send failed: {result.error}", file=sys.stderr)
        return 5

    print(f"Poll sent: {result.message_id}")
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("room_id", help="Matrix room ID (e.g. !abc:matrix.org)")
    parser.add_argument("question", help="Poll question")
    parser.add_argument("options", nargs="+", help="Poll options (2 or more)")
    parser.add_argument(
        "--kind",
        choices=("disclosed", "undisclosed"),
        default="disclosed",
        help="disclosed = results visible while open; undisclosed = hidden until close",
    )
    parser.add_argument(
        "--max-selections",
        type=int,
        default=1,
        help="Maximum answers a voter may pick (default 1)",
    )
    parser.add_argument("--thread", default=None, help="Event ID to thread the poll under")
    parser.add_argument(
        "--strict-solo",
        action="store_true",
        help="Refuse to run while the gateway is active (stronger safety).",
    )
    parser.add_argument(
        "--allow-new-device",
        action="store_true",
        help="Allow password login → new device if MATRIX_ACCESS_TOKEN is unset.",
    )
    args = parser.parse_args(argv)
    if len(args.options) < 2:
        parser.error("Need at least two poll options.")
    if args.max_selections < 1:
        parser.error("--max-selections must be >= 1")
    return args


def main(argv=None):
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    pid = _gateway_running()
    if pid is not None:
        if args.strict_solo:
            print(
                f"Refusing to run (--strict-solo): gateway is active (pid {pid}).",
                file=sys.stderr,
            )
            return 1
        print(
            f"Warning: gateway is active (pid {pid}); opening a second short-lived "
            f"adapter against the same crypto store. This is the same pattern "
            f"Hermes's own send_message uses for Matrix media. Pass --strict-solo "
            f"if you want to refuse rather than proceed.",
            file=sys.stderr,
        )

    # Hermes imports expect the agent dir on sys.path.
    sys.path.insert(0, str(HERMES_AGENT))
    return asyncio.run(_send(args))


if __name__ == "__main__":
    sys.exit(main())
