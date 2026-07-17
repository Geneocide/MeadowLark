"""Persistent store for failed downloads and the progress hook that captures them."""

import json
from collections.abc import Callable
from pathlib import Path

from .logging_utils import get_local_timestamp, log_exception

FailedRecord = dict  # keys: key, urls, source, site, title, failed_at, error

_MAX_ERROR_LEN = 500


def load_failed_downloads(path: Path) -> list[FailedRecord]:
    """Load failed-download records; newest first. Returns [] on missing/corrupt file."""
    if not path.exists():
        return []
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log_exception(exc, f"load_failed_downloads: unreadable store at {path}")
        return []
    if not isinstance(parsed, list):
        return []
    return [r for r in parsed if isinstance(r, dict) and r.get("key")]


def save_failed_downloads(path: Path, records: list[FailedRecord]) -> None:
    """Write failed-download records atomically; never raises on write failure."""
    tmp_path = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(
            json.dumps(records, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        tmp_path.replace(path)
    except OSError as exc:
        log_exception(exc, f"save_failed_downloads: could not write {path}")
        tmp_path.unlink(missing_ok=True)


def add_failed_download(path: Path, record: FailedRecord) -> list[FailedRecord]:
    """Add a record newest-first, replacing any existing record with the same key."""
    records = [r for r in load_failed_downloads(path) if r.get("key") != record.get("key")]
    records.insert(0, record)
    save_failed_downloads(path, records)
    return records


def remove_failed_download(path: Path, key: str) -> list[FailedRecord]:
    """Remove the record with the given key; a missing key is a no-op."""
    records = [r for r in load_failed_downloads(path) if r.get("key") != key]
    save_failed_downloads(path, records)
    return records


def make_failed_record(
    urls: list,
    meta: dict | None,
    title: str,
    error: str,
) -> FailedRecord:
    """Normalize a failure into a display-ready record for the store."""
    meta = meta or {}
    return {
        "key": urls[0] if urls else title,
        "urls": list(urls),
        "source": meta.get("type") or meta.get("source") or "unknown",
        "site": meta.get("site") or "unknown",
        "title": title,
        "failed_at": get_local_timestamp(),
        "error": error[:_MAX_ERROR_LEN],
    }


class FailureHook:
    """
    Progress hook buffering per-entry download errors.

    With ignoreerrors="only_download" (playlist sources), a failing entry never
    raises out of DownloadExecutor.execute - the only signal is a progress event
    with status == "error". A later "finished"/postprocessing event for the same
    video id means a fallback (720p / no-SponsorBlock) succeeded, so the buffered
    failure is discarded. flush() reports what remains.
    """

    def __init__(
        self,
        meta: dict | None,
        on_failure: Callable[[FailedRecord], None],
    ) -> None:
        """Initialize the hook with download metadata and a failure callback."""
        self.meta = meta or {}
        self.on_failure = on_failure
        self._buffered: dict[str, FailedRecord] = {}

    def _vid_id(self, info: dict) -> str:
        # Duplicated from QYT.HistoryHook._vid_id rather than imported: importing
        # QYT here would create a src -> root -> src import cycle.
        return str(
            info.get("id")
            or info.get("_filename")
            or info.get("url")
            or info.get("playlist_id")
            or "unknown",
        )

    def __call__(self, d: dict) -> None:
        """Buffer an error event, or discard a buffered failure once the item finishes."""
        try:
            status = d.get("status")
            info = d.get("info_dict") or {}
            vid = self._vid_id(info)

            if status == "error":
                self._buffered[vid] = make_failed_record(
                    urls=[info.get("webpage_url") or info.get("url") or vid],
                    meta=self.meta,
                    title=info.get("title") or info.get("id") or "(unknown title)",
                    error=str(
                        d.get("error") or d.get("fragment_error") or "download error",
                    ),
                )
            elif status == "finished":
                self._buffered.pop(vid, None)
            elif status == "postprocessing":
                postproc = (d.get("postprocessor") or "").lower()
                if "merger" in postproc or "ffmpegextractaudio" in postproc:
                    self._buffered.pop(vid, None)
        except (AttributeError, TypeError, OSError) as exc:
            # Never let failure capture break the download, but capture it
            log_exception(exc, "FailureHook failed while recording a download error")

    def flush(self) -> None:
        """Report every still-buffered failure, then clear the buffer."""
        for record in self._buffered.values():
            try:
                self.on_failure(record)
            except (AttributeError, TypeError, OSError, RuntimeError) as exc:
                log_exception(exc, "FailureHook: on_failure callback failed")
        self._buffered.clear()
