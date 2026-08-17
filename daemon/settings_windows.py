#!/usr/bin/env python3
"""Token / credentials settings window for Clawdmeter — Windows only.

Launched from the tray menu's "Token Settings..." item as a SEPARATE PROCESS
(tray_windows.py does `subprocess.Popen([pythonw.exe, this file])`) rather
than as an in-process Toplevel. Tkinter's mainloop and pystray's own event
loop both want to own the thread they run on, so keeping this a standalone
process sidesteps that fight entirely instead of trying to thread it in.

Shows, per provider, whether a token/credential file is currently found and
lets the user point the daemon at a non-default location (useful when a CLI
stores its login somewhere unusual, or when testing with a second account).
Overrides are persisted as plain `key = value` lines in the same CONFIG_FILE
the daemon already uses for chime/clock settings
(%LOCALAPPDATA%\\Clawdmeter\\config) via write_config_overrides(), so the
running daemon/tray picks them up on its next read — no restart needed.

Usage::

    pythonw settings_windows.py
"""

import os
import sys

# Repo root = the directory that CONTAINS the `daemon` package (this file is
# <repo>/daemon/settings_windows.py). Mirrors tray_windows.py's resolution so
# this also works launched standalone with cwd != repo root.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Launched via the BASE pythonw.exe (see tray_windows.py's _open_settings),
# which doesn't see the venv's site-packages — add them so `daemon`'s imports
# (httpx, bleak) resolve. Harmless no-op if already inside the venv or if
# there is no venv.
_VENV_SITE = os.path.join(_REPO_ROOT, ".venv", "Lib", "site-packages")
if os.path.isdir(_VENV_SITE):
    import site
    site.addsitedir(_VENV_SITE)

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import daemon.claude_usage_daemon_windows as d

_PAD = 10


def _claude_status() -> tuple[str, str]:
    token = d.read_token()
    if not token:
        tried = ", ".join(str(p) for p in d._windows_credential_candidates())
        return ("not found", f"checked: {tried}")
    return ("found", f"expires {d._read_expiry()}")


def _codex_status() -> tuple[str, str]:
    auth = d._read_codex_auth()
    tokens = auth.get("tokens", {}) if isinstance(auth, dict) and isinstance(auth.get("tokens"), dict) else {}
    if not tokens.get("access_token"):
        return ("not found", f"checked: {d.codex_auth_path()}")
    return ("found", f"account {tokens.get('account_id') or 'unknown'}")


def _antigravity_status() -> tuple[str, str]:
    creds = d._read_gemini_creds()
    if not creds or not creds.get("refresh_token"):
        return ("not found", f"checked: {d.gemini_creds_path()}")
    return ("found", "refresh token present")


class ProviderRow:
    """One provider's status line + path override entry, inside `parent`."""

    def __init__(self, parent: ttk.Frame, row: int, title: str, config_key: str,
                 default_path, status_fn):
        self.config_key = config_key
        self.default_path = str(default_path)
        self.status_fn = status_fn

        ttk.Label(parent, text=title, font=("Segoe UI", 10, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(_PAD, 0)
        )

        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(parent, textvariable=self.status_var)
        self.status_label.grid(row=row + 1, column=0, columnspan=3, sticky="w")

        ttk.Label(parent, text="Path:").grid(row=row + 2, column=0, sticky="w")
        self.path_var = tk.StringVar()
        entry = ttk.Entry(parent, textvariable=self.path_var, width=52)
        entry.grid(row=row + 2, column=1, sticky="we", padx=(4, 4))
        ttk.Button(parent, text="Browse...", command=self._browse).grid(row=row + 2, column=2)
        ttk.Button(parent, text="Reset to default", command=self._reset).grid(
            row=row + 3, column=1, columnspan=2, sticky="w", pady=(2, 0)
        )

        self.refresh()

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select credentials file",
            initialdir=os.path.dirname(self.path_var.get() or self.default_path),
        )
        if path:
            self.path_var.set(path)

    def _reset(self) -> None:
        self.path_var.set(self.default_path)

    def refresh(self) -> None:
        state, detail = self.status_fn()
        self.status_var.set(f"{'✓' if state == 'found' else '✗'} {state} — {detail}")
        self.status_label.configure(foreground="#1a7f37" if state == "found" else "#c0392b")
        override = d._config_value(self.config_key)
        self.path_var.set(override or self.default_path)

    def pending_override(self) -> str:
        """Value to persist: '' (delete override) if the field equals the default."""
        current = self.path_var.get().strip()
        if not current or current == self.default_path:
            return ""
        return current


class SettingsApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("Clawdmeter — Token Settings")
        root.resizable(False, False)

        outer = ttk.Frame(root, padding=_PAD)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)

        ttk.Label(
            outer,
            text="Each provider's token is normally auto-detected from its own "
                 "CLI login. Only change a path below if auto-detection fails\n"
                 "or you want the daemon to read a non-default account.",
            wraplength=520, justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, _PAD))

        self.rows = [
            ProviderRow(outer, 1, "Claude", "claude_credentials_path",
                        d.claude_credentials_default(), _claude_status),
            ProviderRow(outer, 5, "Codex", "codex_auth_path", d.CODEX_AUTH_FILE, _codex_status),
            ProviderRow(outer, 9, "Antigravity (Gemini CLI)", "gemini_creds_path",
                        d.GEMINI_OAUTH_CREDS_FILE, _antigravity_status),
        ]

        btns = ttk.Frame(outer)
        btns.grid(row=13, column=0, columnspan=3, sticky="e", pady=(_PAD, 0))
        ttk.Button(btns, text="Refresh status", command=self._refresh_all).pack(side="left", padx=4)
        ttk.Button(btns, text="Save", command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Close", command=root.destroy).pack(side="left", padx=4)

    def _refresh_all(self) -> None:
        for row in self.rows:
            row.refresh()

    def _save(self) -> None:
        updates = {row.config_key: row.pending_override() for row in self.rows}
        try:
            d.write_config_overrides(updates)
        except OSError as e:
            messagebox.showerror("Clawdmeter", f"Could not save settings:\n{e}")
            return
        self._refresh_all()
        messagebox.showinfo("Clawdmeter", "Saved. The daemon picks up changes on its next poll (~60s).")


def main() -> None:
    root = tk.Tk()
    SettingsApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
