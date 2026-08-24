# Permission-gate hooks

Lets Claude Code / Codex CLI show a pending tool-call
approval on the Clawd on ESP32 device and gate on the device's Allow/Deny (or a
`y`/`n` keypress in the same terminal — whichever answers first wins).

**Nothing here is wired into any of your CLI configs automatically.** These
scripts only run once you add the config snippet below yourself. Do that in
a throwaway test project first, with `.claude/settings.json` **inside that
project** — not `~/.claude/settings.json`. A global hook that blocks on a
BLE round-trip affects every future session in every project if something
about the device, the daemon, or the hook itself misbehaves; keep that risk
scoped until you've used it enough to trust it.

Requires the daemon (`claude_usage_daemon_windows.py` / the tray app) to be
running — the hook blocks waiting on `%LOCALAPPDATA%\ClawdOnESP32\perm_requests\`,
which only the running daemon drains. If the daemon isn't running, every
request times out after its `ttl` (default 55s) with no device round-trip at
all — mildly annoying, never a hang.

## Claude Code (high confidence — documented, mature hook contract)

In a **project's own** `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "python \"C:\\path\\to\\esp32-project\\daemon\\hooks\\claude_permission_hook.py\"", "timeout": 60 }
        ]
      }
    ]
  }
}
```

Widen `matcher` (e.g. `"Bash|Edit|Write"`) once you've confirmed the basic
flow works. A timeout falls through to Claude Code's own normal prompt.

## Codex CLI (real feature, schema not verified live — see script docstring)

In `~/.codex/config.toml` (or a project-local `.codex/config.toml`):

```toml
[[hooks.PermissionRequest]]
matcher = "^Bash$"

[[hooks.PermissionRequest.hooks]]
type = "command"
command = 'python "C:\path\to\esp32-project\daemon\hooks\codex_permission_hook.py"'
timeout = 60
```

Smoke-test with a harmless command first. A timeout here denies (fail-safe)
rather than falling through — see the script's docstring for why.

## Removing a hook

Delete the entry from the config file you added it to. Nothing else on disk
needs cleaning up — the hook scripts create no persistent state outside the
per-request files in `perm_requests\`, which the daemon and the hook itself
both clean up as they go.
