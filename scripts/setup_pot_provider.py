"""
Install the vendored bgutil PO-token provider's script dependencies via Deno.

YouTube gates 1080p+ media behind a per-video GVS PO token (yt-dlp #12482). The
token is minted by the bgutil-ytdlp-pot-provider plugin running in "script-deno"
mode against the vendored server source under ``vendor/bgutil-pot-provider/server``.
That source ships without its ``node_modules`` (generated, not committed), so a
fresh checkout must run this once after ``uv sync`` to populate it:

    uv run python scripts/setup_pot_provider.py

Re-running is idempotent: it skips when ``node_modules`` already exists unless
``--force`` is passed. The install command mirrors the upstream project's own
``deno install --allow-scripts=npm:canvas --frozen`` (see the youtube-403 playbook).

Exit codes:
    0  dependencies installed (or already present)
    2  Deno runtime or vendored server dir could not be located
    other  the underlying ``deno install`` return code
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# vendor/bgutil-pot-provider/server, relative to this script (scripts/..).
_REPO_ROOT = Path(__file__).resolve().parent.parent
_VENDOR_SERVER_DIR = _REPO_ROOT / "vendor" / "bgutil-pot-provider" / "server"
_VENV_DENO = _REPO_ROOT / ".venv" / "Scripts" / "deno.exe"


def resolve_server_dir() -> Path:
    """Return the vendored bgutil server directory (``vendor/.../server``)."""
    return _VENDOR_SERVER_DIR


def resolve_deno() -> str | None:
    """
    Locate the Deno executable.

    Prefers the repo-local ``.venv/Scripts/deno.exe`` (the pinned runtime), then
    falls back to a ``deno`` on ``PATH``. Returns the resolved path, or ``None``
    when no Deno can be found.
    """
    if _VENV_DENO.is_file():
        return str(_VENV_DENO)
    return shutil.which("deno")


def build_deno_install_cmd(deno: str) -> list[str]:
    """Return the ``deno install`` argv for the vendored server (kept for testing)."""
    return [deno, "install", "--allow-scripts=npm:canvas", "--frozen"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Install the vendored bgutil PO-token provider's Deno dependencies "
            "(node_modules) so YouTube 1080p downloads can mint their GVS PO token."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run deno install even if node_modules already exists.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    server_dir = resolve_server_dir()
    if not server_dir.is_dir():
        print(
            f"error: vendored server dir not found: {server_dir}",
            file=sys.stderr,
        )
        return 2

    node_modules = server_dir / "node_modules"
    if node_modules.is_dir() and not args.force:
        print(f"already installed: {node_modules}")
        return 0

    deno = resolve_deno()
    if deno is None:
        print(
            "error: could not locate Deno. Expected .venv/Scripts/deno.exe or a "
            "'deno' on PATH. Run 'uv sync' first.",
            file=sys.stderr,
        )
        return 2

    cmd = build_deno_install_cmd(deno)
    print(f"running: {' '.join(cmd)} (cwd={server_dir})")
    proc = subprocess.run(cmd, cwd=server_dir, check=False)  # noqa: S603
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
