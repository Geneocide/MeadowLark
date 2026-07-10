"""
Report whether MeadowLark's yt-dlp pin can move back to the stable channel.

MeadowLark is temporarily pinned to a yt-dlp *nightly* via ``[tool.uv.sources]``
in ``pyproject.toml`` (see yt-dlp #14680 -- the stable channel lacked the YouTube
HTTP 403 media-download fix at pin time). Nightly versions always sort higher
than the latest stable and a fresh nightly ships daily, so a plain ``>=``
constraint can never fall back to stable on its own. This script answers the one
question that actually decides the switch: is the latest *stable* on PyPI now
newer than the pinned nightly?

  * Yes -> prints the exact two-step revert (delete the ``[tool.uv.sources]``
           block, then ``uv lock --upgrade-package yt-dlp && uv sync``).
  * No  -> reports the pinned nightly is still ahead; nothing to do.

Run from anywhere in the repo:
    uv run python scripts/yt_dlp_channel.py

Exit codes:
    0  a newer stable is available -- revert is recommended
    1  pinned nightly is still ahead of the latest stable -- nothing to do
    2  error (could not read the pin or reach PyPI)
    3  no nightly pin found -- already tracking stable
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from packaging.version import InvalidVersion, Version

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
PYPI_URL = "https://pypi.org/pypi/yt-dlp/json"
_PIN_RE = re.compile(r"yt-dlp-nightly-builds/releases/download/([^/]+)/")


def read_pinned_nightly(pyproject: Path) -> str | None:
    """Return the pinned nightly version from pyproject.toml, or None if absent."""
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"error: cannot read {pyproject}: {exc}"
        raise SystemExit(msg) from exc
    match = _PIN_RE.search(text)
    return match.group(1) if match else None


def fetch_latest_stable(url: str = PYPI_URL) -> str:
    """Return the latest stable yt-dlp version reported by PyPI."""
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310 (literal https)
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        msg = f"error: could not query PyPI: {exc}"
        raise SystemExit(msg) from exc
    version = data.get("info", {}).get("version")
    if not version:
        raise SystemExit("error: PyPI response missing info.version")
    return str(version)


def main() -> int:
    pinned = read_pinned_nightly(PYPROJECT)
    if pinned is None:
        print("No [tool.uv.sources] nightly pin found -- already tracking stable.")
        return 3

    stable = fetch_latest_stable()
    try:
        pinned_v, stable_v = Version(pinned), Version(stable)
    except InvalidVersion as exc:
        msg = f"error: unparseable version ({exc})"
        raise SystemExit(msg) from exc

    print(f"pinned nightly : {pinned}")
    print(f"latest stable  : {stable}")

    if stable_v > pinned_v:
        print(
            f"\n-> Stable {stable} is now newer than the pinned nightly. Revert:\n"
            "   1. Delete the [tool.uv.sources] block in pyproject.toml.\n"
            "   2. uv lock --upgrade-package yt-dlp && uv sync",
        )
        return 0

    print("\n-> Latest stable is not yet newer than the pin; staying on nightly.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
