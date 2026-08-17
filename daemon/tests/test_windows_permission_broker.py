#!/usr/bin/env python3
"""Unit tests for the ESP32 permission-gate broker (daemon side).

Covers the pure request/result file lifecycle in permission_broker_tick() /
drain_requests_as_timeout() without any BLE hardware — a fake Session stands
in for the real bleak client.

Run: python -m pytest daemon/tests/test_windows_permission_broker.py -x -q
"""
import asyncio
import json
import time

import pytest

import daemon.claude_usage_daemon_windows as d


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class FakeSession:
    """Stands in for daemon.claude_usage_daemon_windows.Session — records
    every payload written and lets a test seed device-side decisions without
    any real BLE link."""

    def __init__(self, write_ok: bool = True):
        self.write_ok = write_ok
        self.written: list[dict] = []
        self.perm_decisions: dict[str, str] = {}

    async def write_payload(self, payload: dict) -> bool:
        self.written.append(payload)
        return self.write_ok


@pytest.fixture(autouse=True)
def _isolated_broker_state(tmp_path, monkeypatch):
    """Point PERM_REQUESTS_DIR at a scratch dir and reset in-memory tracking
    so tests never touch the real %LOCALAPPDATA% dir or leak state between
    each other."""
    monkeypatch.setattr(d, "PERM_REQUESTS_DIR", tmp_path)
    d._perm_inflight.clear()
    yield
    d._perm_inflight.clear()


def _write_request(rid: str, provider="claude", tool="Bash", desc="echo hi", ttl=55, mtime=None):
    path = d.PERM_REQUESTS_DIR / f"{rid}.request.json"
    path.write_text(json.dumps({"provider": provider, "tool": tool, "desc": desc, "ttl": ttl}))
    if mtime is not None:
        import os
        os.utime(path, (mtime, mtime))
    return path


def _read_result(rid: str) -> dict:
    return json.loads((d.PERM_REQUESTS_DIR / f"{rid}.result.json").read_text())


# ---------------------------------------------------------------------------
# drain_requests_as_timeout — device unreachable
# ---------------------------------------------------------------------------

def test_drain_writes_timeout_and_removes_request():
    _write_request("abcd1234")
    d.drain_requests_as_timeout()

    assert _read_result("abcd1234") == {"decision": "timeout"}
    assert not (d.PERM_REQUESTS_DIR / "abcd1234.request.json").exists()


def test_drain_is_a_noop_with_no_requests():
    d.drain_requests_as_timeout()  # must not raise on an empty dir
    assert list(d.PERM_REQUESTS_DIR.glob("*")) == []


# ---------------------------------------------------------------------------
# permission_broker_tick — connected path
# ---------------------------------------------------------------------------

def test_tick_relays_new_request_over_ble():
    _write_request("rid00001", provider="codex", tool="Bash", desc="rm -rf /tmp/x", ttl=30)
    session = FakeSession()

    _run(d.permission_broker_tick(session))

    assert len(session.written) == 1
    payload = session.written[0]
    assert payload == {
        "type": "perm", "id": "codex", "rid": "rid00001",
        "tool": "Bash", "desc": "rm -rf /tmp/x", "ttl": 30,
    }
    assert "rid00001" in d._perm_inflight
    # Not resolved yet — no result file should exist.
    assert not (d.PERM_REQUESTS_DIR / "rid00001.result.json").exists()


def test_tick_does_not_resend_an_inflight_request():
    _write_request("rid00002")
    session = FakeSession()

    _run(d.permission_broker_tick(session))
    _run(d.permission_broker_tick(session))

    assert len(session.written) == 1  # second tick must not resend


def test_tick_writes_result_when_device_decides():
    _write_request("rid00003")
    session = FakeSession()
    _run(d.permission_broker_tick(session))  # relays it, becomes in-flight

    session.perm_decisions["rid00003"] = "allow"
    _run(d.permission_broker_tick(session))  # picks up the decision

    assert _read_result("rid00003") == {"decision": "allow"}
    assert "rid00003" not in d._perm_inflight
    assert not (d.PERM_REQUESTS_DIR / "rid00003.request.json").exists()


def test_tick_times_out_and_cancels_stale_inflight_request():
    _write_request("rid00004", ttl=5)
    session = FakeSession()
    _run(d.permission_broker_tick(session))
    assert "rid00004" in d._perm_inflight

    # Simulate the ttl having elapsed without a device decision.
    d._perm_inflight["rid00004"]["sent_at"] = time.time() - 999

    _run(d.permission_broker_tick(session))

    assert _read_result("rid00004") == {"decision": "timeout"}
    assert "rid00004" not in d._perm_inflight
    # A perm_cancel should have been sent so a still-showing modal dismisses.
    cancel_msgs = [m for m in session.written if m.get("type") == "perm_cancel"]
    assert cancel_msgs == [{"type": "perm_cancel", "rid": "rid00004"}]


def test_tick_writes_timeout_when_ble_write_fails():
    _write_request("rid00005")
    session = FakeSession(write_ok=False)

    _run(d.permission_broker_tick(session))

    assert _read_result("rid00005") == {"decision": "timeout"}
    assert "rid00005" not in d._perm_inflight
    assert not (d.PERM_REQUESTS_DIR / "rid00005.request.json").exists()


def test_tick_drops_orphaned_request_without_relaying():
    _write_request("rid00006", mtime=time.time() - d.PERM_MAX_AGE_S - 60)
    session = FakeSession()

    _run(d.permission_broker_tick(session))

    assert session.written == []
    assert not (d.PERM_REQUESTS_DIR / "rid00006.request.json").exists()
    assert not (d.PERM_REQUESTS_DIR / "rid00006.result.json").exists()


def test_tick_drops_malformed_request_file():
    (d.PERM_REQUESTS_DIR / "rid00007.request.json").write_text("not json")
    session = FakeSession()

    _run(d.permission_broker_tick(session))

    assert session.written == []
    assert not (d.PERM_REQUESTS_DIR / "rid00007.request.json").exists()


def test_tick_sweeps_orphaned_result_file():
    """A hook that resolved via its terminal race (see hooks/_broker.py)
    deletes its own request file but may never read the result the daemon
    wrote — that result file must eventually be swept, not litter forever."""
    import os

    result_path = d.PERM_REQUESTS_DIR / "rid00008.result.json"
    result_path.write_text(json.dumps({"decision": "allow"}))
    old = time.time() - 121
    os.utime(result_path, (old, old))
    session = FakeSession()

    _run(d.permission_broker_tick(session))

    assert not result_path.exists()


def test_tick_keeps_fresh_orphaned_result_file():
    """A result file younger than the sweep threshold is left alone — the
    hook may just not have polled it yet."""
    result_path = d.PERM_REQUESTS_DIR / "rid00009.result.json"
    result_path.write_text(json.dumps({"decision": "allow"}))
    session = FakeSession()

    _run(d.permission_broker_tick(session))

    assert result_path.exists()
