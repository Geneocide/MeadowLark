# MeadowLark

A PyQt6 GUI for downloading videos, playlists, and podcasts via yt-dlp.

## Prerequisites

- **Python ≥ 3.10** and **[uv](https://docs.astral.sh/uv/getting-started/installation/)**
- **FFmpeg** — required for audio/podcast downloads. Install via [ffmpeg.org](https://ffmpeg.org/download.html) or a package manager, and make sure it's on `PATH`.
- **Deno** — auto-installed into `.venv/Scripts` when you run `uv sync`.

## Setup

```sh
git clone <repo-url>
cd "vid downloader"
uv sync
cp .env.example .env
git config core.hooksPath .githooks
```

Then open `.env` and fill in the three required paths:

| Variable | Description |
|---|---|
| `VID_DL_VIDEO_STORAGE_DIR` | Where downloaded videos are saved |
| `VID_DL_ARCHIVE_PATH` | yt-dlp archive file (prevents re-downloading) |
| `VID_DL_PODCAST_MISC_OUTPUT_DIR` | Output folder for miscellaneous podcast downloads |

## Run

```sh
uv run python meadowlark.pyw
```

## Environment variable reference

| Variable | Default | Description |
|---|---|---|
| `VID_DL_VIDEO_STORAGE_DIR` | `~/Videos` | Video output directory |
| `VID_DL_ARCHIVE_PATH` | `resources/archive.txt` | yt-dlp download archive |
| `VID_DL_PODCAST_MISC_OUTPUT_DIR` | `~/Music/Podcasts` | Misc podcast output directory |
| `VID_DL_ERROR_LOG` | `error_log.txt` | Error log file path |
| `VID_DL_HISTORY_LOG` | `history_log.txt` | Download history log path |
| `VID_DL_RESOURCES_DIR` | `resources` | Resources directory |
| `VID_DL_VENV_SCRIPTS` | `.venv/Scripts` | Virtual environment Scripts directory |
| `VID_DL_HTTP_TIMEOUT` | `120` | yt-dlp HTTP timeout (seconds) |
| `VID_DL_SOCKET_TIMEOUT` | `120` | yt-dlp socket timeout (seconds) |
| `VID_DL_HTTP_REQUEST_TIMEOUT` | `5` | External API request timeout (seconds) |
| `VID_DL_MAX_FRAGMENT_RETRIES` | `10` | Max fragment retry attempts |
| `VID_DL_PODCAST_MIN_DURATION_SECONDS` | `180` | Minimum duration to count as a podcast |
| `VID_DL_SPONSORBLOCK_CACHE_TTL_HOURS` | `6` | SponsorBlock cache TTL |
| `VID_DL_LIVE_QUEUE_CHECK_INTERVAL_MINUTES` | `30` | Live queue polling interval |
| `VID_DL_PODCAST_LOOKAHEAD_MAX_ATTEMPTS` | `5` | Max lookahead attempts for podcast fetching |
| `VID_DL_MERGE_OUTPUT_FORMAT` | `mp4` | Merge output container format |
| `VID_DL_APP_UPDATE_AUTO_CHECK` | `true` | Check for a new app release once per week at startup (set to `false` to opt out) |
| `VID_DL_APP_UPDATE_LAST_CHECKED` | _(empty)_ | ISO date of the last automatic update check; written by the app, not normally set by hand |
