r"""
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

Installing ``node_modules`` is not on its own enough. Deno also caches the npm
registry payload and the transpiled TS under ``DENO_DIR`` (default
``%LOCALAPPDATA%\deno``), and against a cold ``DENO_DIR`` the plugin's own
script-version probe takes ~26s -- past its hard 15s budget -- so it reports the
provider unavailable and the first 1080p download 403s. This script therefore runs
that same probe once at the end to fill the cache (``--skip-warm`` opts out; CI
does, since the runner's ``DENO_DIR`` is discarded and the bundle ships
``node_modules``, not ``DENO_DIR``).

Exit codes:
    0  dependencies installed (or already present); cache warm-up attempted --
       a failed warm-up is reported on stderr but is NOT fatal
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

# Run from the repo root (`uv run python scripts/setup_pot_provider.py`), so `src.*`
# already resolves; make it work regardless of the caller's cwd.
sys.path.insert(0, str(_REPO_ROOT))

from src.pot_provider import warm_deno_cache  # noqa: E402


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
    parser.add_argument(
        "--skip-warm",
        action="store_true",
        help=(
            "Skip the post-install DENO_DIR warm-up. Use in CI: the runner's Deno "
            "cache is discarded and the bundle ships node_modules, not DENO_DIR."
        ),
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

    # Resolved once, up front: the warm-up must use the same Deno the install did.
    # resolve_deno() may fall back to a Deno on PATH, in which case warm_deno_cache()'s
    # VENV_SCRIPTS_DIR default would look in the wrong place and silently no-op.
    deno = resolve_deno()

    node_modules = server_dir / "node_modules"
    if node_modules.is_dir() and not args.force:
        print(f"already installed: {node_modules}")
    else:
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
        if proc.returncode != 0:
            return proc.returncode

    if args.skip_warm:
        print("skipping DENO_DIR warm-up (--skip-warm)")
        return 0

    print("warming Deno module cache (first run pulls ~63 MB; later runs are ~2s)...")
    # deno is None only on the already-installed path; warm_deno_cache then falls back
    # to VENV_SCRIPTS_DIR and reports a non-fatal "deno.exe not found".
    scripts_dir = Path(deno).parent if deno is not None else None
    warm = warm_deno_cache(server_home=server_dir, scripts_dir=scripts_dir)
    if warm.ok:
        print(f"deno cache warm ({warm.elapsed_s:.1f}s)")
    else:
        # Not fatal: node_modules is installed, so downloads work once Deno's cache
        # fills on its own. Only the FIRST 1080p probe risks the plugin's 15s timeout.
        print(
            f"warning: deno cache warm-up did not complete ({warm.detail}). "
            "The first 1080p download may fail with HTTP 403; retry it.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
