"""Tests for the log path layout defined in spec §4."""

import json


def test_session_log_dir_under_cwd(isolated_cwd):
    """Log directory must be <cwd>/logs/safety_monitor/ (no per-session subdir)."""
    from utils.logging import get_session_log_dir

    session_id = "1a2b3c4d-5e6f-7890-abcd-ef0123456789"
    log_dir = get_session_log_dir(conversation_id=session_id)

    assert log_dir == isolated_cwd / "logs" / "safety_monitor"
    assert log_dir.exists()


def test_log_dir_writes_gitignore(isolated_cwd):
    """First-run creates logs/safety_monitor/.gitignore with '*'."""
    from utils.logging import get_session_log_dir

    get_session_log_dir(conversation_id="anysession")
    gitignore = isolated_cwd / "logs" / "safety_monitor" / ".gitignore"
    assert gitignore.read_text().strip() == "*"


def test_hook_logger_filename(isolated_cwd):
    """Log file name is monitor_<session8>.log."""
    from utils.logging import setup_hook_logger

    session_id = "1a2b3c4d-5e6f-7890-abcd-ef0123456789"
    logger = setup_hook_logger(log_name="llm_monitor", conversation_id=session_id)
    logger.info("test")
    for h in logger.handlers:
        h.flush()

    expected = isolated_cwd / "logs" / "safety_monitor" / "monitor_1a2b3c4d.log"
    assert expected.exists()


def test_append_usage_record_jsonl(isolated_cwd):
    """append_usage_record() appends one JSON line per call."""
    from monitor.llm_monitor import append_usage_record

    session_id = "abcdef01-1234-5678-9abc-def012345678"
    append_usage_record(
        session_id=session_id,
        tool="Bash",
        usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        duration_ms=500.0,
        suspicion=42,
    )
    append_usage_record(
        session_id=session_id,
        tool="Edit",
        usage={"prompt_tokens": 200, "completion_tokens": 30, "total_tokens": 230},
        duration_ms=700.0,
        suspicion=10,
    )

    path = (
        isolated_cwd / "logs" / "safety_monitor" / f"monitor_usage_{session_id}.jsonl"
    )
    lines = path.read_text().splitlines()
    assert len(lines) == 2

    record0 = json.loads(lines[0])
    record1 = json.loads(lines[1])
    assert record0["tool"] == "Bash"
    assert record0["total_tokens"] == 120
    assert record0["suspicion"] == 42
    assert record1["tool"] == "Edit"


def test_append_usage_record_caps_size_at_4kb(isolated_cwd):
    """Per spec §4.4, records are capped at 4096 bytes."""
    from monitor.llm_monitor import append_usage_record

    session_id = "size0001-1111-2222-3333-444444444444"
    append_usage_record(
        session_id=session_id,
        tool="Bash" * 2000,  # forces a giant line
        usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        duration_ms=1.0,
        suspicion=0,
    )
    path = (
        isolated_cwd / "logs" / "safety_monitor" / f"monitor_usage_{session_id}.jsonl"
    )
    line = path.read_text().splitlines()[0]
    assert len(line.encode("utf-8")) <= 4096
    record = json.loads(line)
    assert "TRUNCATED" in record["tool"]
