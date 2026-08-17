#!/usr/bin/env python3
"""Codex CLI PermissionRequest hook — routes permission requests to Clawd on ESP32.

NOT wired into any live Codex config by default — see daemon/hooks/README.md.

Codex's PermissionRequest hook is newer and less battle-tested than Claude
Code's PreToolUse (added for "parity with claude code's auto-approve flow",
openai/codex#16301/#17563) — the exact input field names and output schema
below were confirmed against secondary sources (docs aggregator + GitHub
issues), NOT a live install. Smoke-test this against your actual Codex CLI
version (print the raw stdin to a scratch file first) before trusting it for
real work.

Assumed contract:
  stdin:  {"tool_name": "...", "tool_input": {...}, "hook_event_name": "PermissionRequest", ...}
  stdout: {"hookSpecificOutput": {"hookEventName": "PermissionRequest",
                                   "decision": {"behavior": "allow"|"deny", "message": "..."}}}
  exit 0 either way.

Codex's schema doesn't (per current research) expose a neutral "ask"
pass-through the way Claude Code's does — so unlike the Claude hook, a
"timeout" here maps to DENY (fail-safe) rather than guessing at an
unconfirmed pass-through value. Revisit once the schema is verified live.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _broker import request_permission  # noqa: E402


def _describe(tool_input: dict) -> str:
    for key in ("command", "file_path", "pattern", "url"):
        if key in tool_input and tool_input[key]:
            return str(tool_input[key])[:96]
    return json.dumps(tool_input)[:96]


def main() -> None:
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        sys.exit(0)

    tool_name = event.get("tool_name", "?")
    tool_input = event.get("tool_input") or {}
    desc = _describe(tool_input)

    decision = request_permission("codex", tool_name, desc, ttl=55)

    if decision == "allow":
        behavior = {"behavior": "allow"}
    else:  # "deny" or "timeout" — fail-safe, see module docstring
        behavior = {"behavior": "deny", "message": "Denied via Clawd on ESP32"}

    output = {"hookSpecificOutput": {
        "hookEventName": "PermissionRequest", "decision": behavior,
    }}
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
