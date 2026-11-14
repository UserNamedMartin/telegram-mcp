"""A stuck disconnect or connect must not wedge the account for the process lifetime."""

import asyncio

import pytest
from telethon.sessions import StringSession

from telegram_mcp import runtime


@pytest.fixture(autouse=True)
def _reset_reconnect_state(monkeypatch):
    monkeypatch.setattr(runtime, "_last_conn_verified", {})
    monkeypatch.setattr(runtime, "_conn_locks", {})
    monkeypatch.setattr(runtime, "_last_reconnect_failure", {})
    monkeypatch.setattr(runtime, "_DISCONNECT_TIMEOUT", 0.01)
    monkeypatch.setattr(runtime, "_RECONNECT_TIMEOUT", 0.01)


class _Client:
    def __init__(self, *, hang_disconnect=False, hang_connect=False):
        self.hang_disconnect = hang_disconnect
        self.hang_connect = hang_connect
        self.connected = False
        self.session = StringSession()
        self.handlers = []
        self.calls = []

    def is_connected(self):
        return self.connected

    async def disconnect(self):
        self.calls.append("disconnect")
        if self.hang_disconnect:
            await asyncio.sleep(3600)

    async def connect(self):
        self.calls.append("connect")
        if self.hang_connect:
            await asyncio.sleep(3600)
        self.connected = True

    async def is_user_authorized(self):
        return True

    def list_event_handlers(self):
        return list(self.handlers)

    def add_event_handler(self, callback, event):
        self.handlers.append((callback, event))


@pytest.mark.asyncio
async def test_hanging_disconnect_does_not_block_reconnect():
    client = _Client(hang_disconnect=True)

    await asyncio.wait_for(runtime.ensure_connected(client), timeout=1)

    assert client.calls == ["disconnect", "connect"]
    assert client.connected


@pytest.mark.asyncio
async def test_stuck_connect_swaps_in_fresh_client_for_next_call(monkeypatch):
    stuck = _Client(hang_connect=True)
    handler = (lambda event: None, "NewMessage")
    stuck.handlers.append(handler)
    fresh = _Client()
    built = []

    def build(session, label):
        built.append((session, label))
        return fresh

    monkeypatch.setattr(runtime, "clients", {"default": stuck})
    monkeypatch.setattr(runtime, "_build_client", build)

    with pytest.raises(RuntimeError, match="timed out.*fresh client"):
        await runtime.ensure_connected(stuck)

    assert runtime.clients["default"] is fresh
    assert built == [(stuck.session, "default")]
    assert fresh.handlers == [handler]

    await runtime.ensure_connected(runtime.get_client())
    assert fresh.connected


@pytest.mark.asyncio
async def test_unregistered_client_keeps_the_plain_timeout_error(monkeypatch):
    monkeypatch.setattr(runtime, "clients", {})
    client = _Client(hang_connect=True)

    with pytest.raises(RuntimeError) as excinfo:
        await runtime._force_reconnect(client)

    assert "timed out" in str(excinfo.value)
    assert "fresh client" not in str(excinfo.value)


@pytest.mark.asyncio
async def test_failed_rebuild_keeps_the_old_client(monkeypatch):
    stuck = _Client(hang_connect=True)
    monkeypatch.setattr(runtime, "clients", {"default": stuck})

    def broken_build(session, label):
        raise ValueError("bad proxy config")

    monkeypatch.setattr(runtime, "_build_client", broken_build)

    with pytest.raises(RuntimeError, match="timed out"):
        await runtime._force_reconnect(stuck)

    assert runtime.clients["default"] is stuck
