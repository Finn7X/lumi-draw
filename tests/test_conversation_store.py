"""
Unit tests for InMemoryConversationStore.

These tests do not require a running LLM or network access.

Usage:
    pytest tests/test_conversation_store.py -v
"""

import uuid
from datetime import datetime, timezone, timedelta

import pytest

from app.agent.conversation_store import (
    InMemoryConversationStore,
    DisplayMessage,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_msg(role: str, content: str, image_url: str | None = None) -> DisplayMessage:
    return DisplayMessage(
        message_id=str(uuid.uuid4()),
        role=role,
        content=content,
        image_url=image_url,
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# create / get
# ---------------------------------------------------------------------------

def test_create_returns_valid_conversation_id():
    store = InMemoryConversationStore()
    conv = store.create(user_id="alice")
    assert conv.conversation_id
    # Should be a valid UUID4
    uuid.UUID(conv.conversation_id, version=4)
    assert conv.user_id == "alice"
    assert conv.turn_count == 0
    assert conv.last_image_url is None
    assert conv.messages == []


def test_get_existing_conversation():
    store = InMemoryConversationStore()
    conv = store.create()
    fetched = store.get(conv.conversation_id)
    assert fetched is not None
    assert fetched.conversation_id == conv.conversation_id


def test_get_nonexistent_returns_none():
    store = InMemoryConversationStore()
    assert store.get("nonexistent-id") is None


def test_get_updates_accessed_at():
    store = InMemoryConversationStore()
    conv = store.create()
    before = conv.updated_at
    fetched = store.get(conv.conversation_id)
    assert fetched.updated_at >= before


# ---------------------------------------------------------------------------
# append_message
# ---------------------------------------------------------------------------

def test_append_user_message_does_not_increment_turn_count():
    store = InMemoryConversationStore()
    conv = store.create()
    store.append_message(conv.conversation_id, make_msg("user", "hello"))
    assert store.get(conv.conversation_id).turn_count == 0


def test_append_assistant_message_increments_turn_count():
    store = InMemoryConversationStore()
    conv = store.create()
    store.append_message(conv.conversation_id, make_msg("user", "hello"))
    store.append_message(
        conv.conversation_id,
        make_msg("assistant", "done", image_url="http://example.com/a.png"),
    )
    c = store.get(conv.conversation_id)
    assert c.turn_count == 1
    assert c.last_image_url == "http://example.com/a.png"


def test_multiple_turns_track_last_image_url():
    store = InMemoryConversationStore()
    conv = store.create()
    for i in range(3):
        store.append_message(conv.conversation_id, make_msg("user", f"q{i}"))
        store.append_message(
            conv.conversation_id,
            make_msg("assistant", f"a{i}", image_url=f"http://example.com/{i}.png"),
        )
    c = store.get(conv.conversation_id)
    assert c.turn_count == 3
    assert c.last_image_url == "http://example.com/2.png"


def test_append_to_nonexistent_conversation_raises():
    store = InMemoryConversationStore()
    with pytest.raises(KeyError):
        store.append_message("bad-id", make_msg("user", "hi"))


def test_message_order_preserved():
    store = InMemoryConversationStore()
    conv = store.create()
    contents = ["first", "second", "third"]
    for c in contents:
        store.append_message(conv.conversation_id, make_msg("user", c))
    msgs = store.get(conv.conversation_id).messages
    assert [m.content for m in msgs] == contents


# ---------------------------------------------------------------------------
# Conversation isolation
# ---------------------------------------------------------------------------

def test_two_conversations_are_independent():
    store = InMemoryConversationStore()
    c1 = store.create(user_id="alice")
    c2 = store.create(user_id="bob")

    store.append_message(c1.conversation_id, make_msg("user", "for alice"))
    store.append_message(
        c1.conversation_id,
        make_msg("assistant", "alice reply", image_url="http://example.com/a.png"),
    )

    # c2 should be untouched
    fetched_c2 = store.get(c2.conversation_id)
    assert fetched_c2.turn_count == 0
    assert fetched_c2.messages == []
    assert fetched_c2.last_image_url is None


# ---------------------------------------------------------------------------
# TTL cleanup
# ---------------------------------------------------------------------------

def test_cleanup_removes_expired_conversations():
    store = InMemoryConversationStore(ttl_seconds=1)
    conv = store.create()

    # Manually backdate updated_at to simulate expiry
    store._store[conv.conversation_id].updated_at = (
        datetime.now(timezone.utc) - timedelta(seconds=2)
    )

    removed = store.cleanup_expired()
    assert removed == 1
    assert store.get(conv.conversation_id) is None


def test_cleanup_keeps_active_conversations():
    store = InMemoryConversationStore(ttl_seconds=3600)
    conv = store.create()
    removed = store.cleanup_expired()
    assert removed == 0
    assert store.get(conv.conversation_id) is not None


def test_cleanup_mixed():
    store = InMemoryConversationStore(ttl_seconds=10)
    active = store.create()
    expired = store.create()

    store._store[expired.conversation_id].updated_at = (
        datetime.now(timezone.utc) - timedelta(seconds=20)
    )

    removed = store.cleanup_expired()
    assert removed == 1
    assert store.get(active.conversation_id) is not None
    assert store.get(expired.conversation_id) is None
