# Changelog

## [0.0.2] - 2026-05-12

### Changed

- Alert dialog switched from tkinter to OS-native backends (osascript on macOS, zenity / kdialog / xmessage on Linux, PowerShell MessageBox on Windows). Tkinter dialogs launched from a detached subprocess didn't reliably surface on the active macOS Space.

### Fixed

- LLM-call failures (missing API key, rate limit, network error, parse failure) now surface as a yellow `systemMessage` banner in Claude Code instead of silently allowing the tool call. The agent still proceeds (fail-open), but the user sees why the monitor stopped working.
- Silenced litellm's colored "Give Feedback / Get Help" banners on stdout. Previously they corrupted the hook's JSON output and broke Claude Code's parser whenever any LLM error occurred.

## [0.0.1] - 2026-05-12

### Added

- Initial public release.
- PreToolUse safety monitor for Claude Code with LLM-based trajectory analysis.
- Tkinter alert dialog (cross-platform, stdlib only).
- Local audit logs: `monitor_<s8>.log` and `monitor_usage_<session>.jsonl`.
