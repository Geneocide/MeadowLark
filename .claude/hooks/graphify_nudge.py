# ruff: noqa: INP001
"""
PreToolUse hook: nudge toward the graphify knowledge graph, rate-limited per session.

Fires for Bash search commands (grep/rg/find/…) and Read/Glob/Grep on source or doc
files. Emits the nudge on the first hit of a session and every NUDGE_EVERY hits after,
instead of on every call, so long implementation runs don't pay ~80 tokens per file read.
"""

from __future__ import annotations

import contextlib
import json
import re
import sys
import tempfile
from pathlib import Path

NUDGE_EVERY = 40
SEARCH_RE = re.compile(r"\b(grep|rg|ripgrep|find|fd|ack|ag)\b")
EXTS = (
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb", ".c", ".h",
    ".cpp", ".hpp", ".cc", ".cs", ".kt", ".swift", ".php", ".scala", ".lua", ".sh",
    ".md", ".rst", ".txt", ".mdx",
)  # fmt: skip
NUDGE = (
    "graphify: knowledge graph at graphify-out/. For codebase questions run "
    '`graphify query "<question>"` (scoped subgraph, far smaller than reading files), '
    '`graphify explain "<concept>"`, or `graphify path "<A>" "<B>"` before grepping or '
    "reading source. Read raw files to modify or debug specific code, or when the graph "
    "lacks detail."
)


def relevant(payload: dict) -> bool:
    """Return True when the call is a search or a source-file read outside graphify-out/."""
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input") or {}
    if tool == "Bash":
        return bool(SEARCH_RE.search(inp.get("command", "")))
    target = " ".join(
        str(inp.get(k) or "") for k in ("file_path", "pattern", "path", "glob")
    ).lower().replace("\\", "/")
    if "graphify-out/" in target:
        return False
    if tool == "Grep":
        return True
    return any(ext in target for ext in EXTS)


def should_nudge(session_id: str) -> bool:
    """Increment the per-session counter; nudge on the 1st hit and every NUDGE_EVERY."""
    counter = Path(tempfile.gettempdir()) / f"graphify-nudge-{session_id or 'na'}"
    try:
        count = int(counter.read_text(encoding="ascii").strip() or 0)
    except (OSError, ValueError):
        count = 0
    count += 1
    with contextlib.suppress(OSError):
        counter.write_text(str(count), encoding="ascii")
    return count == 1 or count % NUDGE_EVERY == 0


def main() -> int:
    """Emit additionalContext when the graph exists and the rate limit allows."""
    if not (Path("graphify-out") / "graph.json").is_file():
        return 0
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not relevant(payload) or not should_nudge(str(payload.get("session_id", ""))):
        return 0
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": NUDGE,
                },
            },
        ),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
