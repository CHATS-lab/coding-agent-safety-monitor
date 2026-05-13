# Changelog

## [0.0.5] - 2026-05-12

### Changed

- Dialog title is cleaner: dropped the 🚨 emoji and the redundant "Critical: " prefix.
- Diagnostic titles shortened to fit one line.
- LLM-returned `issue_type` is humanized before display: snake_case / kebab-case → Title Case, length capped at 32 chars.

### Added

- README screenshots of the two most common dialog scenarios (suspicion finding and missing API key) under `assets/`.

## [0.0.4] - 2026-05-12

### Added

- `.env` file search now covers four standard locations in priority order: `<cwd>/.env`, `~/.claude/.env`, `~/.env`, and the plugin dir.
- Dialog body is now kept short (one line). The longer fix instruction lives in the Claude Code permission prompt where there's more room.

## [0.0.3] - 2026-05-12

### Changed

- LLM-call failures now emit `permissionDecision: "ask"` instead of a `systemMessage`-only banner.
- On LLM failure, the desktop alert dialog also pops up so the user is doubly notified.

## [0.0.2] - 2026-05-12

### Changed

- Alert dialog switched from tkinter to OS-native backends (osascript on macOS, zenity / kdialog / xmessage on Linux, PowerShell MessageBox on Windows).

### Fixed

- LLM-call failures (missing API key, rate limit, network error, parse failure) now surface as a yellow `systemMessage` banner.
- Silenced litellm's colored "Give Feedback / Get Help" banners on stdout.

## [0.0.1] - 2026-05-12

### Added

- Initial public release.
- PreToolUse safety monitor for Claude Code with LLM-based trajectory analysis.
- Tkinter alert dialog (cross-platform, stdlib only).
- Local audit logs: `monitor_<s8>.log` and `monitor_usage_<session>.jsonl`.
