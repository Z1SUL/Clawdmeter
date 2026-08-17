#!/usr/bin/env python3
"""Antigravity / Gemini CLI BeforeTool hook — routes permission requests to
Clawd on ESP32.

NOT wired into any live Gemini/Antigravity config by default — see
daemon/hooks/README.md.

Confirmed real (Gemini CLI hooks blog post + docs), but NOT verified against
a live install: whether Antigravity CLI reads hook config from the same
~/.gemini/settings.json as plain Gemini CLI, from its own
~/.gemini/antigravity-cli/ tree, or a project-local file — the same kind of
gap the earlier credential-path investigation (see CLAUDE.md) hit for this
provider. Verify by installing a trivial hook and checking the CLI's /hooks
equivalent before wiring the real one in.

Assumed contract (BeforeTool):
  stdin:  tool-call JSON (exact shape unconfirmed for Antigravity specifically)
  stdout: {"decision": "allow"} or {"decision": "deny", "reason": "..."}
  exit 0 either way.

No neutral pass-through value was found in research for this event, so
"timeout" maps to DENY (fail-safe), same posture as the Codex hook.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _broker import request_permission  # noqa: E402


def _describe(event: dict) -> str:
    tool_input = event.get("tool_input") or event.get("params") or {}
    if isinstance(tool_input, dict):
        for key in ("command", "file_path", "pattern", "url"):
            if key in tool_input and tool_input[key]:
                return str(tool_input[key])[:96]
    return json.dumps(event)[:96]


def main() -> None:
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        sys.exit(0)

    tool_name = event.get("tool_name") or event.get("tool") or "?"
    desc = _describe(event)

    decision = request_permission("antigravity", str(tool_name), desc, ttl=55)

    if decision == "allow":
        output = {"decision": "allow"}
    else:  # "deny" or "timeout" — fail-safe, see module docstring
        output = {"decision": "deny", "reason": "Denied via Clawd on ESP32"}

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
