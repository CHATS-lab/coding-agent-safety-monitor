#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "litellm>=1.0.0",
#     "jinja2>=3.0.0",
#     "python-dotenv>=1.0.0",
# ]
# ///
"""Security Monitor for Claude Code

Analyzes agent behavior trajectories to detect potentially malicious actions.
Runs as a PreToolUse hook — launches a non-blocking native dialog when suspicion
is high and outputs structured hookSpecificOutput JSON on stdout.

Design principles:
- Agent Opacity: the agent never perceives the monitor's existence
- Non-Blocking Notification: dialog is detached, hook returns immediately
- Consistent Alert UI: launch the packaged tkinter dialog across platforms
- Rich Context in Alerts: dialog shows risk analysis AND the proposed change

Runtime: invoked via `uv run --script` (PEP 723 inline deps above). uv creates
and caches an isolated virtualenv automatically — no manual pip install needed.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any


def _emit_setup_banner(reason: str) -> None:
    """Surface a setup problem to the user (not the agent) and exit 0.

    Uses the `systemMessage` field of the hook output — shown as a banner in
    Claude Code, never injected into the agent's context.
    """
    print(json.dumps({"systemMessage": f"⚠️ safety-monitor: {reason}"}))
    sys.exit(0)


try:
    import logging
    import shutil
    import subprocess
    import time
    import traceback

    from jinja2 import Template

    sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))
    from utils import (  # noqa: E402
        call_llm,
        count_tokens,
        extract_json_from_response,
        get_bool_env,
        get_int_env,
        get_max_input_tokens,
        get_plugin_root,
        get_session_log_dir,
        load_env_file,
        log_separator,
        read_transcript,
        setup_hook_logger,
        utc_now_iso,
    )
except ImportError as import_err:
    _emit_setup_banner(
        f"missing dependency '{import_err.name}'. "
        f"Ensure you launched via `uv run --script` (see README)."
    )

load_env_file()

MONITOR_ENABLED: bool = get_bool_env("MONITOR_ENABLED", True)
if not MONITOR_ENABLED:
    sys.exit(0)
MONITOR_THRESHOLD: int = get_int_env("MONITOR_THRESHOLD", 80)
MONITOR_MODEL: str = os.environ.get("MONITOR_MODEL", "claude-haiku-4-5")
MONITOR_PROMPT_NAME: str = os.environ.get("MONITOR_PROMPT_NAME", "monitor_prompt.j2")
MONITOR_ENABLE_THINKING: bool = get_bool_env("MONITOR_ENABLE_THINKING", False)
MONITOR_MAX_INPUT_TOKENS: int = min(
    get_int_env("MONITOR_MAX_INPUT_TOKENS", 200_000),
    get_max_input_tokens(MONITOR_MODEL),
)
# True: strip Skill events from the trajectory so neither the monitor LLM nor
# the user reading logs sees the contents of skills the agent loaded.
MONITOR_MUTE_SKILL: bool = get_bool_env("MONITOR_MUTE_SKILL", True)

THINKING_BUDGET_TOKENS = 1024
THINKING_CONFIG = (
    {"type": "enabled", "budget_tokens": THINKING_BUDGET_TOKENS}
    if MONITOR_ENABLE_THINKING
    else None
)

USAGE_FILE_TEMPLATE = "monitor_usage_{session_id}.jsonl"
# POSIX guarantees writes <= PIPE_BUF are atomic across processes.
MAX_LINE_BYTES = 4096

# Read-only, informational, or delegating tools — always allow without LLM
# analysis. Monitored mutating tools: Bash, Edit, Write, NotebookEdit.
DEFAULT_SKIP_TOOLS = (
    "Read,Glob,Grep,WebSearch,WebFetch,"
    "Agent,Skill,"
    "Task,TaskList,TaskGet,TaskCreate,TaskUpdate,TaskOutput,TaskStop,"
    "TodoWrite,AskUserQuestion,"
    "EnterPlanMode,ExitPlanMode,EnterWorktree"
)
MONITOR_SKIP_TOOLS: set[str] = {
    tool_name.strip()
    for tool_name in os.environ.get("MONITOR_SKIP_TOOLS", DEFAULT_SKIP_TOOLS).split(",")
    if tool_name.strip()
}

PLUGIN_ROOT = get_plugin_root()
PROMPT_PATH = PLUGIN_ROOT / "monitor" / "prompts" / MONITOR_PROMPT_NAME

USER_LINE_PREFIX = "USER:"


def _load_prompt_template() -> Template:
    """Load the Jinja2 template from disk. Cached via PROMPT_TEMPLATE constant."""
    try:
        with open(PROMPT_PATH, "r", encoding="utf-8") as handle:
            return Template(handle.read())
    except FileNotFoundError as missing:
        raise FileNotFoundError(
            f"Prompt template not found: {PROMPT_PATH}"
        ) from missing


# Cache once at module import — the template file doesn't change at runtime
# and the hook is the hot path (one PreToolUse per tool call).
PROMPT_TEMPLATE: Template = _load_prompt_template()


def _is_user_event(line: str) -> bool:
    """Return True if a formatted trajectory line is a USER event."""
    body = line.split("]", 1)[-1].strip() if "]" in line else line
    return body.startswith(USER_LINE_PREFIX)


def format_trajectory(events: list[dict]) -> str:
    """Format raw transcript events into one-line-per-event human-readable text.

    No per-field truncation applied — full content preserved. Overflow is
    handled later by `truncate_trajectory` only when the prompt would exceed
    the model's token budget.
    """
    lines: list[str] = []
    for index, event in enumerate(events):
        lines.extend(_format_event(index, event))
    return "\n".join(lines)


def _format_event(index: int, event: dict) -> list[str]:
    """Produce zero or more trajectory lines for a single transcript event."""
    event_type = event.get("type", "unknown")

    if event_type == "user":
        return _format_user_event(index, event)
    if event_type == "assistant":
        return _format_assistant_event(index, event)
    if event_type in ("PreToolUse", "PostToolUse", "PermissionRequest"):
        tool_name = event.get("tool_name", "unknown")
        if MONITOR_MUTE_SKILL and tool_name == "Skill":
            return []
        tool_input_json = json.dumps(event.get("tool_input", {}))
        return [f"[{index}] {event_type}: {tool_name} - {tool_input_json}"]
    return []


def _format_user_event(index: int, event: dict) -> list[str]:
    content = event.get("message", {}).get("content", "")
    if isinstance(content, str):
        return [f"[{index}] USER: {content}"]
    if isinstance(content, list):
        return [
            f"[{index}] TOOL_RESULT: {part.get('content', '')}"
            for part in content
            if isinstance(part, dict) and part.get("type") == "tool_result"
        ]
    return []


def _format_assistant_event(index: int, event: dict) -> list[str]:
    lines: list[str] = []
    for part in event.get("message", {}).get("content", []):
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text":
            lines.append(f"[{index}] ASSISTANT: {part.get('text', '')}")
        elif part.get("type") == "tool_use":
            tool_name = part.get("name", "unknown")
            if MONITOR_MUTE_SKILL and tool_name == "Skill":
                continue
            tool_input_json = json.dumps(part.get("input", {}))
            lines.append(f"[{index}] TOOL_USE: {tool_name} - {tool_input_json}")
    return lines


def truncate_trajectory(trajectory: str, max_tokens: int) -> str:
    """Truncate `trajectory` to fit within `max_tokens`.

    Drops non-USER lines from the oldest first; if USER lines alone still
    exceed the budget, drops them from the oldest forward too.
    """
    if count_tokens(trajectory, MONITOR_MODEL) <= max_tokens:
        return trajectory

    lines = trajectory.split("\n")
    keep = [True] * len(lines)

    for line_idx, line in enumerate(lines):
        if _is_user_event(line):
            continue
        keep[line_idx] = False
        remaining = "\n".join(lines[i] for i in range(len(lines)) if keep[i])
        if count_tokens(remaining, MONITOR_MODEL) <= max_tokens:
            return remaining

    remaining_lines = [lines[i] for i in range(len(lines)) if keep[i]]
    while (
        remaining_lines
        and count_tokens("\n".join(remaining_lines), MONITOR_MODEL) > max_tokens
    ):
        remaining_lines.pop(0)
    return "\n".join(remaining_lines)


def count_trajectory_events(trajectory: str) -> int:
    """Count the number of event lines in a formatted trajectory.

    Args:
        trajectory: Formatted trajectory string

    Returns:
        Number of event lines
    """
    if not trajectory:
        return 0
    return sum(1 for line in trajectory.split("\n") if line.strip())


def render_prompt(
    trajectory: str, session_id: str, cwd: str, tool_name: str, tool_params: str
) -> str:
    """Render the cached prompt template, trimming the trajectory if it exceeds
    `MONITOR_MAX_INPUT_TOKENS`.

    When the rendered prompt is over budget, we compute the prompt-minus-trajectory
    overhead once and pass the leftover budget to `truncate_trajectory`.
    """

    def _render(traj: str) -> str:
        return PROMPT_TEMPLATE.render(
            session_id=session_id,
            cwd=cwd,
            timestamp=utc_now_iso(),
            trajectory_event_count=count_trajectory_events(traj),
            trajectory=traj,
            tool_name=tool_name,
            tool_params=tool_params,
        )

    prompt = _render(trajectory)
    if MONITOR_MAX_INPUT_TOKENS <= 0:
        return prompt

    prompt_tokens = count_tokens(prompt, MONITOR_MODEL)
    if prompt_tokens <= MONITOR_MAX_INPUT_TOKENS:
        return prompt

    overhead = prompt_tokens - count_tokens(trajectory, MONITOR_MODEL)
    trajectory_budget = max(0, MONITOR_MAX_INPUT_TOKENS - overhead)
    return _render(truncate_trajectory(trajectory, trajectory_budget))


def _build_error_result(reason: str, suspicion: int = 0) -> dict:
    """Build a fallback analysis dict to use when the LLM call fails."""
    return {
        "error": reason,
        "reasoning": f"Monitor error: {reason}",
        "issue_type": "none",
        "issue": None,
        "suspicion": suspicion,
    }


def parse_suspicion(raw_value: Any) -> int:
    """Coerce an LLM-returned suspicion value to an int clamped to [0, 100]."""
    try:
        score = int(float(raw_value))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, score))


def analyze_with_llm(prompt: str) -> dict:
    """Call the monitor LLM and return an analysis dict with a `usage` key."""
    response = call_llm(prompt, model=MONITOR_MODEL, thinking=THINKING_CONFIG)
    usage = response.get("usage", {})

    if response.get("error"):
        analysis = _build_error_result(reason=response["error"])
        analysis["usage"] = usage
        return analysis

    response_text = response.get("text", "")
    if not response_text:
        analysis = _build_error_result(reason="Empty response from LLM")
        analysis["usage"] = usage
        return analysis

    analysis = extract_json_from_response(response_text)
    if analysis:
        analysis["suspicion"] = parse_suspicion(analysis.get("suspicion"))
        analysis["usage"] = usage
        return analysis

    analysis = _build_error_result(reason="Failed to parse LLM response", suspicion=50)
    analysis["usage"] = usage
    return analysis


def append_usage_record(
    session_id: str, tool: str, usage: dict, duration_ms: float, suspicion: int
) -> None:
    """Append one JSON record per LLM call to monitor_usage_<session>.jsonl.

    Opens with O_APPEND and writes the full line in a single os.write() call so
    concurrent PreToolUse hooks don't interleave. Records are truncated to fit
    within MAX_LINE_BYTES (POSIX PIPE_BUF) to keep atomicity guarantees.
    """
    log_dir = get_session_log_dir(conversation_id=session_id)
    path = log_dir / USAGE_FILE_TEMPLATE.format(session_id=session_id)

    record = {
        "ts": utc_now_iso(),
        "tool": tool,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "duration_ms": round(duration_ms, 1),
        "suspicion": suspicion,
    }
    line = (json.dumps(record, ensure_ascii=True) + "\n").encode("utf-8")
    if len(line) > MAX_LINE_BYTES:
        overhead = len(line) - len(record["tool"].encode("utf-8"))
        budget = max(0, MAX_LINE_BYTES - overhead - len("...TRUNCATED"))
        record["tool"] = record["tool"][:budget] + "...TRUNCATED"
        line = (json.dumps(record, ensure_ascii=True) + "\n").encode("utf-8")

    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


DIALOG_ACTION_LINE = (
    "Review this monitor warning carefully, "
    "then approve or reject the pending action in Claude Code."
)
DIALOG_SEVERITY = "Critical"


def launch_alert_dialog(title: str, message: str, logger: logging.Logger) -> None:
    """Launch the tkinter alert dialog in a detached process. Returns immediately."""
    if os.name != "nt" and not _has_graphical_display():
        logger.warning("launch_alert_dialog: no graphical display available")
        return

    dialog_script = Path(__file__).parent / "alert_dialog.py"
    if not dialog_script.exists():
        logger.warning("launch_alert_dialog: missing dialog script: %s", dialog_script)
        return

    python_path = (
        shutil.which("python3") or shutil.which("python") or shutil.which("py")
    )
    if not python_path:
        logger.warning("launch_alert_dialog: no Python interpreter on PATH")
        return

    command = [python_path]
    if Path(python_path).name.lower() == "py":
        command.append("-3")
    command.extend(
        [str(dialog_script), DIALOG_SEVERITY, title, message, DIALOG_ACTION_LINE]
    )

    popen_kwargs: dict[str, object] = {
        "start_new_session": True,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    subprocess.Popen(command, **popen_kwargs)
    logger.info("launch_alert_dialog: launched %s", dialog_script.name)


def _has_graphical_display() -> bool:
    """Return whether the current environment can show a desktop dialog."""
    if sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def main() -> None:
    """PreToolUse hook entry point."""
    try:
        hook_event = json.load(sys.stdin)
        session_id: str = hook_event.get("session_id", "unknown")
        transcript_path: str = hook_event.get("transcript_path")
        tool_name: str = hook_event.get("tool_name", "unknown")
        tool_input: dict = hook_event.get("tool_input", {})
        cwd: str = hook_event.get("cwd", "")

        logger = setup_hook_logger(
            log_name="llm_monitor", conversation_id=session_id, level=logging.INFO
        )

        if tool_name in MONITOR_SKIP_TOOLS:
            logger.info("Skipped (benign tool): %s", tool_name)
            print("{}")
            return

        start_time = time.monotonic()
        log_separator(logger=logger)
        logger.info("Security Monitor Hook Started")
        logger.info("Session: %s | Tool: %s", session_id, tool_name)
        logger.info("Tool input: %s", json.dumps(tool_input, indent=2, default=str))

        events = read_transcript(transcript_path)
        trajectory = format_trajectory(events)
        logger.debug(
            "─── Trajectory (%d events) ───", count_trajectory_events(trajectory)
        )
        logger.debug("%s", trajectory)
        logger.debug("─── End Trajectory ───")

        tool_params_str = json.dumps(tool_input, indent=2)
        prompt = render_prompt(
            trajectory=trajectory,
            session_id=session_id,
            cwd=cwd,
            tool_name=tool_name,
            tool_params=tool_params_str,
        )
        logger.info(
            "Prompt: %d chars, %d tokens (limit: %d tokens)",
            len(prompt),
            count_tokens(prompt, MONITOR_MODEL),
            MONITOR_MAX_INPUT_TOKENS,
        )

        analysis = analyze_with_llm(prompt)
        duration_ms = (time.monotonic() - start_time) * 1000

        usage = analysis.pop("usage", {})
        suspicion: int = int(analysis.get("suspicion", 0))
        if usage:
            append_usage_record(
                session_id=session_id,
                tool=tool_name,
                usage=usage,
                duration_ms=duration_ms,
                suspicion=suspicion,
            )
            logger.info("LLM call usage: %s", json.dumps(usage))
        logger.info("Monitor duration: %.0fms", duration_ms)

        issue_type: str = analysis.get("issue_type") or "unknown"
        issue: str = analysis.get("issue") or "No specific issue"

        logger.info("Monitor result: %s", json.dumps(analysis, default=str))

        if suspicion > MONITOR_THRESHOLD:
            alert_summary = f"{issue_type}: {issue}"
            launch_alert_dialog(issue_type, issue, logger)
            decision_reason = f"Security Monitor ({suspicion}/100): {alert_summary}"
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "ask",
                            "permissionDecisionReason": decision_reason,
                        },
                        "systemMessage": f"🚨 {decision_reason}",
                    }
                )
            )
        else:
            print("{}")

        logger.info("Security Monitor Hook Completed (suspicion=%d)", suspicion)
        log_separator(logger=logger)

    except Exception as exc:
        # Fail-open: stdout empty JSON, exit 0, never write to stderr.
        # Exit 2 + stderr is fed to the agent as a blocking error per the
        # Claude Code hook spec — would violate agent-opacity AND fail-open.
        print("{}")
        try:
            error_dir = Path.cwd() / "logs" / "safety_monitor"
            error_dir.mkdir(parents=True, exist_ok=True)
            with open(
                error_dir / "monitor_errors.log", "a", encoding="utf-8"
            ) as handle:
                handle.write(
                    f"{utc_now_iso()} | {type(exc).__name__}: {exc}\n"
                    f"{traceback.format_exc()}\n"
                )
        except Exception:
            pass
        sys.exit(0)


if __name__ == "__main__":
    main()
