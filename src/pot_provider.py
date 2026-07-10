"""
Resolve and health-check the bgutil PO-token provider (script-deno mode).

YouTube gates 1080p+ media behind a per-video GVS PO token (yt-dlp #12482). That
token is minted by the bgutil-ytdlp-pot-provider plugin running in "script" mode
via the bundled Deno runtime. If the plugin, the Deno runtime, or the generate
script/deps are missing, every 1080p download 403s at the media stage. This module
reports whether the provider is fully wired so startup can warn instead of failing
silently. It mirrors the requirements of
yt_dlp_plugins.extractor.getpot_bgutil_script.BgUtilScriptDenoPTP.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import POT_PROVIDER_SERVER_HOME, VENV_SCRIPTS_DIR

# Mirror BgUtilScriptDenoPTP: script at {server_home}/src/generate_once.ts, deps
# under {server_home}/node_modules, Deno >= 2.0.0.
_SCRIPT_RELPATH: tuple[str, ...] = ("src", "generate_once.ts")
_NODE_MODULES = "node_modules"
_DENO_MIN_VERSION = (2, 0, 0)
_DENO_VERSION_TIMEOUT_S = 5.0
_DENO_VERSION_RE = re.compile(r"deno\s+(\d+)\.(\d+)\.(\d+)")


@dataclass(frozen=True)
class PotProviderStatus:
    """Per-component availability of the script-deno PO-token provider."""

    plugin_installed: bool
    deno_ok: bool
    script_found: bool
    node_modules_found: bool

    @property
    def ok(self) -> bool:
        return (
            self.plugin_installed
            and self.deno_ok
            and self.script_found
            and self.node_modules_found
        )

    def summary(self) -> str:
        """Comma-joined names of missing pieces; empty string when ``ok``."""
        if self.ok:
            return ""
        missing: list[str] = []
        if not self.plugin_installed:
            missing.append("provider plugin (bgutil-ytdlp-pot-provider)")
        if not self.deno_ok:
            missing.append("Deno runtime (>= 2.0)")
        if not self.script_found:
            missing.append("generate_once.ts script")
        if not self.node_modules_found:
            missing.append("script dependencies (node_modules)")
        return ", ".join(missing)


def _plugin_importable() -> bool:
    """Return True if the bgutil script provider plugin imports (i.e. not pruned)."""
    try:
        return (
            importlib.util.find_spec(
                "yt_dlp_plugins.extractor.getpot_bgutil_script",
            )
            is not None
        )
    except (ImportError, ValueError):
        return False


def _deno_ok(scripts_dir: Path) -> bool:
    """Return True if deno.exe exists in ``scripts_dir`` and reports version >= 2.0.0."""
    deno = scripts_dir / "deno.exe"
    if not deno.is_file():
        return False
    try:
        proc = subprocess.run(  # noqa: S603
            [str(deno), "--version"],
            capture_output=True,
            text=True,
            timeout=_DENO_VERSION_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode != 0:
        return False
    m = _DENO_VERSION_RE.search(proc.stdout or "")
    if not m:
        return False
    return tuple(int(g) for g in m.groups()) >= _DENO_MIN_VERSION


def check_pot_provider(
    server_home: Path | None = None,
    scripts_dir: Path | None = None,
) -> PotProviderStatus:
    """
    Probe every component the script-deno provider needs.

    Args:
        server_home: Provider server root; defaults to ``POT_PROVIDER_SERVER_HOME``.
        scripts_dir: Dir holding ``deno.exe``; defaults to ``VENV_SCRIPTS_DIR``.

    Returns:
        A ``PotProviderStatus`` snapshot.
    """
    home = Path(server_home) if server_home is not None else POT_PROVIDER_SERVER_HOME
    scripts = Path(scripts_dir) if scripts_dir is not None else VENV_SCRIPTS_DIR
    return PotProviderStatus(
        plugin_installed=_plugin_importable(),
        deno_ok=_deno_ok(scripts),
        script_found=home.joinpath(*_SCRIPT_RELPATH).is_file(),
        node_modules_found=(home / _NODE_MODULES).is_dir(),
    )
