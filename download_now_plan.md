Plan: Download Now for Podcast Status
TL;DR: Add a "Download Now" right-click menu item to the Podcast Status window that downloads all pending episodes for the selected podcast, bypassing the 24-hour SponsorBlock wait period entirely. The implementation reuses the existing download pipeline but modifies the filtering logic to skip the age check when invoked from the menu action.

Steps

✅ Modify _filter_audio_playlist_urls() [vid downloader.pyw](vid downloader.pyw#L756) to accept an optional bypass_sponsorblock_wait parameter (default False). When True, skip the 24-hour age check and include all episodes that don't have explicit errors.

✅ Update _on_podcast_status_context_menu() [vid downloader.pyw](vid downloader.pyw#L1081) to add a new "Download Now" menu action alongside the existing "Open Latest Video in Browser" action.

✅ Extract the podcast URL from the clicked table row using itemData() or by accessing self._podcast_last_statuses with the selected row index to get the stored "url" field.

✅ Create a new helper method _download_podcast_now_action() that:

- Gets the podcast URL from the selected row
- Calls _filter_audio_playlist_urls(playlist_url, bypass_sponsorblock_wait=True)
- Collects all returned episodes (both "Ready" and those that would have been "Pending SponsorBlock")
- Manually invokes the download queuing logic from _on_podcast_check_finished() [vid downloader.pyw](vid downloader.pyw#L1248) to queue them with appropriate outtmpl
- Ensure the status display updates after Download Now is triggered (the existing status update mechanism should handle this on the next check cycle).

Verification

Right-click on a podcast row in the Podcast Status window and confirm "Download Now" appears in the context menu
Click "Download Now" on a podcast with pending SponsorBlock episodes
Verify those episodes are queued for download immediately (check download queue or log output)
Confirm the downloads begin without waiting for the 24-hour period
Decisions

Download ALL pending episodes for the podcast, not just the latest (per user requirement)
Completely bypass SponsorBlock check (not just 24-hour wait) when "Download Now" is used
Reuse existing download pipeline to minimize code duplication and maintain consistency