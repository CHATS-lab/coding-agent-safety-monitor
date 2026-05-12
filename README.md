# Safety Monitor

A Claude Code plugin that monitor your coding agent. Before it actually runs a command or edits a file, the monitor reads the conversation so far, asks a separate LLM whether the next move looks malicious or off-task, and if it does, pops up a desktop dialog so you can decide.

## How it works

The plugin hooks `PreToolUse`. On every tool call the agent is about to make, the monitor reads the session transcript, and ships it off to an LLM monitor with one question: how suspicious is this, on a scale of 0 to 100.

If the score is at or below 80, the hook returns silently and the agent's tool call goes through as if the monitor weren't there. The agent never finds out it was watched.

If the score is above 80, the hook prints a `permissionDecision: "ask"` back to Claude Code — which surfaces its built-in permission prompt — and at the same time launches a pop-up dialog explaining what the LLM thought was off. You read both, then approve or reject in the Claude Code panel.

## Installation

You need [`uv`](https://docs.astral.sh/uv/). One-time:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then in Claude Code:

```text
/plugin marketplace add CHATS-lab/coding-agent-safety-monitor
/plugin install safety-monitor@safety-monitor
```

If you'd rather not add a marketplace, clone and install from the local path:

```bash
git clone https://github.com/CHATS-lab/coding-agent-safety-monitor.git
# In Claude Code:
/plugin install ./safety-monitor
```

There's no `pip install` step. uv builds an isolated virtualenv the first time the hook fires and caches it for the rest of the session.

## Configuration

Set `ANTHROPIC_API_KEY` in `~/.env` or your shell. That's the only thing you have to set. The rest defaults to something sensible:

```
MONITOR_ENABLED=true                # master switch
MONITOR_MODEL=claude-haiku-4-5      # any model litellm understands
MONITOR_THRESHOLD=80                # popup when suspicion > this
```

The full list of knobs is in `.env.example`. If you're going to cite this in a paper, pin a dated model id like `claude-haiku-4-5-20251001` so the reviewer can reproduce your numbers.

## Logs

Two files per session, under `<cwd>/logs/safety_monitor/`:

- `monitor_<session8>.log` — what happened, in plain text
- `monitor_usage_<session>.jsonl` — token counts and durations, one record per LLM call

Nothing else leaves your machine.

## Citing

```
@misc{safety-monitor-2026,
  author = {Ye, Jingheng},
  title  = {Safety Monitor: An LLM-Based Monitor for Coding Agents},
  year   = {2026},
  url    = {https://github.com/CHATS-lab/coding-agent-safety-monitor}
}
```

## License

MIT License - see LICENSE file for details.
