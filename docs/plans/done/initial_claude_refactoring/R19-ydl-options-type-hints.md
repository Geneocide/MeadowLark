# R19 — Replace `Any` Type Hints on `logger`/`qhook` in `src/ydl_options.py` ✅ DONE

## Problem

`build_base_ydl_opts` in `src/ydl_options.py` annotated both parameters as `Any`:

```python
def build_base_ydl_opts(logger: Any, qhook: Any) -> dict[str, Any]:  # noqa: ANN401
```

The `# noqa: ANN401` suppressed the Ruff warning. The actual types passed at every call site are:
- `logger` → `QLogger` (defined in `QYT.py`)
- `qhook` → `QHook` (defined in `QYT.py`)

**Importing `QYT` into `src/ydl_options.py` is problematic** because `QYT.py` lives at the project root, is a Qt module, and has no `src/` relationship. Creating a direct import would couple a configuration utility to the Qt layer — the wrong dependency direction.

The correct solution is a **Protocol** defined in a new `src/qt_protocols.py`. Protocols describe the interface without importing the concrete class, keeping `src/` independent of the Qt root modules.

---

## What the Protocols Need to Express

**`QLogger` interface** — yt-dlp calls these methods on the logger object:
- `debug(msg: str) -> None`
- `warning(msg: str) -> None`
- `error(msg: str) -> None`

**`QHook` interface** — yt-dlp calls the hook as a callable with a progress dict:
- `__call__(d: dict) -> None`

---

## Implementation (Option B — shared `src/qt_protocols.py`)

Created `src/qt_protocols.py` with `YdlLogger` (`@runtime_checkable` Protocol) and `YdlProgressHook` Protocol. Updated `src/ydl_options.py` to import and use them in the `build_base_ydl_opts` signature; removed `# noqa: ANN401` suppression.

Method stubs in `qt_protocols.py` have one-line docstrings to satisfy Ruff D102.

287 tests pass, 1 skipped (pre-existing). `ruff check src/qt_protocols.py src/ydl_options.py` — clean.
