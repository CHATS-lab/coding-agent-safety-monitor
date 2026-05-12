# Roadmap

## V0.0.1 (current) — Claude Code only

- PreToolUse LLM monitor + tkinter alert dialog
- Local audit logs only, zero network calls beyond the LLM API

## V0.1.0 — Multi-agent support

Goal: extend the same monitor logic to other coding agents by reusing `monitor/` and `utils/`, adding only platform-specific hook adapters.

| Platform     | Hook mechanism                       | Adapter target              |
|--------------|---------------------------------------|-----------------------------|
| Cursor       | `.cursor-plugin/` + Cursor hooks API  | `.cursor-plugin/hooks.json` |
| Codex        | `.codex/` plugin spec                 | `.codex/INSTALL.md` + hooks |
| OpenCode     | `.opencode/` plugin spec              | `.opencode/INSTALL.md`      |
| Copilot CLI  | plugin marketplace command            | matches superpowers pattern |
| Gemini CLI   | `gemini-extension.json`               | extension manifest          |

Open questions to investigate before V0.1:

- Which of these platforms expose a PreToolUse-equivalent that can BLOCK a tool call (not just log)? Claude Code's `permissionDecision: "ask"` is the gold standard; others may force us to ship a less-strict variant.
- Stdin/stdout schemas differ — wrap them behind a `HookEvent` adapter.
