# Spotify Playlister CLI Utility

Playlister is a Linux command-line tool written in Python 3 that allows users to manage and synchronize Spotify playlists using a matrix defined in a CSV sheet.

- **GitHub Repository**: https://github.com/lquesada/playlister
- **Author & Copyright**: Copyright (c) 2026 Luis Quesada Torres ([www.luisquesada.com](https://www.luisquesada.com))
- **License**: Licensed under the [MIT License](LICENSE).

---

## Third-Party Libraries & Attributions

This project includes a vendored copy of the lightweight **spotipy** library (located in the `spotipy/` directory).
- **Source**: Obtained from the original repository at [https://github.com/tarruda/spotipy](https://github.com/tarruda/spotipy) by Thiago de Arruda.
- **Copyright**: Copyright (c) 2014 Thiago de Arruda
- **License**: MIT License. See [spotipy/LICENSE.txt](spotipy/LICENSE.txt) for details.

---

## Quick Setup & Synchronization Workflow

Get up and running with Spotify Playlister in a few simple steps:

### 1. Build the Executable
Compile the modular Python files into a single, self-contained executable binary:
```bash
./build.sh
```
This runs the unit tests first, and on success, packages the tool into `bin/playlister`.

### 2. Configure Credentials
Before using Spotify APIs, you need to create an application in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard):
- Set a **Redirect URI** to `http://127.0.0.1:8000/callback`.
- On your first run of `diff`, `push`, or `dump`, `playlister` will interactively prompt for your **Client ID** and **Client Secret**, and output an authorization URL. 
- Open that URL in your browser, approve, and copy the redirected URL (usually starts with `http://127.0.0.1:8000/callback?code=...`) back into the CLI.
- Stored credentials are saved securely in `~/.playlister/keys` with `600` permissions.

### 3. Bootstrap your CSV Sheet
If you already have an existing playlist on Spotify, you can easily initialize your CSV matrix headers and tracks by dumping it:
```bash
./bin/playlister dump <PLAYLIST_URL_OR_ID> > my_playlist_dump.txt
```
This prints:
```text
#playlist:43TtjGF050gzkar4IPmsLN #title:<My Cool Playlist>

#track:2TpxZ7JUBn3uw46yR768g0 #title:<Song One Name>
#track:1xLMxG745VdGkXW4G4tP1Z #title:<Song Two Name>
```
You can import this file into spreadsheet software (e.g. LibreOffice Calc, Excel, Google Sheets) to align tracks in Column 0 and playlists in Row 0, then define track sequence numbers in the intersecting cells.

### 4. Diff (Dry Run)
Check the differences between your local CSV sheet and Spotify playlists without making any changes:
```bash
./bin/playlister diff my_sheet.csv
```
This will fetch track listings from Spotify, compare them to your target sequence, and display a plan of additions, removals, and reorderings.

### 5. Push (Update Spotify)
When you are satisfied with the diff, push the updates directly to Spotify:
```bash
./bin/playlister push my_sheet.csv
```
By default, the tool prompts you to confirm changes for each playlist. To skip confirmation prompts (e.g., in scripts or cron jobs), run:
```bash
./bin/playlister push my_sheet.csv --auto-approve
```

---

## Detailed Command Reference

Playlister uses a subcommand-based command-line interface.

### Global Options
These flags can be placed before or after any subcommand that contacts Spotify:
* `--key-dir <DIR_PATH>` (default: `~/.playlister`): Alternative directory for Spotify credentials and cache storage.
* `--no-store-key`: Runs the current session in memory without saving credentials/tokens to disk.

### 1. `diff <csv_file>`
Calculates differences between the CSV matrix and current Spotify playlists, printing a dry-run plan.
* **Usage**: `playlister diff my_sheet.csv`

### 2. `push <csv_file>`
Applies proposed updates directly to Spotify.
* **Usage**: `playlister push my_sheet.csv`
* **Options**:
  * `--auto-approve` / `--auto_approve`: Apply changes without confirmation prompts.
  * `--remove-dupes` / `--remove_dupes`: Clean up any duplicate tracks found in Spotify playlists. (By default, duplicate tracks cause errors and abort updates).

### 3. `check <csv_file>`
Verifies that all online Spotify playlist and track titles match their expected `#title:<...>` directives defined in the CSV sheet.
* **Usage**: `playlister check my_sheet.csv`

### 4. `print <csv_file>`
Validates CSV sheet structure, syntax, and track ordering locally without connecting to Spotify. It prints the parsed playlists and tracks.
* **Usage**: `playlister print my_sheet.csv`

### 5. `dump <playlist_or_album>`
Retrieves track details for the provided Spotify playlist or album and dumps them as CSV directives to `stdout`.
* **Usage**: `playlister dump https://open.spotify.com/playlist/37i9dQZF1DXcBWIGmqZBmE`

### 6. `test-keys`
Verifies connection and credentials. 
* **Usage**: `playlister test-keys` (performs online request to Spotify's `/me` endpoint).
* **Options**:
  * `--local`: Validates local credentials folder structure offline without contacting Spotify.

### 7. `clear-keys`
Deletes stored Spotify credentials (specifically the `keys` file) from disk.
* **Usage**: `playlister clear-keys`

### 8. `clear-cache`
Clears local track metadata cache (durations/names) to force a fresh fetch from Spotify.
* **Usage**: `playlister clear-cache`

### 9. `clear-all`
Deletes the entire stored credentials and cache directory (`~/.playlister`).
* **Usage**: `playlister clear-all`

---

## CSV Formatting Rules
For complete configuration syntax, inner cell rules, and parameter flags, see the [Playlister Documentation](doc/index.md).

---

## Running Tests
To execute the unit test suite:
```bash
./tests.sh
```
