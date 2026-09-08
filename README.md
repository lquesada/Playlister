# Spotify & YouTube Playlister CLI Utility

Playlister is a Linux command-line tool written in Python 3 that allows users to manage and synchronize Spotify and YouTube playlists using a matrix defined in a CSV sheet.

- **GitHub Repository**: https://github.com/lquesada/playlister
- **Author & Copyright**: Copyright (c) 2026 Luis Quesada Torres ([www.luisquesada.com](https://www.luisquesada.com))
- **License**: Licensed under the [MIT License](LICENSE).

---

## Third-Party Libraries & Attributions

This project includes a vendored copy of the lightweight **spotipy** library (located in the `spotipy/` directory).
- **Source**: Obtained from the original repository at [https://github.com/tarruda/spotipy](https://github.com/tarruda/spotipy) by Thiago de Arruda.
- **Copyright**: Copyright (c) 2014 Thiago de Arruda
- **License**: MIT License. See [spotipy/LICENSE.txt](spotipy/LICENSE.txt) for details.

The YouTube Data API v3 client and OAuth 2.0 implementation use Python's built-in standard library (`urllib.request`), requiring zero external dependencies.

---

## Quick Setup & Synchronization Workflow

Get up and running with Playlister in a few simple steps:

### 1. Build the Executable
Compile the modular Python files into a single, self-contained executable binary:
```bash
./build.sh
```
This runs the test suite first and packages the tool into `bin/playlister`.

---

### 2. Configure Credentials

#### A. Spotify Setup
1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Create an application to get your **Client ID** and **Client Secret**.
3. In your Spotify app settings, add `http://127.0.0.1:8000/callback` as a **Redirect URI**.
4. On your first run of `diff`, `push`, or `dump`, `playlister` will interactively prompt for credentials and print an authorization URL. Authorize in your browser and paste the redirected URL back into the CLI.
5. Spotify credentials are saved securely in `~/.playlister/keys` (permissions `0600`).

#### B. YouTube Setup (100% Free, No Credit Card Required)
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g. *Playlister*).
3. Navigate to **APIs & Services** > **Library**, search for **YouTube Data API v3**, and click **Enable**.
4. Configure the **OAuth consent screen**:
   - Choose **External**, enter an App name, and save.
   - Under **Test users**, click **+ ADD USERS** and add your Google account email.
5. Create credentials under **APIs & Services** > **Credentials**:
   - Click **+ CREATE CREDENTIALS** > **OAuth client ID**.
   - Application type: **Desktop app**.
   - Copy your **Client ID** and **Client Secret** (or click **Download JSON**).
6. On your first run targeting YouTube, `playlister` prompts for your Client ID and Secret (or you can point to the downloaded JSON file with `--youtube-client-secrets path/to/client_secrets.json`).
7. Open the generated Google consent link, approve, and paste the authorization code back into the CLI.
8. YouTube credentials are saved securely in `~/.playlister/youtube_keys` (permissions `0600`).

---

### 3. Bootstrap your CSV Sheet

If you already have existing playlists, dump them directly to CSV format:

#### Dump from Spotify:
```bash
./bin/playlister dump https://open.spotify.com/playlist/43TtjGF050gzkar4IPmsLN > my_playlist_dump.txt
```

#### Dump from YouTube:
```bash
./bin/playlister dump https://www.youtube.com/playlist?list=PL1234567890 > my_playlist_dump.txt
```

This generates formatted directives:
```text
#youtubeplaylist:PL1234567890 #youtubetitle:<My YouTube Mix>

#youtubetrack:dQw4w9WgXcQ #youtubetitle:<Never Gonna Give You Up>
#youtubetrack:kJQP7kiw5Fk #youtubetitle:<Despacito>
```

You can import this into spreadsheet software (e.g. LibreOffice Calc, Excel, Google Sheets) to align tracks and playlists into a matrix.

---

### 4. Diff (Dry Run)

Check proposed additions, removals, and reorderings without making any changes:
```bash
./bin/playlister diff my_sheet.csv
```

To restrict the diff to a specific service:
```bash
./bin/playlister diff my_sheet.csv --spotify
./bin/playlister diff my_sheet.csv --youtube
```

---

### 5. Push (Apply Changes)

Apply the changes to Spotify and/or YouTube:
```bash
./bin/playlister push my_sheet.csv
```

By default, the tool prompts for confirmation before applying changes to each playlist. To skip prompts (e.g. in automated scripts), use:
```bash
./bin/playlister push my_sheet.csv --auto-approve
```

---

## Detailed Command Reference

### Global Options
* `--service [all|spotify|youtube]` (default: `all`): Target service.
* `--spotify`: Target Spotify only (shorthand for `--service spotify`).
* `--youtube`: Target YouTube only (shorthand for `--service youtube`).
* `--youtube-client-secrets <PATH>`: Path to Google Cloud `client_secrets.json` file.
* `--key-dir <DIR_PATH>` (default: `~/.playlister`): Alternative directory for credentials and caches.
* `--no-store-key`: Prompts for credentials in memory without saving to disk.
* `--strict`: Enforces strict validation on all processed playlists (disallows gaps and duplicate positions).
* `--ignore-missing-tracks`: Ignores and skips CSV rows that do not have a valid track ID.

### 1. `diff <csv_file>`
Calculates differences between the CSV matrix and online playlists, displaying a dry-run plan.
```bash
playlister diff my_sheet.csv
playlister diff my_sheet.csv --youtube
```

### 2. `push <csv_file>`
Applies proposed updates to Spotify and/or YouTube.
```bash
playlister push my_sheet.csv
```
Options:
* `--auto-approve`: Apply changes without confirmation prompts.
* `--remove-dupes`: Automatically clean up duplicate tracks found online.

### 3. `check <csv_file>`
Verifies that online playlist and track titles match their expected `#title:<...>`, `#spotifytitle:<...>`, and `#youtubetitle:<...>` directives.
```bash
playlister check my_sheet.csv
```

### 4. `print <csv_file>`
Validates CSV sheet structure, syntax, and track ordering locally without network access.
```bash
playlister print my_sheet.csv
```

### 5. `dump <playlist_or_album>`
Retrieves track details from Spotify or YouTube and outputs CSV directives.
```bash
playlister dump https://open.spotify.com/playlist/37i9dQZF1DXcBWIGmqZBmE
playlister dump https://www.youtube.com/playlist?list=PL1234567890
```

### 6. `test-keys`
Tests API credentials and connection.
```bash
playlister test-keys
playlister test-keys --youtube
playlister test-keys --local
```

### 7. `clear-keys`
Deletes stored credentials (`keys` for Spotify, `youtube_keys` for YouTube).
```bash
playlister clear-keys
playlister clear-keys --youtube
```

### 8. `clear-cache`
Clears cached metadata (duration and names).
```bash
playlister clear-cache
```

### 9. `clear-all`
Deletes the entire credentials and cache directory (`~/.playlister`).
```bash
playlister clear-all
```

---

## CSV Formatting Rules

### Column Categorization
* **Playlist Columns**: Any column where the **Row 0 header cell** contains `#playlist`, `#spotifyplaylist`, `#youtubeplaylist`, or `#ytplaylist`.
* **Track Descriptor Columns**: **Any column** where Row 0 does **not** contain a playlist directive. Multiple descriptor columns can be used to organize Spotify IDs, YouTube IDs, notes, and song titles.

### Playlist Directives (Row 0 cells)
* `#spotifyplaylist:<ID_or_URL>` (alias: `#playlist:...`): Defines a Spotify playlist.
* `#youtubeplaylist:<ID_or_URL>` (alias: `#ytplaylist:...`): Defines a YouTube playlist.
* `#spotifytitle:<TITLE>`: Expected Spotify title (quotes `<...>`, `@...@`, `!...!` supported).
* `#youtubetitle:<TITLE>`: Expected YouTube title.
* `#title:<TITLE>`: General expected title.
* `#strict`: Enforces continuous sequence starting from 1 with no duplicates or empty cells.
* `#ignore`: Ignores this playlist completely.
* **Shared Playlists**: You can include **both** `#spotifyplaylist` and `#youtubeplaylist` in the same column header cell to sync both services to the exact same track ordering!

### Track Directives (Row 1+ cells across descriptor columns)
* `#spotifytrack:<ID_or_URL>` (alias: `#track:...`): Spotify track ID or URL.
* `#youtubetrack:<ID_or_URL>` (alias: `#yttrack:...`): YouTube video ID or URL (`v=` URL, `youtu.be/` URL, or raw ID).
* `#spotifytitle:<TITLE>`: Expected Spotify track title.
* `#youtubetitle:<TITLE>`: Expected YouTube video title.
* `#title:<TITLE>`: General expected track title.
* `#ignore`: Ignores this track row entirely.

### Multi-Column Layout Example
You can structure your spreadsheet with dedicated columns:

```csv
Spotify,YouTube,Title,#spotifyplaylist:sp_hits #title:<Hits>,#youtubeplaylist:PL_hits #title:<Hits>,#spotifyplaylist:sp_pop #youtubeplaylist:PL_pop #title:<Soft Pop>
#spotifytrack:4cOdK2wGLETKBW3PvgPWqT,#youtubetrack:dQw4w9WgXcQ,#title:<Never Gonna Give You Up>,1,1,1
#spotifytrack:3BDidzS8avudzMj1G9ZZaz,#youtubetrack:kJQP7kiw5Fk,#title:<Despacito>,2,2,#no
#spotifytrack:1xLMxG745VdGkXW4G4tP1Z,#youtubetrack:9bZkp7q19f0,#title:<Gangnam Style>,3,#no,2
```

Alternatively, you can place column directives in the header (e.g. `#spotifytrack` in Col 0, `#youtubetrack` in Col 1) and raw IDs in the cells below without repeating `#` on every row!

---

## YouTube Quota Management

The YouTube Data API v3 free tier provides **10,000 units per day**:
* Reading playlist items: **1 unit**
* Creating a playlist: **50 units**
* Adding a video (`playlistItems.insert`): **50 units**
* Removing an item (`playlistItems.delete`): **50 units**

At 50 units per video change, the daily free quota easily allows adding or modifying **~200 songs per day**. Tracks with no changes consume zero write quota units. Metadata like video titles and durations are cached in `~/.playlister/youtube_cache` to minimize read quota.

---

## Running Tests

To run the full unit test suite:
```bash
./tests.sh
```
