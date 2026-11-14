"""send_video_note sends an MP4 as a round video note with real size and duration."""

from pathlib import Path

import pytest

from telegram_mcp import runtime
from telegram_mcp.tools import media
from test_send_file_video_meta import _mp4, _mvhd, _tkhd, _trak


class _Client:
    def __init__(self):
        self.file = None
        self.kwargs = None

    async def send_file(self, entity, file, **kwargs):
        self.file = file
        self.kwargs = kwargs
        return type("Sent", (), {"id": 501})()


@pytest.fixture
def wired(tmp_path, monkeypatch):
    root = (tmp_path / "root").resolve()
    root.mkdir()
    client = _Client()
    monkeypatch.setattr(runtime, "SERVER_ALLOWED_ROOTS", [root])
    monkeypatch.setattr(media, "clients", {"default": client})
    monkeypatch.setattr(media, "get_client", lambda account=None: client)

    async def _resolve_entity(chat_id, cl):
        return "entity:chat"

    monkeypatch.setattr(media, "resolve_entity", _resolve_entity)
    return root, client


@pytest.mark.asyncio
async def test_sends_round_video_with_parsed_attributes(wired):
    root, client = wired
    (root / "note.mp4").write_bytes(_mp4(_mvhd(9000), _trak(_tkhd(384, 384))))

    result = await media.send_video_note("chat", "note.mp4", topic_id=7)

    assert client.file == str(root / "note.mp4")
    assert client.kwargs["video_note"] is True
    assert client.kwargs["reply_to"] == 7
    (attributes,) = client.kwargs["attributes"]
    assert attributes.round_message is True
    assert (attributes.w, attributes.h, attributes.duration) == (384, 384, 9)
    assert "Video note sent" in result
    assert "MessageIDs: [501]" in result


@pytest.mark.asyncio
async def test_unparseable_mp4_falls_back_to_telethon_attributes(wired):
    root, client = wired
    (root / "note.mp4").write_bytes(b"not an mp4")

    await media.send_video_note("chat", "note.mp4")

    assert client.kwargs["video_note"] is True
    assert "attributes" not in client.kwargs


@pytest.mark.asyncio
async def test_rejects_non_mp4(wired):
    root, client = wired
    (root / "clip.mov").write_bytes(b"x")

    result = await media.send_video_note("chat", "clip.mov")

    assert "File extension is not allowed for send_video_note" in result
    assert client.kwargs is None


def test_video_note_has_size_limit():
    assert runtime.MAX_FILE_BYTES["send_video_note"] == 100 * 1024 * 1024
    assert Path("a.mp4").suffix in runtime.EXTENSION_ALLOWLISTS["send_video_note"]
