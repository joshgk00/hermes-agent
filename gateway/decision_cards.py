from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import os
import re
import tempfile
import uuid

from hermes_constants import get_hermes_dir

DEFAULT_ACTIONS = {
    "✅": "approve",
    "❌": "deny",
    "🗑️": "close",
    "🗑": "close",
}

_DECISION_ID_RE = re.compile(r"(?im)^Decision(?:\s+ID)?:\s*`?([A-Za-z0-9_.:-]+)`?\s*$")


def extract_decision_id(body: str) -> str | None:
    """Extract a decision ID from a decision-card body."""
    match = _DECISION_ID_RE.search(body or "")
    return match.group(1) if match else None


def default_expiry_iso(days: int | None) -> str | None:
    """Return an ISO expiry timestamp days from now, or None for no expiry."""
    if days is None or days <= 0:
        return None
    from datetime import timedelta

    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


@dataclass
class DecisionCard:
    decision_id: str
    platform: str
    room_id: str
    message_id: str
    body: str
    actions: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_ACTIONS))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str | None = None
    session_key: str | None = None
    thread_id: str | None = None
    created_by: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: str | None = None
    resolved_by: str | None = None
    resolved_action: str | None = None


class DecisionCardStore:
    def __init__(self, path: Path | None = None):
        base = get_hermes_dir("decision-cards", "decision-cards")
        self.path = path or (base / "cards.json")
        self.audit_path = self.path.parent / "audit.jsonl" if path else base / "audit.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        *,
        platform: str,
        room_id: str,
        message_id: str,
        body: str,
        actions: dict[str, str] | None = None,
        decision_id: str | None = None,
        expires_at: str | None = None,
        session_key: str | None = None,
        thread_id: str | None = None,
        created_by: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionCard:
        card = DecisionCard(
            decision_id=decision_id or f"D-{uuid.uuid4().hex[:12]}",
            platform=platform,
            room_id=room_id,
            message_id=message_id,
            body=body,
            actions=actions or dict(DEFAULT_ACTIONS),
            expires_at=expires_at,
            session_key=session_key,
            thread_id=thread_id,
            created_by=created_by,
            metadata=metadata or {},
        )
        cards = self._load()
        cards[message_id] = self._to_dict(card)
        self._save(cards)
        return card

    def get_by_message_id(self, message_id: str) -> DecisionCard | None:
        raw = self._load().get(message_id)
        return self._from_dict(raw) if raw else None

    def get_by_decision_id(self, decision_id: str) -> DecisionCard | None:
        for raw in self._load().values():
            if raw.get("decision_id") == decision_id:
                return self._from_dict(raw)
        return None

    def resolve(self, message_id: str, *, action: str, user_id: str) -> DecisionCard | None:
        cards = self._load()
        raw = cards.get(message_id)
        if not raw:
            return None
        card = self._from_dict(raw)
        if self.is_expired(card):
            self._audit({
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": "decision_expired",
                "message_id": message_id,
                "decision_id": card.decision_id,
                "action": action,
                "user_id": user_id,
            })
            return None
        if raw.get("resolved"):
            return card
        now = datetime.now(timezone.utc).isoformat()
        raw.update({
            "resolved": True,
            "resolved_at": now,
            "resolved_by": user_id,
            "resolved_action": action,
        })
        cards[message_id] = raw
        self._save(cards)
        self._audit({
            "ts": now,
            "event": "decision_resolved",
            "message_id": message_id,
            "decision_id": raw.get("decision_id"),
            "action": action,
            "user_id": user_id,
        })
        return self._from_dict(raw)

    def is_expired(self, card: DecisionCard) -> bool:
        if not card.expires_at:
            return False
        try:
            expires = datetime.fromisoformat(card.expires_at)
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
        except ValueError:
            return False
        return expires <= datetime.now(timezone.utc)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text())
        except json.JSONDecodeError:
            return {}

    def _save(self, data: dict[str, Any]) -> None:
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix="cards.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def _audit(self, row: dict[str, Any]) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    def _to_dict(self, card: DecisionCard) -> dict[str, Any]:
        return card.__dict__.copy()

    def _from_dict(self, raw: dict[str, Any]) -> DecisionCard:
        return DecisionCard(**raw)
