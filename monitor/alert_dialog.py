#!/usr/bin/env python3
"""Cross-platform safety-monitor alert dialog using OS-native tools.

Usage:
    python alert_dialog.py <severity> <issue_type> <body> <action_line>

Uses native OS dialog backends — no tkinter, no extra deps:
- macOS:   `osascript display alert` (rendered by the window server, always
           appears on the active Space and current monitor)
- Linux:   zenity → kdialog → xmessage fallback chain
- Windows: PowerShell `System.Windows.Forms.MessageBox`

Process blocks until the user dismisses the dialog, then exits 0.
"""

import os
import platform
import shutil
import subprocess
import sys

SEVERITY = sys.argv[1] if len(sys.argv) > 1 else "Critical"
ISSUE_TYPE = sys.argv[2] if len(sys.argv) > 2 else "Unknown Issue"
BODY_TEXT = sys.argv[3] if len(sys.argv) > 3 else "No details available."
ACTION_TEXT = (
    sys.argv[4] if len(sys.argv) > 4 else "Review the pending action carefully."
)


def _escape_applescript(text: str) -> str:
    """Escape text for AppleScript double-quoted strings."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _escape_powershell(text: str) -> str:
    """Escape text for PowerShell single-quoted strings."""
    return text.replace("'", "''").replace("\n", "`n")


def _show_macos_dialog(title: str, message: str) -> int:
    """Display a native macOS alert via osascript (blocking).

    `display alert` is rendered by the window server itself, so it always
    appears on the active monitor and current Space — even when launched
    from a detached background process.
    """
    safe_title = _escape_applescript(title)
    safe_message = _escape_applescript(message)
    alert_type = "critical" if SEVERITY.lower() == "critical" else "warning"
    script = (
        f'display alert "{safe_title}" '
        f'message "{safe_message}" '
        f"as {alert_type} "
        f'buttons {{"OK"}} '
        f'default button "OK"'
    )
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return result.returncode


def _show_linux_dialog(title: str, message: str) -> int:
    """Display a native Linux dialog using the best available tool (blocking).

    Tries zenity, kdialog, and xmessage in order. Returns 1 if no graphical
    display is available or no dialog tool is found.
    """
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print("alert_dialog: no DISPLAY/WAYLAND_DISPLAY set", file=sys.stderr)
        return 1

    commands = [
        ["zenity", "--warning", "--title", title, "--text", message, "--no-wrap"],
        ["kdialog", "--sorry", f"{title}\n\n{message}"],
        ["xmessage", "-center", f"{title}\n\n{message}"],
    ]
    for cmd in commands:
        if shutil.which(cmd[0]):
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode

    print("alert_dialog: no Linux dialog tool found", file=sys.stderr)
    return 1


def _show_windows_dialog(title: str, message: str) -> int:
    """Display a native Windows message box via PowerShell (blocking)."""
    safe_title = _escape_powershell(title)
    safe_message = _escape_powershell(message)
    icon = "Error" if SEVERITY.lower() == "critical" else "Warning"
    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "[System.Windows.Forms.MessageBox]::Show("
        f"'{safe_message}', '{safe_title}', 'OK', '{icon}')"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        text=True,
    )
    return result.returncode


def main() -> int:
    """Launch the best available native dialog for the current OS."""
    title = f"\U0001f6a8 {SEVERITY}: {ISSUE_TYPE}"
    message = f"{BODY_TEXT}\n\n{ACTION_TEXT}"
    system = platform.system()

    if system == "Darwin":
        return _show_macos_dialog(title, message)
    if system == "Linux":
        return _show_linux_dialog(title, message)
    if system == "Windows":
        return _show_windows_dialog(title, message)

    print(f"Unsupported platform: {system}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
