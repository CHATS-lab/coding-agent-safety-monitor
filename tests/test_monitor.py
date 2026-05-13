"""Behavioral tests for monitor/llm_monitor.py."""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MONITOR_SCRIPT = REPO_ROOT / "monitor" / "llm_monitor.py"


def _run_monitor(
    event: dict, cwd: Path, env_extra: dict | None = None
) -> subprocess.CompletedProcess:
    """Invoke llm_monitor.py with the given event JSON on stdin."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"),
        "HOME": os.environ.get("HOME", str(REPO_ROOT.parent)),
    }
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(MONITOR_SCRIPT)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd),
        timeout=20,
    )


def test_skip_tool_returns_empty_json_and_exits_zero(tmp_path):
    """Read is in MONITOR_SKIP_TOOLS, must return {} with exit 0."""
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text("")
    event = {
        "session_id": "test-skip",
        "transcript_path": str(transcript),
        "tool_name": "Read",
        "tool_input": {"file_path": "/etc/passwd"},
        "cwd": str(tmp_path),
    }
    result = _run_monitor(event, cwd=tmp_path, env_extra={"MONITOR_ENABLED": "true"})
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "{}"


def test_disabled_monitor_exits_zero(tmp_path):
    """MONITOR_ENABLED=false short-circuits."""
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text("")
    event = {
        "session_id": "test-disabled",
        "transcript_path": str(transcript),
        "tool_name": "Bash",
        "tool_input": {"command": "rm -rf /"},
        "cwd": str(tmp_path),
    }
    result = _run_monitor(event, cwd=tmp_path, env_extra={"MONITOR_ENABLED": "false"})
    assert result.returncode == 0


def test_monitor_invalid_stdin_fails_open(tmp_path):
    """Invalid JSON on stdin must still print {} and exit 0, with no stderr leak."""
    proc = subprocess.run(
        [sys.executable, str(MONITOR_SCRIPT)],
        input="not-valid-json{",
        capture_output=True,
        text=True,
        env={
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"),
            "HOME": os.environ.get("HOME", str(REPO_ROOT.parent)),
            "MONITOR_ENABLED": "true",
        },
        cwd=str(tmp_path),
        timeout=20,
    )
    assert proc.returncode == 0, f"stderr={proc.stderr}"
    assert proc.stdout.strip().startswith("{")
    assert proc.stderr == "", f"stderr leaked: {proc.stderr!r}"


def test_hook_output_never_sets_additional_context():
    """Static check: source must not reference 'additionalContext'."""
    src = MONITOR_SCRIPT.read_text()
    assert "additionalContext" not in src, (
        "Per spec §1.1, the monitor must never set additionalContext "
        "(would inject into the agent's context)."
    )


def test_pep723_inline_deps_declared():
    """PEP 723 header must list runtime deps so `uv run --script` works."""
    src = MONITOR_SCRIPT.read_text()
    assert "# /// script" in src, "PEP 723 block missing"
    assert 'requires-python = ">=3.10"' in src
    for dep in ("litellm", "jinja2", "python-dotenv"):
        assert dep in src, f"PEP 723 block missing dep: {dep}"


def test_missing_dep_path_emits_system_message():
    """Source must wrap top-level imports in try/except that emits a systemMessage.

    This guarantees that if the runtime can't load litellm/jinja2/python-dotenv,
    the user sees a banner in Claude Code instead of a silent failure.
    """
    src = MONITOR_SCRIPT.read_text()
    assert "_emit_setup_banner" in src, "missing banner helper"
    assert "systemMessage" in src, "banner must emit systemMessage field"
    # The helper must be called from the import error path
    assert "except ImportError" in src and "_emit_setup_banner(" in src


def test_llm_failure_triggers_permission_prompt(tmp_path):
    """When the LLM call fails (auth, rate limit, network), the hook must
    emit `permissionDecision: "ask"` so Claude Code's native permission
    prompt appears. A `systemMessage`-only banner is too easy to miss,
    so we fail-ASK instead of fail-open.

    Drives the failure path by setting an obviously-invalid API key.
    """
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text('{"type":"user","message":{"content":"deploy"}}\n')
    event = {
        "session_id": "test-llm-fail",
        "transcript_path": str(transcript),
        "tool_name": "Bash",
        "tool_input": {"command": "ls"},
        "cwd": str(tmp_path),
    }
    proc = subprocess.run(
        [sys.executable, str(MONITOR_SCRIPT)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env={
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"),
            "HOME": os.environ.get("HOME", str(REPO_ROOT.parent)),
            "MONITOR_ENABLED": "true",
            "ANTHROPIC_API_KEY": "deliberately-invalid-for-test",
        },
        cwd=str(tmp_path),
        timeout=30,
    )
    assert proc.returncode == 0, f"stderr={proc.stderr}"
    out = json.loads(proc.stdout.strip())
    hso = out.get("hookSpecificOutput", {})
    assert hso.get("hookEventName") == "PreToolUse"
    assert hso.get("permissionDecision") == "ask", (
        f"expected ask, got {hso.get('permissionDecision')} — full output: {out}"
    )
    assert "Safety monitor unavailable" in hso.get("permissionDecisionReason", "")
    assert "systemMessage" in out
    # additionalContext must never leak into agent's context
    assert "additionalContext" not in hso
