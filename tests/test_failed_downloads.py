"""Tests for the failed-downloads store, record factory, and FailureHook."""

import json
from pathlib import Path
from queue import Queue
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QApplication

from QYT import QYTQueue
from src.failed_downloads import (
    FailureHook,
    add_failed_download,
    load_failed_downloads,
    make_failed_record,
    remove_failed_download,
    save_failed_downloads,
)

_app = QApplication.instance() or QApplication([])

_RECORD_KEYS = {"key", "urls", "source", "site", "title", "failed_at", "error"}
_META = {"site": "youtube", "type": "1080"}


@pytest.fixture
def store(tmp_path: Path) -> Path:
    return tmp_path / "fd.json"


def test_load_missing_file_returns_empty(store: Path) -> None:
    assert load_failed_downloads(store) == []


def test_load_corrupt_json_returns_empty(store: Path) -> None:
    store.write_text("{not json", encoding="utf-8")
    assert load_failed_downloads(store) == []


def test_add_and_load_roundtrip(store: Path) -> None:
    add_failed_download(store, make_failed_record(["u1"], _META, "T", "boom"))

    records = load_failed_downloads(store)
    assert len(records) == 1
    assert set(records[0]) == _RECORD_KEYS
    assert records[0]["error"] == "boom"
    assert records[0]["source"] == "1080"


def test_add_dedupes_by_key_newest_first(store: Path) -> None:
    add_failed_download(store, make_failed_record(["u1"], _META, "T1", "first"))
    add_failed_download(store, make_failed_record(["u2"], _META, "T2", "second"))
    add_failed_download(store, make_failed_record(["u1"], _META, "T1", "retry"))

    records = load_failed_downloads(store)
    assert [r["key"] for r in records] == ["u1", "u2"]
    assert records[0]["error"] == "retry"


def test_remove_missing_key_noop(store: Path) -> None:
    add_failed_download(store, make_failed_record(["u1"], _META, "T", "boom"))

    remove_failed_download(store, "nope")

    assert [r["key"] for r in load_failed_downloads(store)] == ["u1"]


def test_remove_existing_key(store: Path) -> None:
    add_failed_download(store, make_failed_record(["u1"], _META, "T", "boom"))

    remove_failed_download(store, "u1")

    assert load_failed_downloads(store) == []


def test_make_failed_record_empty_urls() -> None:
    record = make_failed_record([], None, "t", "e")

    assert record["key"] == "t"
    assert record["source"] == "unknown"
    assert record["site"] == "unknown"


def test_error_truncated() -> None:
    record = make_failed_record(["u1"], _META, "T", "x" * 1000)

    assert len(record["error"]) == 500


def test_failure_hook_buffers_and_flushes() -> None:
    captured: list[dict] = []
    hook = FailureHook(_META, on_failure=captured.append)

    hook({"status": "error", "info_dict": {"id": "v1", "webpage_url": "u", "title": "T"}})
    hook.flush()

    assert len(captured) == 1
    assert captured[0]["key"] == "u"
    assert captured[0]["title"] == "T"


def test_failure_hook_discards_after_finish() -> None:
    captured: list[dict] = []
    hook = FailureHook(_META, on_failure=captured.append)

    hook({"status": "error", "info_dict": {"id": "v1", "webpage_url": "u", "title": "T"}})
    hook({"status": "finished", "info_dict": {"id": "v1"}})
    hook.flush()

    assert captured == []


def test_failure_hook_discards_after_merger_postprocessing() -> None:
    captured: list[dict] = []
    hook = FailureHook(_META, on_failure=captured.append)

    hook({"status": "error", "info_dict": {"id": "v1", "webpage_url": "u", "title": "T"}})
    hook(
        {
            "status": "postprocessing",
            "postprocessor": "Merger",
            "info_dict": {"id": "v1"},
        },
    )
    hook.flush()

    assert captured == []


def test_failure_hook_flush_clears_buffer() -> None:
    captured: list[dict] = []
    hook = FailureHook(_META, on_failure=captured.append)

    hook({"status": "error", "info_dict": {"id": "v1", "webpage_url": "u", "title": "T"}})
    hook.flush()
    hook.flush()

    assert len(captured) == 1


def test_failure_hook_never_raises() -> None:
    hook = FailureHook(None, on_failure=lambda _record: None)

    hook({})
    hook({"status": "error", "info_dict": None})
    hook.flush()


def test_qytqueue_download_emits_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    queue_obj = QYTQueue(Queue())
    monkeypatch.setattr(queue_obj.executor, "execute", lambda _u, _o: (False, "err msg"))
    monkeypatch.setattr(queue_obj.executor, "_extract_title", lambda _u: "T")
    captured: list[dict] = []
    queue_obj.download_failed.connect(captured.append)

    queue_obj.download(["u"], {"qmeta": _META})

    assert len(captured) == 1
    assert captured[0]["source"] == "1080"
    assert captured[0]["error"] == "err msg"


def test_qytqueue_download_no_emit_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    queue_obj = QYTQueue(Queue())
    monkeypatch.setattr(queue_obj.executor, "execute", lambda _u, _o: (True, ""))
    monkeypatch.setattr(queue_obj.executor, "_extract_title", lambda _u: "T")
    captured: list[dict] = []
    queue_obj.download_failed.connect(captured.append)

    queue_obj.download(["u"], {"qmeta": _META})

    assert captured == []


# --- Store robustness: non-list / malformed JSON payloads ---


@pytest.mark.parametrize("payload", ['{"a": 1}', "42", '"hello"', "null", "true"])
def test_load_non_list_json_returns_empty(store: Path, payload: str) -> None:
    store.write_text(payload, encoding="utf-8")
    assert load_failed_downloads(store) == []


def test_load_filters_non_dict_and_keyless_entries(store: Path) -> None:
    store.write_text(
        json.dumps(
            [
                {"key": "u1", "title": "ok"},
                "not-a-dict",
                123,
                None,
                {"title": "no key field"},
                {"key": ""},
                {"key": None},
                {"key": 0},
            ],
        ),
        encoding="utf-8",
    )

    records = load_failed_downloads(store)

    assert [r["key"] for r in records] == ["u1"]


def test_load_oserror_returns_empty(monkeypatch: pytest.MonkeyPatch, store: Path) -> None:
    store.write_text("[]", encoding="utf-8")

    def boom(self: Path, *args: object, **kwargs: object) -> str:
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "read_text", boom)

    assert load_failed_downloads(store) == []


def test_save_oserror_swallowed_and_tmp_cleaned(
    monkeypatch: pytest.MonkeyPatch,
    store: Path,
) -> None:
    def boom(self: Path, *args: object, **kwargs: object) -> int:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", boom)

    save_failed_downloads(store, [{"key": "u1"}])  # must not raise

    assert not store.exists()
    assert not store.with_suffix(".tmp").exists()


def test_save_creates_missing_parent_dir(tmp_path: Path) -> None:
    nested = tmp_path / "nested" / "dir" / "fd.json"

    save_failed_downloads(nested, [{"key": "u1"}])

    assert nested.exists()
    assert load_failed_downloads(nested) == [{"key": "u1"}]


def test_unicode_roundtrip(store: Path) -> None:
    record = make_failed_record(["u1"], _META, "日本語タイトル 🎬", "エラー: 失敗しました")
    add_failed_download(store, record)

    loaded = load_failed_downloads(store)

    assert loaded[0]["title"] == "日本語タイトル 🎬"
    assert loaded[0]["error"] == "エラー: 失敗しました"
    assert "\\u" not in store.read_text(encoding="utf-8")


def test_add_falsy_key_record_vanishes_on_reload(store: Path) -> None:
    """
    A record with empty urls AND an empty title gets key == "".

    add_failed_download's own return value still contains it, but the next
    load_failed_downloads call silently drops it (filters falsy keys), so the
    record is unrecoverable after the first reload. No current call site
    passes an empty title, but nothing guards against it either.
    """
    record = make_failed_record([], None, "", "some error")
    assert record["key"] == ""

    returned = add_failed_download(store, record)
    assert returned[0]["key"] == ""

    reloaded = load_failed_downloads(store)
    assert reloaded == []


def test_remove_with_falsy_key_is_noop(store: Path) -> None:
    add_failed_download(store, make_failed_record(["u1"], _META, "T", "e"))

    remove_failed_download(store, "")
    remove_failed_download(store, None)  # type: ignore[arg-type]

    assert [r["key"] for r in load_failed_downloads(store)] == ["u1"]


# --- make_failed_record boundary values ---


def test_error_exactly_500_not_truncated() -> None:
    record = make_failed_record(["u1"], _META, "T", "x" * 500)
    assert record["error"] == "x" * 500


def test_error_501_truncated_to_500() -> None:
    record = make_failed_record(["u1"], _META, "T", "x" * 501)
    assert len(record["error"]) == 500
    assert record["error"] == "x" * 500


def test_make_failed_record_empty_type_falls_back_to_source() -> None:
    record = make_failed_record(["u1"], {"type": "", "source": "manual"}, "T", "e")
    assert record["source"] == "manual"


def test_make_failed_record_non_string_title_used_as_key() -> None:
    record = make_failed_record([], None, 12345, "e")  # type: ignore[arg-type]
    assert record["key"] == 12345


def test_make_failed_record_non_string_error_raises_typeerror() -> None:
    with pytest.raises(TypeError):
        make_failed_record(["u1"], _META, "T", None)  # type: ignore[arg-type]


# --- FailureHook buffer/discard ordering ---


def test_failure_hook_error_finish_error_rebuffers() -> None:
    captured: list[dict] = []
    hook = FailureHook(_META, on_failure=captured.append)

    hook({"status": "error", "info_dict": {"id": "v1", "webpage_url": "u1", "title": "T1"}})
    hook({"status": "finished", "info_dict": {"id": "v1"}})
    hook(
        {
            "status": "error",
            "info_dict": {"id": "v1", "webpage_url": "u1", "title": "T1-retry"},
        },
    )
    hook.flush()

    assert len(captured) == 1
    assert captured[0]["title"] == "T1-retry"


def test_failure_hook_two_ids_one_ok_one_failed() -> None:
    captured: list[dict] = []
    hook = FailureHook(_META, on_failure=captured.append)

    hook({"status": "error", "info_dict": {"id": "v1", "webpage_url": "u1", "title": "Fails"}})
    hook({"status": "error", "info_dict": {"id": "v2", "webpage_url": "u2", "title": "Ok"}})
    hook({"status": "finished", "info_dict": {"id": "v2"}})
    hook.flush()

    assert len(captured) == 1
    assert captured[0]["title"] == "Fails"


def test_failure_hook_unrelated_postprocessor_does_not_discard() -> None:
    captured: list[dict] = []
    hook = FailureHook(_META, on_failure=captured.append)

    hook({"status": "error", "info_dict": {"id": "v1", "webpage_url": "u1", "title": "T"}})
    hook(
        {
            "status": "postprocessing",
            "postprocessor": "EmbedThumbnail",
            "info_dict": {"id": "v1"},
        },
    )
    hook.flush()

    assert len(captured) == 1


def test_failure_hook_empty_error_string_falls_back_to_default() -> None:
    captured: list[dict] = []
    hook = FailureHook(_META, on_failure=captured.append)

    hook(
        {
            "status": "error",
            "error": "",
            "fragment_error": "",
            "info_dict": {"id": "v1", "webpage_url": "u1", "title": "T"},
        },
    )
    hook.flush()

    assert captured[0]["error"] == "download error"


def test_failure_hook_non_dict_info_dict_does_not_raise() -> None:
    captured: list[dict] = []
    hook = FailureHook(_META, on_failure=captured.append)

    hook({"status": "error", "info_dict": ["not", "a", "dict"]})
    hook.flush()

    assert captured == []


def test_failure_hook_missing_vid_id_collision_loses_earlier_failure() -> None:
    """
    Two events lacking an id collide on the same fallback vid key.

    Both lack id/_filename/url/playlist_id and hash to "unknown", so the
    second error silently overwrites the first in the buffer.
    """
    captured: list[dict] = []
    hook = FailureHook(_META, on_failure=captured.append)

    hook({"status": "error", "info_dict": {"title": "First"}})
    hook({"status": "error", "info_dict": {"title": "Second"}})
    hook.flush()

    assert len(captured) == 1
    assert captured[0]["title"] == "Second"


# --- QYTQueue.download: hook/flush interaction with overall success/failure ---


def test_qytqueue_download_flushes_hook_failure_on_overall_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue_obj = QYTQueue(Queue())

    def fake_execute(_urls: list, opts: dict) -> tuple[bool, str]:
        for hook in opts.get("progress_hooks", []):
            if isinstance(hook, FailureHook):
                hook(
                    {
                        "status": "error",
                        "info_dict": {"id": "v1", "webpage_url": "u1", "title": "Entry"},
                    },
                )
        return True, ""

    monkeypatch.setattr(queue_obj.executor, "execute", fake_execute)
    monkeypatch.setattr(queue_obj.executor, "_extract_title", lambda _u: "T")
    captured: list[dict] = []
    queue_obj.download_failed.connect(captured.append)

    queue_obj.download(["u"], {"qmeta": _META})

    assert len(captured) == 1
    assert captured[0]["title"] == "Entry"


def test_qytqueue_download_hook_and_batch_both_emit_on_same_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Document the intentional overlap between hook and batch failure capture.

    A single-video failure can be captured by both the hook and the
    batch-level record; Phase 2's dedupe-by-key is what collapses them, not
    this layer.
    """
    queue_obj = QYTQueue(Queue())

    def fake_execute(_urls: list, opts: dict) -> tuple[bool, str]:
        for hook in opts.get("progress_hooks", []):
            if isinstance(hook, FailureHook):
                hook(
                    {
                        "status": "error",
                        "info_dict": {"id": "v1", "webpage_url": "u", "title": "T"},
                    },
                )
        return False, "err msg"

    monkeypatch.setattr(queue_obj.executor, "execute", fake_execute)
    monkeypatch.setattr(queue_obj.executor, "_extract_title", lambda _u: "T")
    captured: list[dict] = []
    queue_obj.download_failed.connect(captured.append)

    queue_obj.download(["u"], {"qmeta": _META})

    assert len(captured) == 2


# --- QYTQueue.run crash path: degenerate item shapes ---


def test_run_crash_path_empty_urls_and_none_item_uses_unknown_placeholders() -> None:
    class _StopLoop(Exception):
        """Breaks out of the otherwise infinite worker loop."""

    queue = MagicMock()
    item = ([], None)
    queue.get.side_effect = [item, _StopLoop()]
    queue.empty.return_value = True

    ydl_queue = QYTQueue(queue)
    captured: list[dict] = []
    ydl_queue.download_failed.connect(captured.append)

    with (
        patch("QYT.keep"),
        patch.object(ydl_queue, "download", side_effect=RuntimeError("boom")),
        pytest.raises(_StopLoop),
    ):
        ydl_queue.run()

    assert len(captured) == 1
    assert captured[0]["title"] == "(unknown)"
    assert captured[0]["key"] == "(unknown)"
    assert captured[0]["urls"] == []
    assert captured[0]["source"] == "unknown"
    assert "RuntimeError: boom" in captured[0]["error"]


def test_run_crash_path_non_dict_item_meta_falls_back_to_empty() -> None:
    class _StopLoop(Exception):
        """Breaks out of the otherwise infinite worker loop."""

    queue = MagicMock()
    item = (["https://example.com/v"], ["not", "a", "dict"])
    queue.get.side_effect = [item, _StopLoop()]
    queue.empty.return_value = True

    ydl_queue = QYTQueue(queue)
    captured: list[dict] = []
    ydl_queue.download_failed.connect(captured.append)

    with (
        patch("QYT.keep"),
        patch.object(ydl_queue, "download", side_effect=RuntimeError("boom")),
        pytest.raises(_StopLoop),
    ):
        ydl_queue.run()

    assert len(captured) == 1
    assert captured[0]["title"] == "https://example.com/v"
    assert captured[0]["key"] == "https://example.com/v"
    assert captured[0]["source"] == "unknown"
