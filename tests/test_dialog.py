"""Static and import tests for the alert dialog (no GUI)."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DIALOG = REPO_ROOT / "monitor" / "alert_dialog.py"


def test_dialog_file_exists():
    assert DIALOG.exists()


def test_dialog_no_legacy_variant_imports():
    """No references to deleted alert_dialog variants from the research seed."""
    src = DIALOG.read_text()
    for forbidden in (
        "alert_dialog_v1",
        "alert_dialog_v2",
        "alert_dialog_tkinter",
        "alter_dialog_swift",
        "mock_monitor_",
    ):
        assert forbidden not in src, f"forbidden reference: {forbidden}"


def test_dialog_compiles():
    """Python syntax check."""
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(DIALOG)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
