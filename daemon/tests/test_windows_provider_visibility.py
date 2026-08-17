#!/usr/bin/env python3
"""Unit tests for the provider-visibility feature (hide unused AI tabs).

Covers _providers_enabled_now() / providers_enabled_tick() — the file-
existence checks and the daemon's send-only-on-change behavior. No BLE
hardware needed: a fake Session stands in for the real bleak client, same
pattern as test_windows_permission_broker.py.

Run: python -m pytest daemon/tests/test_windows_provider_visibility.py -x -q
"""
import asyncio

import pytest

import daemon.claude_usage_daemon_windows as d


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class FakeSession:
    def __init__(self, write_ok: bool = True):
        self.write_ok = write_ok
        self.written: list[dict] = []

    async def write_payload(self, payload: dict) -> bool:
        self.written.append(payload)
        return self.write_ok


@pytest.fixture(autouse=True)
def _isolated_state():
    """Reset the module-level send-once-on-change tracker between tests."""
    d._last_sent_providers_enabled = None
    yield
    d._last_sent_providers_enabled = None


@pytest.fixture
def _stub_paths(tmp_path, monkeypatch):
    """Point all three provider path lookups at scratch files/dirs, none of
    which exist yet — tests create them individually to flip a provider on."""
    claude_path = tmp_path / "claude_creds.json"
    codex_path = tmp_path / "codex_auth.json"
    gemini_path = tmp_path / "gemini_creds.json"
    monkeypatch.setattr(d, "_windows_credential_candidates", lambda: [claude_path])
    monkeypatch.setattr(d, "codex_auth_path", lambda: codex_path)
    monkeypatch.setattr(d, "gemini_creds_path", lambda: gemini_path)
    return claude_path, codex_path, gemini_path


def test_all_absent_reports_all_disabled(_stub_paths):
    assert d._providers_enabled_now() == (False, False, False)


def test_only_claude_present(_stub_paths):
    claude_path, _, _ = _stub_paths
    claude_path.write_text("{}")
    assert d._providers_enabled_now() == (True, False, False)


def test_only_codex_present(_stub_paths):
    _, codex_path, _ = _stub_paths
    codex_path.write_text("{}")
    assert d._providers_enabled_now() == (False, True, False)


def test_all_present(_stub_paths):
    claude_path, codex_path, gemini_path = _stub_paths
    claude_path.write_text("{}")
    codex_path.write_text("{}")
    gemini_path.write_text("{}")
    assert d._providers_enabled_now() == (True, True, True)


def test_tick_sends_on_first_call(_stub_paths):
    claude_path, _, _ = _stub_paths
    claude_path.write_text("{}")
    session = FakeSession()

    _run(d.providers_enabled_tick(session))

    assert session.written == [
        {"type": "providers", "claude": True, "codex": False, "antigravity": False}
    ]


def test_tick_does_not_resend_when_unchanged(_stub_paths):
    claude_path, _, _ = _stub_paths
    claude_path.write_text("{}")
    session = FakeSession()

    _run(d.providers_enabled_tick(session))
    _run(d.providers_enabled_tick(session))

    assert len(session.written) == 1


def test_tick_resends_when_set_changes(_stub_paths):
    claude_path, codex_path, _ = _stub_paths
    claude_path.write_text("{}")
    session = FakeSession()
    _run(d.providers_enabled_tick(session))

    codex_path.write_text("{}")  # user logs into Codex mid-session
    _run(d.providers_enabled_tick(session))

    assert len(session.written) == 2
    assert session.written[1] == {
        "type": "providers", "claude": True, "codex": True, "antigravity": False
    }


def test_tick_retries_after_a_failed_write(_stub_paths):
    claude_path, _, _ = _stub_paths
    claude_path.write_text("{}")
    session = FakeSession(write_ok=False)

    _run(d.providers_enabled_tick(session))
    assert d._last_sent_providers_enabled is None  # write failed, not recorded as sent

    session.write_ok = True
    _run(d.providers_enabled_tick(session))
    assert d._last_sent_providers_enabled == (True, False, False)
