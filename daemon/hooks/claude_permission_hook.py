#!/usr/bin/env python3
"""Claude Code PreToolUse hook — routes permission requests to Clawd on ESP32.

NOT wired into any live Claude Code config by default. See
daemon/hooks/README.md for how to enable this, and enable it project-scoped
(that project's own .claude/settings.json) in a disposable test project
first — never the global ~/.claude/settings.json — since this blocks on a
BLE round-trip and a bug here would affect every future Claude Code session.

Contract (Claude Code's documented PreToolUse hook):
  stdin:  {"tool_name": "...", "tool_input": {...}, "hook_event_name": "PreToolUse", ...}
  stdout: {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "allow"|"deny"|"ask",
                                   "permissionDecisionReason": "..." (optional)}}
  exit 0 either way — a nonzero exit is a hook error, not a decision.

On "timeout" this emits permissionDecision:"ask", which hands off to Claude
Code's own normal interactive prompt — the documented, confirmed-safe
pass-through for this CLI.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _broker import request_permission  # noqa: E402


def _describe(tool_name: str, tool_input: dict) -> str:
    for key in ("command", "file_path", "pattern", "url", "prompt"):
        if key in tool_input and tool_input[key]:
            return str(tool_input[key])[:96]
    return json.dumps(tool_input)[:96]


def main() -> None:
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        sys.exit(0)  # malformed input — say nothing, let Claude Code's own flow handle it

    tool_name = event.get("tool_name", "?")
    tool_input = event.get("tool_input") or {}
    desc = _describe(tool_name, tool_input)

    decision = request_permission("claude", tool_name, desc, ttl=55)

    if decision == "allow":
        output = {"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "allow",
        }}
    elif decision == "deny":
        output = {"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": "Denied via Clawd on ESP32",
        }}
    else:  # timeout — fall through to Claude Code's own prompt
        output = {"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "ask",
        }}

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
