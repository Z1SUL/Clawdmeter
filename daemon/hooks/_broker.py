#!/usr/bin/env python3
"""Shared broker client for the ESP32 permission-gate hooks.

Each CLI-specific hook (claude_permission_hook.py, codex_permission_hook.py,
antigravity_permission_hook.py) calls request_permission() to hand a pending
tool call to the Clawdmeter device and race it against a terminal keypress —
whichever answers first wins. This writes a <rid>.request.json file into the
daemon's PERM_REQUESTS_DIR and polls for <rid>.result.json, which
claude_usage_daemon_windows.permission_broker_tick() writes once the device
(or a timeout) decides. See daemon/hooks/README.md for how to wire a hook
into a CLI's config, and the plan doc for the full protocol.

Windows-only (uses msvcrt for the terminal-keypress race), matching this
project's Windows-first daemon scope. A timeout here must never be treated
as an allow by the caller — see each hook script's mapping.
"""
import json
import os
import secrets
import sys
import time
from pathlib import Path

try:
    import msvcrt
except ImportError:
    msvcrt = None  # non-Windows: degrades to file-poll-only, no terminal race

PERM_REQUESTS_DIR = (
    Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    / "Clawdmeter" / "perm_requests"
)
_POLL_INTERVAL_S = 0.15


def request_permission(provider: str, tool: str, desc: str, ttl: int = 55) -> str:
    """Block until the Clawdmeter device or this terminal answers, or `ttl`
    seconds elapse. Returns "allow", "deny", or "timeout" — never raises, so
    a broker/filesystem hiccup degrades to "timeout" rather than wedging the
    CLI that called this.
    """
    rid = secrets.token_hex(4)
    req_path = PERM_REQUESTS_DIR / f"{rid}.request.json"
    result_path = PERM_REQUESTS_DIR / f"{rid}.result.json"
    try:
        PERM_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
        req_path.write_text(
            json.dumps({"provider": provider, "tool": tool, "desc": desc, "ttl": ttl}),
            encoding="utf-8",
        )
    except OSError as e:
        print(f"[Clawdmeter] Could not reach the permission broker: {e}", file=sys.stderr)
        return "timeout"

    print(
        f"[Clawdmeter] Waiting for approval on the device, or press y/n here "
        f"({ttl}s) — {tool}: {desc}",
        file=sys.stderr,
    )

    decision = "timeout"
    deadline = time.monotonic() + ttl
    try:
        while time.monotonic() < deadline:
            if result_path.exists():
                try:
                    decision = json.loads(result_path.read_text(encoding="utf-8")).get(
                        "decision", "timeout"
                    )
                except (OSError, json.JSONDecodeError):
                    decision = "timeout"
                break
            if msvcrt is not None and msvcrt.kbhit():
                key = msvcrt.getch().decode("utf-8", errors="ignore").lower()
                if key == "y":
                    decision = "allow"
                    break
                if key == "n":
                    decision = "deny"
                    break
            time.sleep(_POLL_INTERVAL_S)
    finally:
        # Best-effort cleanup — if the device later writes a result after we
        # already decided via the terminal, permission_broker_tick's own
        # orphan sweep clears that leftover file on the daemon side.
        req_path.unlink(missing_ok=True)
        result_path.unlink(missing_ok=True)

    print(f"[Clawdmeter] Decision: {decision}", file=sys.stderr)
    return decision
