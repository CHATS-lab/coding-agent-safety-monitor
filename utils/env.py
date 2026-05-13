"""Environment variable loading and plugin path resolution."""

import os
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_PLUGIN_ROOT: Path = Path(__file__).parent.parent.absolute()
DEFAULT_PROJECT_ROOT: Path = DEFAULT_PLUGIN_ROOT.parent
PROJECT_ROOT: Path = DEFAULT_PROJECT_ROOT
DEFAULT_DOTENV_PATH: Path = DEFAULT_PROJECT_ROOT / ".env"


def get_plugin_root() -> Path:
    """Return the plugin root, preferring CLAUDE_PLUGIN_ROOT when set."""
    if "CLAUDE_PLUGIN_ROOT" in os.environ:
        return Path(os.environ["CLAUDE_PLUGIN_ROOT"])
    return DEFAULT_PLUGIN_ROOT


def get_bool_env(name: str, default: bool) -> bool:
    """Read a boolean env var. True iff value lowercases to 'true'."""
    return os.environ.get(name, str(default)).lower() == "true"


def get_int_env(name: str, default: int) -> int:
    """Read an int env var. Falls back to default if missing or non-numeric."""
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def load_env_file() -> None:
    """Load env vars from the first `.env` found in standard user locations.

    Priority (highest wins; shell env always wins overall):
      1. <cwd>/.env             — per-project override
      2. ~/.claude/.env         — Claude Code config dir (recommended)
      3. ~/.env                 — user-global
      4. ${CLAUDE_PLUGIN_ROOT}/.env — plugin-bundled fallback

    All four are merged with `override=False` so the first one that
    defines a key wins; later files only fill in missing keys.
    """
    plugin_root = get_plugin_root()
    search_paths = [
        Path.cwd() / ".env",
        Path.home() / ".claude" / ".env",
        Path.home() / ".env",
        plugin_root / ".env",
    ]
    for candidate in search_paths:
        if candidate.exists():
            load_dotenv(dotenv_path=candidate, override=False)
