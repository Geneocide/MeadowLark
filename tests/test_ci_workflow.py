"""
Guards the link between pyproject.toml's declared Python floor and the CI matrix.

.github/workflows/ci.yml documents (in its own comments) that the `test` job's
matrix "must cover the full `requires-python` range in pyproject.toml" -- but a
comment is not enforcement. This module reads the floor out of `requires-python`
(rather than repeating the literal "3.12", so the two cannot silently drift) and
proves the `test` job's matrix names it. Mirrors the equivalent guard in the
sibling genekit repo (`python/tests/test_packaging_metadata.py`,
`test_ci_matrix_actually_exercises_the_declared_floor`).
"""

import re
import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

_CI_PYTHON_VERSION_LIST = re.compile(r"python-version:\s*\[([^\]]*)\]")
_CI_PYTHON_VERSION_SCALAR = re.compile(r"""python-version:\s*["'](\d+\.\d+)["']""")
_CI_QUOTED_VERSION = re.compile(r"""["'](\d+\.\d+)["']""")


def _extract_versions(text: str) -> set[str]:
    versions = set(_CI_PYTHON_VERSION_SCALAR.findall(text))
    for listed in _CI_PYTHON_VERSION_LIST.findall(text):
        versions.update(_CI_QUOTED_VERSION.findall(listed))
    return versions


def _requires_python_floor() -> str:
    with (_REPO_ROOT / "pyproject.toml").open("rb") as handle:
        requires_python = tomllib.load(handle)["project"]["requires-python"]
    floor = re.fullmatch(r">=(\d+\.\d+)", requires_python)
    assert floor is not None, f"requires-python is not a bare '>=X.Y' floor: {requires_python!r}"
    return floor.group(1)


def test_ci_matrix_actually_exercises_the_declared_floor() -> None:
    """
    A declared floor that no CI leg runs is a claim, not a fact.

    Written to fail loudly rather than emptily: a workflow reformat that broke
    the extraction would otherwise leave a green no-op, so a non-empty result
    and a plausible version count are asserted before the membership check.
    The slice matters too -- the `lint` job carries its own unrelated
    `UV_PYTHON` pin, and searching the whole file would risk that (or a future
    job) masking a `test` job matrix that had genuinely dropped the floor.
    """
    workflow = (_REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    start = re.search(r"^  test:$", workflow, re.MULTILINE)
    assert start is not None, "no '  test:' job key found in ci.yml; the slice boundary moved"
    end = re.search(r"^  lint:$", workflow, re.MULTILINE)
    assert end is not None, "no '  lint:' job key found in ci.yml; the slice boundary moved"
    assert end.start() > start.start(), "ci.yml job order changed; the test-job slice is inverted"
    test_job = workflow[start.start() : end.start()]

    versions = _extract_versions(test_job)
    assert versions, "no python-version values extracted from the test job; the regex went stale"
    assert len(versions) >= 3, (
        f"test matrix names too few interpreters to be the real one: {sorted(versions)}"
    )

    floor = _requires_python_floor()
    assert floor in versions, (
        f"declared floor {floor} is not in the CI test matrix: {sorted(versions)}"
    )


def test_ci_version_list_regex_does_not_cross_a_closing_bracket() -> None:
    r"""
    `[^\]]*` must stop at the first `]`.

    So a second bracketed matrix key on the same job (e.g. an `os: [...]`
    axis) can never bleed into the captured version list.
    """
    text = 'python-version: ["3.12", "3.13"]\nos: [windows-latest, ubuntu-latest]\n'
    assert _CI_PYTHON_VERSION_LIST.findall(text) == ['"3.12", "3.13"']
    assert _extract_versions(text) == {"3.12", "3.13"}


def test_ci_version_regexes_ignore_matrix_interpolation_syntax() -> None:
    """
    Matrix interpolation syntax must not be mistaken for a literal version pin.

    `python-version: ${{ matrix.python-version }}` (the job-level env wiring
    in the real workflow) names the matrix key, not a literal version -- if
    it were, the `test` job's own env line would trivially "satisfy" the
    extraction regardless of the matrix's actual contents.
    """
    text = "name: py${{ matrix.python-version }}\nUV_PYTHON: ${{ matrix.python-version }}\n"
    assert _extract_versions(text) == set()


def test_ci_matrix_slice_excludes_the_lint_jobs_unrelated_pin() -> None:
    """
    Regression guard for why the real test slices to the `test:` job first.

    The `lint` job pins its own interpreter via `UV_PYTHON` for unrelated
    reasons (ruff reads `target-version` from `requires-python`, not the
    running interpreter). This synthetic workflow drops "3.12" from the
    `test` job's own matrix so the slice's effect is provable independent of
    the real ci.yml's current leg shape.
    """
    synthetic = (
        "  test:\n"
        "    strategy:\n"
        "      matrix:\n"
        '        python-version: ["3.13", "3.14"]\n'
        "  lint:\n"
        '    UV_PYTHON: "3.12"\n'
    )
    start = re.search(r"^  test:$", synthetic, re.MULTILINE)
    end = re.search(r"^  lint:$", synthetic, re.MULTILINE)
    assert start is not None
    assert end is not None
    sliced = synthetic[start.start() : end.start()]

    assert _extract_versions(sliced) == {"3.13", "3.14"}
    assert "3.12" not in _extract_versions(sliced)


def test_pyproject_requires_python_floor_matches_helper() -> None:
    """
    Pin `_requires_python_floor`'s parse against the real pyproject.toml.

    A change to the `requires-python` shape (e.g. a pinned upper bound like
    ">=3.12,<3.15") is caught here with a clear message rather than as an
    opaque `AssertionError` inside the main matrix test.
    """
    assert _requires_python_floor() == "3.12"
