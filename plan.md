
# Plan: Fix Audio Playlist Output Folder Resolution

The issue: audio playlist downloads end up in “NA” because we queue individual video URLs after expansion, and the `%(playlist)s` template is no longer available to yt-dlp.

Below are two viable approaches with implementation steps, trade-offs, and success criteria.

---

## Option A — Preserve Playlist Context by Downloading the Playlist

Instead of queuing individual episodes, enqueue the playlist URL with `playlist_items` restriction as needed. This keeps `%(playlist)s` available for `outtmpl`.

### Steps
1. In `_filter_audio_playlist_urls()`:
   - Stop returning per-episode `to_download` URLs.
   - Return playlist URLs in `to_download` when the latest episode is “Ready”.
   - Optionally include `playlist_items=1` if you only want the newest episode, or derive a range based on business rules.

2. In `_on_podcast_check_finished()`:
   - Leave behavior unchanged; it queues whatever is in `to_download`.

3. In `get_options()` for `audio_playlists`:
   - Keep current `outtmpl` using `%(playlist)s`.

4. Edge Cases:
   - Ensure `download_archive` behavior correctly de-duplicates per-episode even when downloading a playlist URL repeatedly.
   - Confirm `match_filter` still respects live/upcoming logic on playlist entries.

### Pros
- Minimal template changes.
- Lets yt-dlp populate `%(playlist)s` natively.

### Cons
- If you only want the newest episode, relying on `playlist_items` can be brittle for all platforms.
- Some platforms may misreport `playlist` fields or pagination.

### Success Criteria
- Files land in `manual podcasts/<PlaylistName>/`.
- No “NA” directories created.
- Archive prevents redownloading already-grabbed episodes.

---

## Option B — Pass Playlist Name Explicitly With Per-Episode URLs (Recommended)

Continue expanding to individual episode URLs, but explicitly compute and pass the playlist name so templates don’t depend on yt-dlp’s `%(playlist)s`.

### Steps
1. Extract a robust “playlist label”:
   - In `_filter_audio_playlist_urls()`:
     - From the playlist extraction response (`info`), prefer:
       - `info.get("title")` (playlist title)
       - Fallbacks: `info.get("uploader")` → parsed channel name → sanitized URL path segment.
     - Add this label into a return structure mapping `video_url -> playlist_label`.

2. Return structure changes:
   - Change `finished` payload to include a list of objects: `[{"url": ..., "playlist": ...}, ...]` for `to_download` and `pending`.
   - Update `_PodcastCheckWorker.finished` and `_on_podcast_check_finished()` signatures to accept these richer objects.

3. Build per-URL templating:
   - In `_on_podcast_check_finished()`:
     - Convert the object list to two parallel lists:
       - `urls = [obj["url"] for obj in to_download]`
       - `temp_outtmpl_map = {obj["url"]: computed_outtmpl_for_that_playlist}`
     - Two approaches for templating:
       - a) If yt-dlp version supports per-entry `outtmpl_dict` (template variables via `paths` or `outtmpl` mapping), use it.
       - b) Otherwise, run multiple sub-batches grouped by `playlist_label`, and set `outtmpl` per group:
         ```
         C:/Users/etreq/OneDrive/Desktop/scripts/manual podcasts/<playlist_label>/%(title)s.%(ext)s
         ```
     - Keep `postprocessors` the same.

4. Sanitize folder names:
   - Implement a small helper (e.g., `utils.sanitize_for_path`) to replace invalid Windows path characters: `<>:"/\|?*` and strip trailing dots/spaces.

5. Keep archive logic intact:
   - No change needed; still de-dups per-video ID.

6. Backward compatibility:
   - Default to `misc/` if no playlist label can be resolved.

### Pros
- Precise control over folder naming (consistent across platforms).
- Doesn’t depend on yt-dlp providing `%(playlist)s` on single-URL downloads.
- Easy to extend (e.g., special folder overrides per feed).

### Cons
- Slightly more code complexity (mapping playlist labels to per-batch `outtmpl`).

### Success Criteria
- Each episode from a podcast lands under a folder using the resolved playlist label.
- No “NA” directories created, even if `%(playlist)s` is missing in yt-dlp metadata.
- Mixed-platform robustness: works for YouTube and other feeds.

---

## Option C — Hybrid

- Default to Option B (explicit label passing).
- If a given site reliably provides `%(playlist)s`, allow a per-site toggle to use Option A for simplicity.

---

## Implementation Notes and Snippets

- Suggested output template in Option B:
  ```python
  base = "C:/Users/etreq/OneDrive/Desktop/scripts/manual podcasts"
  outtmpl = f"{base}/{sanitize(playlist_label)}/%(title)s.%(ext)s"
  ```

- Grouping sub-batches by label (Option B):
  ```python
  groups = {}
  for obj in to_download_objs:
      groups.setdefault(obj["playlist"], []).append(obj["url"])

  for label, urls in groups.items():
      batch_opts = dict(ydl_opts)
      batch_opts["outtmpl"] = f"{base}/{sanitize(label)}/%(title)s.%(ext)s"
      self.downloadQueue.put((urls, batch_opts))
  ```

- Sanitization helper (Windows-safe):
  ```python
  def sanitize(name: str) -> str:
      invalid = '<>:"/\\|?*'
      table = str.maketrans({c: "_" for c in invalid})
      cleaned = name.translate(table).rstrip(". ").strip()
      return cleaned or "misc"
  ```

---

## Open Questions

- Do you ever want more than the newest episode per feed when “Ready”? If yes, Option A with `playlist_items` ranges or Option B with N-latest logic is needed.
    - Yes, sometimes I want more than the single newest episode. Default behavior would be to get all undownloaded episodes. Downloaded epiosdes will be saved in tfarchive.txt.
- Any per-podcast custom folder overrides needed beyond playlist title?
    - No, I don’t think we need that.
- Should we collapse shows with long titles to short “slugs” to avoid path length issues?
    - Yes, shorten titles so they will not threaten Windows path length limits. the path before the playlist directory is `C:/Users/etreq/OneDrive/Desktop/scripts/manual podcasts'.

---

## Recommended Path

- Implement Option B (explicit playlist label passing) for reliability and cross-site consistency.
- Add a config flag later to allow Option A where `%(playlist)s` is known to be populated correctly.

---

## Validation Checklist

- Trigger “YT Podcasts” scan:
  - Status dialog shows labels resolved.
  - Ready episodes download under “manual podcasts/<ResolvedName>/”.
- No directories named “NA”.
- Windows path constraints handled (no invalid characters).
- Archive still prevents re-downloads.

---

I’m in read-only mode. If you want, switch to Code mode and I can help implement Option B step-by-step with diffs.
