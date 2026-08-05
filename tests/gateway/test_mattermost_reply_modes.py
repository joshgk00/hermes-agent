import asyncio
from unittest.mock import AsyncMock

from gateway.config import PlatformConfig
from plugins.platforms.mattermost.adapter import MattermostAdapter


def _adapter(mode: str):
    adapter = MattermostAdapter(
        PlatformConfig(enabled=True, token="fake", extra={"url": "https://mm.example.com"})
    )
    api_post = AsyncMock(return_value={"id": "post-id"})
    resolve_root_id = AsyncMock(return_value="resolved-root")
    adapter._reply_mode = mode
    adapter._api_post = api_post
    adapter._resolve_root_id = resolve_root_id
    return adapter, api_post, resolve_root_id


def test_follow_thread_reply_mode_does_not_create_thread_for_top_level_message():
    async def run():
        adapter, api_post, resolve_root_id = _adapter("follow_thread")
        result = await adapter.send("channel-id", "hello", reply_to="top-level-post", metadata=None)
        assert result.success
        payload = api_post.call_args.args[1]
        assert "root_id" not in payload
        resolve_root_id.assert_not_awaited()

    asyncio.run(run())


def test_follow_thread_reply_mode_keeps_existing_thread():
    async def run():
        adapter, api_post, resolve_root_id = _adapter("follow_thread")
        result = await adapter.send(
            "channel-id",
            "hello",
            reply_to="reply-post",
            metadata={"thread_id": "thread-root"},
        )
        assert result.success
        payload = api_post.call_args.args[1]
        assert payload["root_id"] == "thread-root"
        resolve_root_id.assert_not_awaited()

    asyncio.run(run())


def test_smart_reply_mode_aliases_follow_thread():
    async def run():
        adapter, api_post, resolve_root_id = _adapter("smart")
        result = await adapter.send(
            "channel-id",
            "hello",
            reply_to="reply-post",
            metadata={"thread_id": "thread-root"},
        )
        assert result.success
        payload = api_post.call_args.args[1]
        assert payload["root_id"] == "thread-root"
        resolve_root_id.assert_not_awaited()

    asyncio.run(run())


def test_thread_reply_mode_keeps_legacy_anchor_behavior():
    async def run():
        adapter, api_post, resolve_root_id = _adapter("thread")
        result = await adapter.send("channel-id", "hello", reply_to="any-post", metadata=None)
        assert result.success
        payload = api_post.call_args.args[1]
        assert payload["root_id"] == "resolved-root"
        resolve_root_id.assert_awaited_once_with("any-post")

    asyncio.run(run())
