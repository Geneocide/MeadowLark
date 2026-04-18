from pathlib import Path

LiveQueueEntries = dict[str, tuple[str, str | None]]


def load_live_queue(path: Path) -> LiveQueueEntries:
    """Load live queue entries from file; returns {url: (source, playlist_id)}."""
    entries: LiveQueueEntries = {}
    if not path.exists():
        return entries
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            # stored as: source|url  or  source|url|playlist_id
            parts = line.split("|", 2)
            if len(parts) >= 2 and parts[1]:  # noqa: PLR2004
                playlist_id = parts[2] if len(parts) == 3 and parts[2] else None  # noqa: PLR2004
                entries[parts[1]] = (parts[0], playlist_id)
    return entries


def save_live_queue(path: Path, entries: LiveQueueEntries) -> None:
    """Write live queue entries to file."""
    with path.open("w", encoding="utf-8") as f:
        for url, (source, playlist_id) in entries.items():
            if playlist_id:
                f.write(f"{source}|{url}|{playlist_id}\n")
            else:
                f.write(f"{source}|{url}\n")


def add_to_live_queue(
    path: Path,
    url: str,
    source: str,
    playlist_id: str | None = None,
) -> None:
    """Add a URL to the live queue, avoiding duplicates."""
    entries = load_live_queue(path)
    entries[url] = (source, playlist_id)
    save_live_queue(path, entries)
