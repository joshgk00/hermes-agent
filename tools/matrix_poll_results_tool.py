"""get_matrix_poll_results — read vote counts for a Matrix poll.

Reads from the cache at ~/.hermes/platforms/matrix/polls_cache.db, which
the running gateway's MatrixAdapter populates as it sees poll events
arrive in rooms it's in. Because the gateway is always online (and is a
member of every room the bot is in), it has the Megolm keys to decrypt
vote events in encrypted rooms — the cache ends up with plaintext
votes. This tool is a pure read of that cache.

Caveats:
  * Only polls the gateway witnessed are present. Polls from before the
    gateway was running, or rooms the gateway isn't in, won't appear.
  * "Total votes" counts distinct voters, not distinct selections. In
    multi-select polls a voter contributes one row even if they picked
    several answers.
"""

import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


_POLL_CACHE_DB = Path.home() / ".hermes" / "platforms" / "matrix" / "polls_cache.db"


READ_POLL_RESULTS_SCHEMA = {
    "name": "read_poll_results",
    "description": (
        "Get vote counts and results for a Matrix poll. USE THIS whenever "
        "the user asks about poll results, votes, tallies, who voted, "
        "what the poll totals are, or 'what are the results of the poll'. "
        "Takes the poll's event_id (returned earlier by send_matrix_poll) "
        "and returns counts per answer option."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "poll_event_id": {
                "type": "string",
                "description": "The event_id returned by send_matrix_poll.",
            },
            "include_voters": {
                "type": "boolean",
                "description": "If true, list per-option voter Matrix IDs. Default false.",
            },
        },
        "required": ["poll_event_id"],
    },
}


def _error(msg: str) -> str:
    return json.dumps({"error": msg})


def _check_read_poll_results() -> bool:
    """Surface the tool whenever the gateway is running + Matrix deps are
    importable. The cache file may not exist yet on a fresh install —
    that's fine; the handler returns a friendly error if so."""
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
    try:
        from gateway.platforms.matrix import check_matrix_requirements  # noqa: F401
    except Exception:
        return False
    return True


def read_poll_results_tool(args, **kw) -> str:
    poll_event_id = (args.get("poll_event_id") or "").strip()
    if not poll_event_id:
        return _error("poll_event_id is required")
    include_voters = bool(args.get("include_voters", False))

    if not _POLL_CACHE_DB.exists():
        return _error(
            "Poll cache not initialized yet. Restart the gateway, then send "
            "a poll via send_matrix_poll; once it's been sent the cache will "
            "catch any votes that follow."
        )

    try:
        with sqlite3.connect(str(_POLL_CACHE_DB)) as db:
            db.row_factory = sqlite3.Row
            poll_row = db.execute(
                "SELECT * FROM polls WHERE poll_event_id = ?",
                (poll_event_id,),
            ).fetchone()
            if poll_row is None:
                return _error(
                    f"No poll with event_id {poll_event_id} in the cache. "
                    "Either the gateway wasn't online when it was sent, the "
                    "bot isn't in the room, or the ID is wrong."
                )

            response_rows = db.execute(
                "SELECT voter_user_id, selections_json, ts "
                "FROM poll_responses WHERE poll_event_id = ?",
                (poll_event_id,),
            ).fetchall()
    except sqlite3.Error as exc:
        logger.exception("Poll cache read failed")
        return _error(f"Poll cache read failed: {exc}")

    try:
        options = json.loads(poll_row["options_json"] or "[]")
    except json.JSONDecodeError:
        options = []

    counts = {opt.get("id", ""): 0 for opt in options if isinstance(opt, dict)}
    voters_per_option: dict = {opt.get("id", ""): [] for opt in options if isinstance(opt, dict)} if include_voters else {}

    counted_voters = set()
    retracted_voters = set()
    for row in response_rows:
        try:
            selections = json.loads(row["selections_json"] or "[]") or []
        except json.JSONDecodeError:
            continue
        voter = row["voter_user_id"]
        if not selections:
            retracted_voters.add(voter)
            continue
        counted_voters.add(voter)
        for sel in selections:
            if sel in counts:
                counts[sel] += 1
                if include_voters and voter not in voters_per_option[sel]:
                    voters_per_option[sel].append(voter)

    result = {
        "poll_event_id": poll_event_id,
        "room_id": poll_row["room_id"],
        "sender": poll_row["sender"],
        "question": poll_row["question"],
        "options": options,
        "kind": poll_row["kind"],
        "max_selections": poll_row["max_selections"],
        "counts": counts,
        "voter_count": len(counted_voters),
        "retracted_count": len(retracted_voters),
        "is_ended": bool(poll_row["ended_at"]),
    }
    if include_voters:
        result["voters_per_option"] = voters_per_option

    return json.dumps(result)


from tools.registry import registry  # noqa: E402

registry.register(
    name="read_poll_results",
    toolset="messaging",
    schema=READ_POLL_RESULTS_SCHEMA,
    handler=read_poll_results_tool,
    check_fn=_check_read_poll_results,
    emoji="📈",
)
