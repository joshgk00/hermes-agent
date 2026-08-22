from pathlib import Path

from gateway.decision_cards import DecisionCardStore, extract_decision_id


def test_create_and_lookup_decision_card(tmp_path: Path):
    store = DecisionCardStore(path=tmp_path / "cards.json")

    card = store.create(
        platform="matrix",
        room_id="!room:matrix.org",
        message_id="$event",
        body="Decision: D-1\nApprove the thing",
        decision_id="D-1",
    )

    assert card.decision_id == "D-1"
    loaded = store.get_by_message_id("$event")
    assert loaded is not None
    assert loaded.body == "Decision: D-1\nApprove the thing"
    assert loaded.actions["✅"] == "approve"


def test_resolve_is_idempotent(tmp_path: Path):
    store = DecisionCardStore(path=tmp_path / "cards.json")
    store.create(
        platform="matrix",
        room_id="!room:matrix.org",
        message_id="$event",
        body="Decision: D-1",
        decision_id="D-1",
    )

    first = store.resolve("$event", action="approve", user_id="@josh:matrix.org")
    second = store.resolve("$event", action="deny", user_id="@josh:matrix.org")

    assert first is not None
    assert second is not None
    assert second.resolved is True
    assert second.resolved_action == "approve"
    assert second.resolved_by == "@josh:matrix.org"


def test_expired_decision_card_does_not_resolve(tmp_path: Path):
    store = DecisionCardStore(path=tmp_path / "cards.json")
    store.create(
        platform="matrix",
        room_id="!room:matrix.org",
        message_id="$event",
        body="Decision: D-1",
        decision_id="D-1",
        expires_at="2000-01-01T00:00:00+00:00",
    )

    resolved = store.resolve("$event", action="approve", user_id="@josh:matrix.org")

    assert resolved is None
    loaded = store.get_by_message_id("$event")
    assert loaded is not None
    assert loaded.resolved is False


def test_lookup_by_decision_id_across_rooms(tmp_path: Path):
    store = DecisionCardStore(path=tmp_path / "cards.json")
    store.create(platform="matrix", room_id="!a:matrix.org", message_id="$a", body="Decision: D-1", decision_id="D-1")
    store.create(platform="matrix", room_id="!b:matrix.org", message_id="$b", body="Decision: D-2", decision_id="D-2")

    assert store.get_by_decision_id("D-1").room_id == "!a:matrix.org"
    assert store.get_by_decision_id("D-2").room_id == "!b:matrix.org"


def test_extract_decision_id():
    assert extract_decision_id("Title\nDecision: D-20260506-001\nBody") == "D-20260506-001"
    assert extract_decision_id("Title\nDecision ID: `D-matrix-reaction-test-20260507-0001`\nBody") == "D-matrix-reaction-test-20260507-0001"
    assert extract_decision_id("No decision here") is None
