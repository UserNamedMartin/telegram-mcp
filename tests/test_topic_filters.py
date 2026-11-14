"""get_messages, list_messages and search_messages accept a forum topic_id."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from telethon.tl import functions, types

from telegram_mcp.tools import messages

DATE = datetime(2026, 10, 5, tzinfo=timezone.utc)
CHANNEL_ID = 1234567890
CHAT_ID = -1001234567890
TOPIC_ID = 3173


def _msg(msg_id, text="hello"):
    return types.Message(
        id=msg_id,
        peer_id=types.PeerChannel(CHANNEL_ID),
        date=DATE,
        message=text,
        reply_to=types.MessageReplyHeader(forum_topic=True, reply_to_msg_id=TOPIC_ID),
    )


class AsyncIter:
    def __init__(self, items):
        self.items = list(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.items:
            raise StopAsyncIteration
        return self.items.pop(0)


@pytest.fixture
def client(monkeypatch):
    cl = AsyncMock()
    cl._mb_entity_cache = MagicMock()  # read synchronously by Message._finish_init
    cl.get_input_entity.return_value = types.InputPeerChannel(CHANNEL_ID, 1)
    monkeypatch.setattr(messages, "get_client", lambda account=None: cl)
    monkeypatch.setattr(
        messages,
        "resolve_entity",
        AsyncMock(
            return_value=types.Channel(
                id=CHANNEL_ID,
                title="Forum",
                photo=types.ChatPhotoEmpty(),
                date=DATE,
                forum=True,
            )
        ),
    )
    monkeypatch.setattr(messages, "topics_for_messages", AsyncMock(return_value={}))
    monkeypatch.setattr(messages.transcription, "prefetch_transcripts", AsyncMock())
    return cl


def _search_result(*msgs):
    return types.messages.Messages(messages=list(msgs), topics=[], chats=[], users=[])


@pytest.mark.asyncio
async def test_get_messages_pages_the_topic_thread(client):
    client.get_messages.return_value = [_msg(11)]

    result = await messages.get_messages(chat_id=CHAT_ID, page=2, page_size=10, topic_id=TOPIC_ID)

    assert client.get_messages.await_args.kwargs == {
        "limit": 10,
        "add_offset": 10,
        "reply_to": TOPIC_ID,
    }
    assert "ID: 11" in result


@pytest.mark.asyncio
async def test_get_messages_without_topic_is_unchanged(client):
    client.get_messages.return_value = []
    await messages.get_messages(chat_id=CHAT_ID)
    assert client.get_messages.await_args.kwargs == {"limit": 20, "add_offset": 0}


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ["get_messages", "list_messages"])
@pytest.mark.parametrize("bad", ["general", 0, -5])
async def test_invalid_topic_id_is_rejected(client, tool, bad):
    result = await getattr(messages, tool)(chat_id=CHAT_ID, topic_id=bad)
    assert result == messages.TOPIC_ID_ERROR
    client.get_messages.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_messages_reads_topic_thread(client):
    client.get_messages.return_value = [_msg(12)]

    result = await messages.list_messages(chat_id=CHAT_ID, limit=5, topic_id=str(TOPIC_ID))

    assert client.get_messages.await_args.kwargs == {"limit": 5, "reply_to": TOPIC_ID}
    assert [r["id"] for r in json.loads(result)["results"]] == [12]


@pytest.mark.asyncio
async def test_list_messages_date_walk_stays_in_topic(client):
    client.iter_messages = lambda *a, **kw: (client.iter_kwargs.append(kw), AsyncIter([]))[1]
    client.iter_kwargs = []

    await messages.list_messages(chat_id=CHAT_ID, from_date="2026-10-01", topic_id=TOPIC_ID)

    assert client.iter_kwargs[0]["reply_to"] == TOPIC_ID


@pytest.mark.asyncio
async def test_search_in_topic_uses_server_side_top_msg_id(client):
    client.return_value = _search_result(_msg(21, "invoice"), _msg(20, "Invoice paid"))

    result = await messages.search_messages(
        chat_id=CHAT_ID, query="invoice", limit=5, topic_id=TOPIC_ID
    )

    request = client.await_args.args[0]
    assert isinstance(request, functions.messages.SearchRequest)
    assert request.top_msg_id == TOPIC_ID
    assert request.q == "invoice"
    client.get_messages.assert_not_awaited()
    assert [r["id"] for r in json.loads(result)["results"]] == [21, 20]


@pytest.mark.asyncio
async def test_search_in_topic_respects_limit_across_pages(client):
    first = types.messages.MessagesSlice(
        count=3, messages=[_msg(30), _msg(29)], topics=[], chats=[], users=[]
    )
    second = _search_result(_msg(28))
    client.side_effect = [first, second]

    result = await messages.search_messages(
        chat_id=CHAT_ID, query="hello", limit=3, topic_id=TOPIC_ID
    )

    assert [r["id"] for r in json.loads(result)["results"]] == [30, 29, 28]
    assert client.await_args_list[1].args[0].offset_id == 29


@pytest.mark.asyncio
async def test_list_messages_search_in_topic(client):
    client.return_value = _search_result(_msg(41, "report"))

    result = await messages.list_messages(
        chat_id=CHAT_ID, search_query="report", to_date="2026-10-31", topic_id=TOPIC_ID
    )

    request = client.await_args.args[0]
    assert request.top_msg_id == TOPIC_ID
    assert request.max_date == datetime(2026, 11, 1, tzinfo=timezone.utc)
    assert [r["id"] for r in json.loads(result)["results"]] == [41]
