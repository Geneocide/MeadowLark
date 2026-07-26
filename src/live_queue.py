from pathlib import Path

LiveQueueEntries = dict[str, tuple[str, str | None, str | None]]
"""Maps url -> (source, playlist_id, label)."""


def load_live_queue(path: Path) -> LiveQueueEntries:
    """Load live queue entries from file; returns {url: (source, playlist_id, label)}."""
    entries: LiveQueueEntries = {}
    if not path.exists():
        return entries
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            # stored as: source|url[|playlist_id[|label]]
            # The label is the folder the item was destined for before it was
            # parked here; without it a podcast episode cannot be filed back
            # under its show (see build_podcast_outtmpl).
            parts = line.split("|", 3)
            if len(parts) >= 2 and parts[1]:
                playlist_id = parts[2] if len(parts) >= 3 and parts[2] else None
                label = parts[3] if len(parts) == 4 and parts[3] else None
                entries[parts[1]] = (parts[0], playlist_id, label)
    return entries


def save_live_queue(path: Path, entries: LiveQueueEntries) -> None:
    """Write live queue entries to file."""
    with path.open("w", encoding="utf-8") as f:
        for url, (source, playlist_id, label) in entries.items():
            if label:
                f.write(f"{source}|{url}|{playlist_id or ''}|{label}\n")
            elif playlist_id:
                f.write(f"{source}|{url}|{playlist_id}\n")
            else:
                f.write(f"{source}|{url}\n")


def add_to_live_queue(
    path: Path,
    url: str,
    source: str,
    playlist_id: str | None = None,
    label: str | None = None,
) -> None:
    """Add a URL to the live queue, avoiding duplicates."""
    entries = load_live_queue(path)
    entries[url] = (source, playlist_id, label)
    save_live_queue(path, entries)
