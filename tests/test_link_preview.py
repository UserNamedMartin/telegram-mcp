"""send_message and edit_message can suppress the link preview card."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telethon.tl import functions, types

from telegram_mcp.tools import messages

DATE = datetime(2026, 10, 5, tzinfo=timezone.utc)
CHAT_ID = 1234


@pytest.fixture
def client(monkeypatch):
    cl = AsyncMock()
    cl.get_me.return_value = SimpleNamespace(premium=True)
    cl.send_message.return_value = SimpleNamespace(id=77)
    cl.return_value = SimpleNamespace()
    monkeypatch.setattr(messages, "get_client", lambda account=None: cl)
    monkeypatch.setattr(
        messages,
        "resolve_entity",
        AsyncMock(return_value=types.User(id=CHAT_ID, first_name="Test")),
    )
    return cl


@pytest.mark.asyncio
async def test_send_message_defaults_keep_telethon_call_unchanged(client):
    await messages.send_message(chat_id=CHAT_ID, message="https://example.com")
    assert "link_preview" not in client.send_message.await_args.kwargs


@pytest.mark.asyncio
async def test_send_message_without_preview(client):
    result = await messages.send_message(
        chat_id=CHAT_ID, message="https://example.com", link_preview=False
    )
    assert client.send_message.await_args.kwargs["link_preview"] is False
    assert "message_id=77" in result


@pytest.mark.asyncio
async def test_send_message_with_entities_without_preview(client):
    await messages.send_message(
        chat_id=CHAT_ID,
        message="Meet 13/09 https://example.com",
        format_date="13/09",
        link_preview=False,
    )
    request = client.await_args.args[0]
    assert isinstance(request, functions.messages.SendMessageRequest)
    assert request.no_webpage is True


@pytest.mark.asyncio
async def test_rich_send_without_preview(client):
    await messages.send_message(
        chat_id=CHAT_ID, message="**a** https://example.com", parse_mode="rich", link_preview=False
    )
    request = client.await_args.args[0]
    assert isinstance(request, functions.messages.SendMessageRequest)
    assert request.no_webpage is True


@pytest.mark.asyncio
async def test_edit_message_without_preview(client):
    result = await messages.edit_message(
        chat_id=CHAT_ID, message_id=5, new_text="https://example.com", link_preview=False
    )
    assert client.edit_message.await_args.kwargs["link_preview"] is False
    assert result == "Message 5 edited."


@pytest.mark.asyncio
async def test_edit_message_default_keeps_telethon_call_unchanged(client):
    await messages.edit_message(chat_id=CHAT_ID, message_id=5, new_text="x")
    assert client.edit_message.await_args.kwargs == {}


@pytest.mark.asyncio
async def test_rich_edit_without_preview(client):
    await messages.edit_message(
        chat_id=CHAT_ID, message_id=5, new_text="**a**", parse_mode="rich", link_preview=False
    )
    request = client.await_args.args[0]
    assert isinstance(request, functions.messages.EditMessageRequest)
    assert request.no_webpage is True
