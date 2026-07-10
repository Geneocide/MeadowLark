"""
Boundary tests for the bgutil PO-token provider healthcheck.

Coverage map
============
src.pot_provider.check_pot_provider
    - all components present               -> ok is True, summary() == ""
    - missing generate_once.ts             -> not ok, summary names the script
    - missing node_modules                 -> not ok, summary names node_modules
    - provider plugin pruned               -> not ok, summary names the plugin
    - deno runtime missing/old             -> not ok, summary names Deno
    - everything missing                   -> summary lists every piece

src.pot_provider._deno_ok
    - deno.exe present, recent version     -> True
    - deno.exe present, pre-2.0 version    -> False
    - deno.exe absent                      -> False without invoking subprocess

src.pot_provider.PotProviderStatus
    - frozen dataclass                     -> field assignment raises FrozenInstanceError
    - frozen dataclass                     -> attribute delete raises FrozenInstanceError
    - ok/summary() invariant holds across all 16 boolean combinations
    - summary() component order is stable when everything is missing

src.pot_provider._plugin_importable (exercised directly, not mocked away)
    - find_spec returns a spec             -> True
    - find_spec returns None               -> False
    - find_spec raises ImportError/ValueError -> False

src.pot_provider._deno_ok (additional boundaries)
    - exact min version (2.0.0)            -> True
    - just below min major (1.99.99)       -> False
    - multiline stdout, version on line 1  -> True
    - extra internal whitespace            -> True
    - empty / None stdout                  -> False
    - unparseable / incomplete version     -> False
    - prerelease suffix (2.0.0-rc.1)       -> True (documents permissive parsing)
    - non-zero returncode                  -> False, even with valid-looking stdout
    - subprocess timeout / OSError         -> False (swallowed)
    - deno.exe path is a directory         -> False, subprocess never invoked
    - numeric (not lexical) version compare -> 2.10.0 >= 2.9.0 is True

src.pot_provider.check_pot_provider (path resolution)
    - str server_home/scripts_dir          -> resolved like Path
    - relative server_home                 -> resolved against cwd
    - omitted args                         -> falls back to config module defaults
    - script path exists but is a directory -> treated as not found
    - node_modules path exists but is a file -> treated as not found
"""

import itertools
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src import pot_provider

# ---------------------------------------------------------------------------
# Tree helpers
# ---------------------------------------------------------------------------


def _valid_tree(root: Path) -> Path:
    """Build a fully wired server_home under ``root`` and return it."""
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "generate_once.ts").touch()
    (root / "node_modules").mkdir(parents=True, exist_ok=True)
    return root


# ---------------------------------------------------------------------------
# check_pot_provider — filesystem components (deno/plugin patched out)
# ---------------------------------------------------------------------------


def test_status_ok_when_all_present(tmp_path: Path) -> None:
    home = _valid_tree(tmp_path)
    with (
        patch("src.pot_provider._plugin_importable", return_value=True),
        patch("src.pot_provider._deno_ok", return_value=True),
    ):
        status = pot_provider.check_pot_provider(server_home=home, scripts_dir=tmp_path)
    assert status.ok is True
    assert status.summary() == ""


def test_missing_script_not_ok(tmp_path: Path) -> None:
    # node_modules present, but no src/generate_once.ts.
    (tmp_path / "node_modules").mkdir()
    with (
        patch("src.pot_provider._plugin_importable", return_value=True),
        patch("src.pot_provider._deno_ok", return_value=True),
    ):
        status = pot_provider.check_pot_provider(server_home=tmp_path, scripts_dir=tmp_path)
    assert status.ok is False
    assert "generate_once.ts" in status.summary()


def test_missing_node_modules_not_ok(tmp_path: Path) -> None:
    # script present, but no node_modules dir.
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "generate_once.ts").touch()
    with (
        patch("src.pot_provider._plugin_importable", return_value=True),
        patch("src.pot_provider._deno_ok", return_value=True),
    ):
        status = pot_provider.check_pot_provider(server_home=tmp_path, scripts_dir=tmp_path)
    assert status.ok is False
    assert "node_modules" in status.summary()


def test_plugin_pruned_not_ok(tmp_path: Path) -> None:
    home = _valid_tree(tmp_path)
    with (
        patch("src.pot_provider._plugin_importable", return_value=False),
        patch("src.pot_provider._deno_ok", return_value=True),
    ):
        status = pot_provider.check_pot_provider(server_home=home, scripts_dir=tmp_path)
    assert status.ok is False
    assert "provider plugin" in status.summary()


def test_deno_missing_not_ok(tmp_path: Path) -> None:
    home = _valid_tree(tmp_path)
    with (
        patch("src.pot_provider._plugin_importable", return_value=True),
        patch("src.pot_provider._deno_ok", return_value=False),
    ):
        status = pot_provider.check_pot_provider(server_home=home, scripts_dir=tmp_path)
    assert status.ok is False
    assert "Deno" in status.summary()


def test_summary_lists_multiple_missing(tmp_path: Path) -> None:
    # Empty server_home + both probes False -> every component is missing.
    with (
        patch("src.pot_provider._plugin_importable", return_value=False),
        patch("src.pot_provider._deno_ok", return_value=False),
    ):
        status = pot_provider.check_pot_provider(server_home=tmp_path, scripts_dir=tmp_path)
    summary = status.summary()
    assert "provider plugin" in summary
    assert "Deno" in summary


# ---------------------------------------------------------------------------
# _deno_ok — version parsing / gating
# ---------------------------------------------------------------------------


def test_deno_ok_parses_recent_version(tmp_path: Path) -> None:
    (tmp_path / "deno.exe").touch()
    with patch(
        "src.pot_provider.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="deno 2.5.4 (stable)"),
    ):
        assert pot_provider._deno_ok(tmp_path) is True


def test_deno_ok_rejects_old_version(tmp_path: Path) -> None:
    (tmp_path / "deno.exe").touch()
    with patch(
        "src.pot_provider.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="deno 1.46.3"),
    ):
        assert pot_provider._deno_ok(tmp_path) is False


def test_deno_ok_false_when_exe_absent(tmp_path: Path) -> None:
    with patch("src.pot_provider.subprocess.run") as mock_run:
        assert pot_provider._deno_ok(tmp_path) is False
    mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# PotProviderStatus — dataclass invariants
# ---------------------------------------------------------------------------


def test_status_is_frozen_dataclass() -> None:
    status = pot_provider.PotProviderStatus(
        plugin_installed=True,
        deno_ok=True,
        script_found=True,
        node_modules_found=True,
    )
    with pytest.raises(FrozenInstanceError):
        status.plugin_installed = False


def test_status_frozen_dataclass_blocks_attribute_delete() -> None:
    status = pot_provider.PotProviderStatus(
        plugin_installed=True,
        deno_ok=True,
        script_found=True,
        node_modules_found=True,
    )
    with pytest.raises(FrozenInstanceError):
        del status.deno_ok


# ---------------------------------------------------------------------------
# PotProviderStatus — ok/summary() combinatorial invariants
# ---------------------------------------------------------------------------

_ALL_MISSING_LABELS = {
    "plugin_installed": "provider plugin (bgutil-ytdlp-pot-provider)",
    "deno_ok": "Deno runtime (>= 2.0)",
    "script_found": "generate_once.ts script",
    "node_modules_found": "script dependencies (node_modules)",
}


@pytest.mark.parametrize("flags", list(itertools.product([True, False], repeat=4)))
def test_status_ok_and_summary_invariants_across_all_combinations(
    flags: tuple[bool, bool, bool, bool],
) -> None:
    plugin, deno, script, node_modules = flags
    status = pot_provider.PotProviderStatus(
        plugin_installed=plugin,
        deno_ok=deno,
        script_found=script,
        node_modules_found=node_modules,
    )
    expected_ok = plugin and deno and script and node_modules
    assert status.ok is expected_ok
    summary = status.summary()
    assert (summary == "") is expected_ok
    field_names = ("plugin_installed", "deno_ok", "script_found", "node_modules_found")
    for field, present in zip(field_names, flags, strict=True):
        label = _ALL_MISSING_LABELS[field]
        if present:
            assert label not in summary
        else:
            assert label in summary


def test_summary_component_order_is_stable_when_all_missing() -> None:
    status = pot_provider.PotProviderStatus(
        plugin_installed=False,
        deno_ok=False,
        script_found=False,
        node_modules_found=False,
    )
    assert status.summary() == (
        "provider plugin (bgutil-ytdlp-pot-provider), "
        "Deno runtime (>= 2.0), "
        "generate_once.ts script, "
        "script dependencies (node_modules)"
    )


# ---------------------------------------------------------------------------
# _plugin_importable — exercised directly (not mocked away)
# ---------------------------------------------------------------------------


def test_plugin_importable_true_when_spec_found() -> None:
    with patch(
        "src.pot_provider.importlib.util.find_spec",
        return_value=MagicMock(),
    ):
        assert pot_provider._plugin_importable() is True


def test_plugin_importable_false_when_spec_none() -> None:
    with patch("src.pot_provider.importlib.util.find_spec", return_value=None):
        assert pot_provider._plugin_importable() is False


def test_plugin_importable_false_on_import_error() -> None:
    with patch(
        "src.pot_provider.importlib.util.find_spec",
        side_effect=ImportError,
    ):
        assert pot_provider._plugin_importable() is False


def test_plugin_importable_false_on_value_error() -> None:
    with patch(
        "src.pot_provider.importlib.util.find_spec",
        side_effect=ValueError,
    ):
        assert pot_provider._plugin_importable() is False


# ---------------------------------------------------------------------------
# _deno_ok — additional version-parsing / subprocess boundaries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ("deno 2.0.0 (release, x86_64-pc-windows-msvc)", True),
        ("deno 1.99.99 (release)", False),
        ("deno 2.5.4 (stable)\nv8 12.4.254.21\ntypescript 5.6.2\n", True),
        ("deno    2.5.4   (release)", True),
        ("", False),
        ("deno version unknown", False),
        ("deno 2.5", False),
        ("deno 2.0.0-rc.1 (canary)", True),
    ],
    ids=[
        "exact-min-boundary",
        "just-below-min-major",
        "multiline-first-line",
        "extra-whitespace",
        "empty-stdout",
        "unparseable",
        "incomplete-semver",
        "prerelease-suffix-accepted",
    ],
)
def test_deno_ok_version_string_boundaries(
    tmp_path: Path,
    stdout: str,
    *,
    expected: bool,
) -> None:
    (tmp_path / "deno.exe").touch()
    with patch(
        "src.pot_provider.subprocess.run",
        return_value=MagicMock(returncode=0, stdout=stdout),
    ):
        assert pot_provider._deno_ok(tmp_path) is expected


def test_deno_ok_none_stdout_does_not_crash(tmp_path: Path) -> None:
    (tmp_path / "deno.exe").touch()
    with patch(
        "src.pot_provider.subprocess.run",
        return_value=MagicMock(returncode=0, stdout=None),
    ):
        assert pot_provider._deno_ok(tmp_path) is False


def test_deno_ok_nonzero_returncode_short_circuits(tmp_path: Path) -> None:
    (tmp_path / "deno.exe").touch()
    with patch(
        "src.pot_provider.subprocess.run",
        return_value=MagicMock(returncode=1, stdout="deno 2.5.4 (release)"),
    ):
        assert pot_provider._deno_ok(tmp_path) is False


def test_deno_ok_timeout_expired_swallowed(tmp_path: Path) -> None:
    (tmp_path / "deno.exe").touch()
    with patch(
        "src.pot_provider.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="deno --version", timeout=5.0),
    ):
        assert pot_provider._deno_ok(tmp_path) is False


def test_deno_ok_oserror_swallowed(tmp_path: Path) -> None:
    (tmp_path / "deno.exe").touch()
    with patch(
        "src.pot_provider.subprocess.run",
        side_effect=FileNotFoundError("deno.exe vanished"),
    ):
        assert pot_provider._deno_ok(tmp_path) is False


def test_deno_ok_exe_path_is_directory_not_file(tmp_path: Path) -> None:
    (tmp_path / "deno.exe").mkdir()
    with patch("src.pot_provider.subprocess.run") as mock_run:
        assert pot_provider._deno_ok(tmp_path) is False
    mock_run.assert_not_called()


def test_deno_ok_numeric_not_lexical_comparison(tmp_path: Path) -> None:
    """
    Guard against a regression to string comparison.

    "2.10.0" < "2.9.0" lexically even though it is numerically newer; the
    implementation must compare version tuples as integers.
    """
    (tmp_path / "deno.exe").touch()
    with (
        patch("src.pot_provider._DENO_MIN_VERSION", (2, 9, 0)),
        patch(
            "src.pot_provider.subprocess.run",
            return_value=MagicMock(returncode=0, stdout="deno 2.10.0 (release)"),
        ),
    ):
        assert pot_provider._deno_ok(tmp_path) is True


# ---------------------------------------------------------------------------
# check_pot_provider — path resolution boundaries
# ---------------------------------------------------------------------------


def test_check_pot_provider_accepts_str_paths(tmp_path: Path) -> None:
    home = _valid_tree(tmp_path / "home")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    with (
        patch("src.pot_provider._plugin_importable", return_value=True),
        patch("src.pot_provider._deno_ok", return_value=True),
    ):
        status = pot_provider.check_pot_provider(
            server_home=str(home),
            scripts_dir=str(scripts),
        )
    assert status.ok is True
    assert status.summary() == ""


def test_check_pot_provider_relative_server_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _valid_tree(tmp_path / "relhome")
    with (
        patch("src.pot_provider._plugin_importable", return_value=True),
        patch("src.pot_provider._deno_ok", return_value=True),
    ):
        status = pot_provider.check_pot_provider(
            server_home=Path("relhome"),
            scripts_dir=tmp_path,
        )
    assert status.ok is True


def test_check_pot_provider_uses_config_defaults_when_omitted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    default_home = _valid_tree(tmp_path / "default_home")
    monkeypatch.setattr(pot_provider, "POT_PROVIDER_SERVER_HOME", default_home)
    monkeypatch.setattr(pot_provider, "VENV_SCRIPTS_DIR", tmp_path)
    with (
        patch("src.pot_provider._plugin_importable", return_value=True),
        patch("src.pot_provider._deno_ok", return_value=True),
    ):
        status = pot_provider.check_pot_provider()
    assert status.ok is True
    assert status.summary() == ""


# ---------------------------------------------------------------------------
# check_pot_provider — file-vs-directory type confusion
# ---------------------------------------------------------------------------


def test_script_path_is_directory_not_file(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "generate_once.ts").mkdir()  # wrong type: dir, not file
    (tmp_path / "node_modules").mkdir()
    with (
        patch("src.pot_provider._plugin_importable", return_value=True),
        patch("src.pot_provider._deno_ok", return_value=True),
    ):
        status = pot_provider.check_pot_provider(server_home=tmp_path, scripts_dir=tmp_path)
    assert status.script_found is False
    assert status.ok is False
    assert "generate_once.ts" in status.summary()


def test_node_modules_path_is_file_not_dir(tmp_path: Path) -> None:
    home = _valid_tree(tmp_path)
    (home / "node_modules").rmdir()
    (home / "node_modules").touch()  # wrong type: file, not dir
    with (
        patch("src.pot_provider._plugin_importable", return_value=True),
        patch("src.pot_provider._deno_ok", return_value=True),
    ):
        status = pot_provider.check_pot_provider(server_home=home, scripts_dir=tmp_path)
    assert status.node_modules_found is False
    assert status.ok is False
    assert "node_modules" in status.summary()
