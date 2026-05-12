"""File I/O helpers for JSONL transcripts and JSON extraction."""

import json
import re
from pathlib import Path
from typing import Optional, Union


def read_jsonl(file_path: Union[str, Path], limit: Optional[int] = None) -> list[dict]:
    """Read records from a JSONL file. Returns [] if the file is missing."""
    if not file_path:
        return []

    records: list[dict] = []
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            for line_num, raw_line in enumerate(handle, start=1):
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    records.append(json.loads(stripped))
                except json.JSONDecodeError as exc:
                    raise json.JSONDecodeError(
                        f"Invalid JSON on line {line_num}: {exc.msg}",
                        exc.doc,
                        exc.pos,
                    ) from exc
    except FileNotFoundError:
        return []

    if limit:
        return records[-limit:]
    return records


def read_transcript(
    transcript_path: Union[str, Path], limit: Optional[int] = None
) -> list[dict]:
    """Read events from a `.jsonl` or `.json` transcript file."""
    if not transcript_path:
        return []
    path = Path(transcript_path)
    if path.suffix == ".json":
        return _read_conversation_json(path=path, limit=limit)
    return read_jsonl(file_path=path, limit=limit)


def _read_conversation_json(path: Path, limit: Optional[int] = None) -> list[dict]:
    """Read events from a `{"events": {"0": {...}, "1": {...}}}` shaped file."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return []

    events_by_id: dict = payload.get("events", {})
    events = sorted(events_by_id.values(), key=lambda ev: int(ev.get("id", 0)))
    if limit:
        return events[-limit:]
    return events


def save_jsonl(file_path: Union[str, Path], records: list[dict]) -> None:
    """Write records to a JSONL file (overwrite).

    Args:
        file_path: Path to the output file
        records: List of dictionaries to write
    """
    with open(file_path, "w", encoding="utf-8", errors="backslashreplace") as f:
        for record in records:
            f.write(json.dumps(record, default=str, ensure_ascii=True) + "\n")


def extract_json_from_response(response_text: str) -> Optional[dict]:
    """Extract JSON from an LLM response.

    Tries markdown code fence, then raw JSON, then brace-matched extraction.
    """
    fence_match = re.search(
        r"```json\s*(.*?)\s*```", response_text, re.DOTALL | re.IGNORECASE
    )
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    return _extract_brace_balanced(response_text)


def _extract_brace_balanced(text: str) -> Optional[dict]:
    """Find the first brace-balanced JSON object in text.

    Tracks brace depth while skipping braces inside JSON string literals.
    """
    start = text.find("{")
    while start != -1:
        brace_depth = 0
        is_in_string = False
        should_escape_next = False

        for index in range(start, len(text)):
            current_char = text[index]

            if should_escape_next:
                should_escape_next = False
                continue

            if current_char == "\\":
                if is_in_string:
                    should_escape_next = True
                continue

            if current_char == '"':
                is_in_string = not is_in_string
                continue

            if is_in_string:
                continue

            if current_char == "{":
                brace_depth += 1
            elif current_char == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    candidate = text[start : index + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break

        start = text.find("{", start + 1)

    return None
