# MeadowLark

A simple desktop app for downloading videos, playlists, and podcasts from YouTube and other sites. Built on top of [yt-dlp](https://github.com/yt-dlp/yt-dlp).

---

## Table of Contents

- [What MeadowLark Does](#what-meadowlark-does)
- [Features at a Glance](#features-at-a-glance)
- [Installation](#installation)
- [First Launch](#first-launch)
- [How to Use](#how-to-use)
  - [Downloading a Single Video or Audio File](#downloading-a-single-video-or-audio-file)
  - [Downloading a Playlist](#downloading-a-playlist)
  - [Downloading Podcasts](#downloading-podcasts)
  - [Live Videos](#live-videos)
- [Settings Reference](#settings-reference)
  - [Downloads Tab](#downloads-tab)
  - [Playlists Tab](#playlists-tab)
  - [Interface Tab](#interface-tab)
  - [Automation Tab](#automation-tab)
- [cookies.txt — What It Is and How to Get One](#cookiestxt--what-it-is-and-how-to-get-one)
- [Download History](#download-history)
- [Updates](#updates)
- [Developer Setup](#developer-setup)
- [Environment Variable Reference](#environment-variable-reference)

---

## What MeadowLark Does

MeadowLark lets you save videos and audio from YouTube (and hundreds of other sites) directly to your computer. You drag a URL onto the app and the file lands in your chosen folder. That's it.

It also handles:
- Bulk playlist downloads at a scheduled interval
- Podcast feeds saved as audio files
- Age-restricted videos (when you supply a cookies.txt from your browser)
- Automatically skipping videos you've already downloaded

---

## Features at a Glance

| Feature | What it does |
|---|---|
| **Drag-and-drop downloads** | Drop a URL onto the 1080p, 720p, or Audio zone to start downloading immediately |
| **Playlist downloader** | Point the app at a text file of playlist URLs; it downloads new entries on a schedule |
| **Podcast mode** | Downloads audio-only (m4a/mp3) and skips anything shorter than 3 minutes |
| **Archive / skip already-downloaded** | Keeps a log so videos are never downloaded twice |
| **SponsorBlock integration** | Skips sponsor segments when downloading podcasts |
| **Mark as watched** | Optionally tells YouTube a video is watched after you download it |
| **Live video queue** | Queues live streams and retries them automatically until they're available |

---

## Installation

> **Windows 10/11 only.**

1. Go to the [Releases page](https://github.com/TheGeneCode/MeadowLark/releases) and download `MeadowLark-Setup-{version}.exe`.
2. Double-click the installer and follow the wizard. You can optionally create a desktop shortcut during setup.
3. Launch MeadowLark from the Start Menu or your desktop shortcut.

---

## First Launch

The first time you open MeadowLark, a short setup wizard appears and asks two questions:

1. **Where should videos be saved?** — defaults to your `Videos` folder.
2. **Where should podcast episodes be saved?** — defaults to `Music\Podcasts`.

Pick your folders and click **OK**. The app remembers these choices in `AppData\Roaming\MeadowLark` and you won't be asked again. You can change them any time in **Settings → Downloads**.

---

## How to Use

### Downloading a Single Video or Audio File

1. Drag the URL from your browser's address bar and drop it onto one of the three drop zones in the app window:
   - **1080** — saves the video at up to 1080p
   - **720** — saves the video at 720p (smaller file)
   - **audio** — extracts audio only and saves as m4a
2. The status bar at the bottom shows download progress. When it says **[ Ready ]** again, the file is in your folder.

### Downloading a Playlist

MeadowLark can batch-download entire YouTube playlists. It tracks which videos it has already downloaded and skips them on future runs.

**Set up a playlist file:**

1. Open Notepad and add one YouTube playlist URL per line. Lines starting with `#` are treated as comments and skipped.

   ```
   # My tech videos
   https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxx

   # Gaming channel
   https://www.youtube.com/playlist?list=PLyyyyyyyyyyyyyyyy
   ```

2. Save the file as `playlists.txt` (or any name you like).

3. In MeadowLark, open **Settings → Playlists** and use the **Browse…** button next to the relevant playlist file:
   - **Playlists file (1080p)** — full quality video
   - **Playlists file (720p)** — medium quality video
   - **Playlists file (audio)** — audio only

4. Click **Apply** and then use the matching button in the main window (**Playlists**, **720 Playlists**, or **YT Podcasts**) to run a download.

### Downloading Podcasts

Podcast mode works just like the playlist downloader but saves audio files and filters out anything shorter than 3 minutes (so shorts and trailers are skipped automatically).

1. Add YouTube channel or podcast playlist URLs to your audio playlist file (see above).
2. Enable **Automation → Auto-check podcasts** if you want the app to check for new episodes on a schedule without you clicking anything.
3. New episodes land in your **Audio directory** (default: `Music\Podcasts`).

### Live Videos

If a video is currently live (not yet archived), MeadowLark adds it to an internal queue and retries it every 30 minutes until the stream has ended and a recording is available. No action is required from you — just drop the URL and forget it.

---

## Settings Reference

Open Settings from the menu or toolbar. Click **Apply** to save any change.

### Downloads Tab

| Setting | What it does |
|---|---|
| **Video directory** | Folder where downloaded videos are saved |
| **Audio directory** | Folder where podcast/audio files are saved |
| **Video format** | Container for video files: `mp4` (widest compatibility), `mkv`, or `webm` |
| **Audio format** | Format for audio files: `m4a` (recommended), `mp3`, `opus`, `flac`, or `wav` |
| **Mark watched on YouTube** | After a video downloads, automatically marks it as watched in your YouTube account. Requires a [cookies.txt](#cookiestxt--what-it-is-and-how-to-get-one) file with an active login. |

### Playlists Tab

| Setting | What it does |
|---|---|
| **Playlists file (1080p)** | Text file containing YouTube playlist URLs to download at 1080p |
| **Playlists file (720p)** | Same, but downloads at 720p |
| **Playlists file (audio)** | Same, but downloads audio only (podcast mode) |
| **Cookies.txt** | Path to your browser cookies export. Used for age-restricted or account gated (premium) videos and the "Mark watched" feature. See [below](#cookiestxt--what-it-is-and-how-to-get-one). |

> The playlist files are copied into AppData automatically when you browse and apply, so the originals can be moved or deleted.

### Interface Tab

| Setting | What it does |
|---|---|
| **Drop label — 1080/720/audio** | The text shown on each drop zone. Cosmetic only; doesn't change behavior. |
| **Ready text** | Status bar text shown when the app is idle |
| **Button labels** | Rename any of the three playlist/podcast buttons |
| **Always on top** | Keeps the MeadowLark window above all other windows |
| **Auto-check for app updates** | Checks GitHub for a new release once a week at startup and asks if you'd like any available update. Uncheck to opt out. |

### Automation Tab

| Setting | What it does |
|---|---|
| **Auto-check podcasts** | When on, the app automatically checks your podcast playlist file for new episodes |
| **Check interval** | How often to check, in minutes (5–1440). Default is 60 minutes. |

---

## cookies.txt — What It Is and How to Get One

Some videos on YouTube, or other sites, are age-restricted or require a login. MeadowLark can use a **cookies.txt** file — an export of your browser's YouTube session — to download these as if you were logged in.

The same file is needed if you enable **Mark watched on YouTube**.

### What is a cookies.txt file?

It's a plain text file containing the login tokens from your browser's session. Think of it like a temporary pass that tells websites "this is me." It does not contain your password.

### How to export one

**Option A — Browser extension (easiest)**

1. Install the **Get cookies.txt LOCALLY** extension:
   - [Chrome / Edge](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   - [Firefox](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)
2. Make sure you are logged into the sites you need an account for in that browser.
3. With the sites all open, click the extension icon, and click **Export**.
4. Save the file somewhere easy to find, e.g. `C:\Users\YourName\cookies.txt`.

**Option B — yt-dlp CLI (for advanced users)**

```powershell
yt-dlp --cookies-from-browser chrome --cookies cookies.txt --skip-download https://www.youtube.com
```

Replace `chrome` with `firefox`, `edge`, or `brave` as appropriate.

### Pointing MeadowLark at the file

1. Open **Settings → Playlists**.
2. Next to **Cookies.txt**, click **Browse…** and select the file you exported.
3. Click **Apply**.

> **Important:** MeadowLark reads the file in-place and does not copy it. If your browser extension keeps the file updated automatically (some do), MeadowLark will always use the latest version.

### Cookies expire

Browser cookies expire eventually (usually after a few weeks to a few months). If you start getting login errors or age-restriction errors, re-export a fresh cookies.txt and update the path in Settings.

---

## YouTube 1080p Downloads & the PO-Token Provider

YouTube gates 1080p (and higher) video streams behind a per-video **GVS PO token** (yt-dlp [#12482](https://github.com/yt-dlp/yt-dlp/issues/12482)). Without that token, the app can still fetch the metadata and *lower* resolutions, but every 1080p download fails at the media stage with:

```
unable to download video data: HTTP Error 403: Forbidden
```

MeadowLark mints the token with the **[bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider)** plugin running in **script (Deno) mode**. The plugin is a pinned dependency (installed by `uv sync`), and the Deno runtime is auto-installed into `.venv/Scripts`. The provider's generate script is **vendored** into the repo under `vendor/bgutil-pot-provider/server` (pinned to the same version as the plugin); its Node dependencies (`node_modules`) are generated once by `scripts/setup_pot_provider.py`.

### What the app checks at startup

On launch MeadowLark probes the provider and, if anything is missing, shows a **"PO Token Providers: none"** warning naming the missing pieces. It looks for:

| Component | Where |
|---|---|
| Provider plugin | importable `yt_dlp_plugins.extractor.getpot_bgutil_script` (from `uv sync`) |
| Deno runtime ≥ 2.0 | `deno.exe` in `.venv/Scripts` (from `uv sync`) |
| Generate script | `{server_home}/src/generate_once.ts` |
| Script dependencies | `{server_home}/node_modules` |

`server_home` defaults to the vendored `vendor/bgutil-pot-provider/server` (dev) or the bundled `bgutil-server` dir (frozen build), and is overridable with the `VID_DL_POT_SERVER_HOME` environment variable.

### Setting up the provider server

> **Installer users don't need this.** The packaged build (from `installer\setup.iss`) bundles the Deno runtime, the provider plugin, and the generate script **with its `node_modules` already built** into the app's `bgutil-server` folder, so 1080p works out of the box. The steps below are only for running MeadowLark **from source**.

The generate script is already vendored in the repo, so setup is a single command:

```sh
uv run python scripts/setup_pot_provider.py
```

This runs `deno install` in `vendor/bgutil-pot-provider/server`, creating `node_modules` next to the vendored `src/generate_once.ts`. Run it once after `uv sync` (re-running is a no-op unless you pass `--force`). Then restart MeadowLark — the warning dialog should no longer appear, and 1080p downloads will succeed.

> If you keep the provider somewhere else, point `VID_DL_POT_SERVER_HOME` at that `server` directory (the folder containing `src/generate_once.ts` and `node_modules`).

---

## Download History

MeadowLark keeps two logs in its AppData folder:

- **history_log.txt** — a record of every successful download (title, URL, timestamp)
- **error_log.txt** — errors and failures

You can view recent history inside the app via the **History** menu item (if available in your version). The archive file (`archive.txt`) is what yt-dlp uses internally to skip already-downloaded videos; you normally don't need to touch it. There is an **Ignore Archive?** checkbox that will download a video you have previously downloaded, if you need. Be careful to uncheck it when you no longer need it, or you could accidentally download whole playlists you've already seen.

---

## Updates

MeadowLark checks GitHub for new releases once a week at startup. When an update is found, a dialog appears with a download link.

To check manually: **Settings → About → Check for Updates**.

To turn off automatic checks: **Settings → Interface → Auto-check for app updates** (uncheck).

---

## Developer Setup

```sh
git clone https://github.com/TheGeneCode/MeadowLark
cd MeadowLark
uv sync
uv run python scripts/setup_pot_provider.py   # installs the vendored PO-token provider deps (needed for 1080p)
cp .env.example .env
git config core.hooksPath .githooks
uv run python meadowlark.pyw
```

> Skipping `setup_pot_provider.py` means 1080p downloads fail with HTTP 403 and the app shows a "PO Token Providers: none" warning at startup. See [YouTube 1080p Downloads](#youtube-1080p-downloads--the-po-token-provider).

### Prerequisites

- **Python ≥ 3.10** and **[uv](https://docs.astral.sh/uv/getting-started/installation/)**
- **FFmpeg** — required for audio/podcast downloads. Install via [ffmpeg.org](https://ffmpeg.org/download.html) or a package manager, and make sure it's on `PATH`.
- **Deno** — auto-installed into `.venv/Scripts` when you run `uv sync`.

---

## Environment Variable Reference

Advanced users can override defaults by editing the `.env` file in `AppData\Roaming\MeadowLark\.env`. Most settings are easier to change through the Settings dialog.

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
| `VID_DL_MARK_WATCHED` | `false` | Auto-mark downloaded YouTube videos as watched via cookies session (requires valid `cookies.txt`) |
| `VID_DL_POT_SERVER_HOME` | `vendor/bgutil-pot-provider/server` (dev) / bundled `bgutil-server` (frozen) | PO-token provider server home (bgutil script-deno mode); must contain `src/generate_once.ts` and `node_modules` (run `scripts/setup_pot_provider.py`). See [YouTube 1080p Downloads](#youtube-1080p-downloads--the-po-token-provider). |
