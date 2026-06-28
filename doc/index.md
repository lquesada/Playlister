# Playlister Documentation

Playlister is a Linux command-line tool written in Python 3 that allows users to manage and synchronize Spotify playlists using a matrix defined in a CSV sheet.

- **GitHub Repository**: https://github.com/lquesada/playlister
- **Author & Copyright**: Copyright (c) 2026 Luis Quesada Torres ([www.luisquesada.com](https://www.luisquesada.com))
- **License**: Licensed under the [MIT License](../LICENSE).

---

## Command Line Usage

```bash
playlister <subcommand> [options]
```

### Subcommands

* **`diff <csv_file>`**
  Calculates differences between the CSV matrix and current Spotify playlists, printing a dry-run plan.
  * *Usage*: `playlister diff my_sheet.csv`

* **`push <csv_file>`**
  Applies proposed updates directly to Spotify.
  * *Usage*: `playlister push my_sheet.csv`
  * *Options*:
    * `--auto-approve` / `--auto_approve`: Apply changes without confirmation prompts.
    * `--remove-dupes` / `--remove_dupes`: Clean up any duplicate tracks found in Spotify playlists.

* **`check <csv_file>`**
  Verifies that all online Spotify playlist and track titles match their expected `#title:<...>` directives defined in the CSV sheet.
  * *Usage*: `playlister check my_sheet.csv`

* **`print <csv_file>`**
  Validates CSV sheet structure, syntax, and track ordering locally without connecting to Spotify. It prints the parsed playlists and tracks.
  * *Usage*: `playlister print my_sheet.csv`

* **`dump <playlist_or_album>`**
  Retrieves track details for the provided Spotify playlist or album and dumps them as CSV directives to `stdout`.
  * *Usage*: `playlister dump https://open.spotify.com/playlist/37i9dQZF1DXcBWIGmqZBmE`

* **`test-keys`**
  Verifies connection and credentials. 
  * *Usage*: `playlister test-keys` (performs online request to Spotify's `/me` endpoint).
  * *Options*:
    * `--local`: Validates local credentials folder structure offline without contacting Spotify.

* **`clear-keys`**
  Deletes stored Spotify credentials (specifically the `keys` file) from disk.
  * *Usage*: `playlister clear-keys`

* **`clear-cache`**
  Clears local track metadata cache (durations/names) to force a fresh fetch from Spotify.
  * *Usage*: `playlister clear-cache`

* **`clear-all`**
  Deletes the entire stored credentials and cache directory (`~/.playlister`).
  * *Usage*: `playlister clear-all`

---

## Global Options
These options apply to all subcommands interacting with Spotify and must be specified with root:
* `--key-dir <DIR_PATH>` (default: `~/.playlister`): Alternative directory for Spotify credentials and cache storage.
* `--no-store-key`: Runs the current session in memory without saving credentials/tokens to disk.

---

## Credentials & Cache Management
The tool always prints the path of the credentials directory currently in use (e.g. `Using API key directory: /home/user/.playlister`).
1. If the credentials file is missing or empty, the tool prints help instructions detailing how to create an application in the Spotify Developer Dashboard (https://developer.spotify.com/dashboard) to retrieve the Client ID and Client Secret.
2. It prompts the user via standard input for their Client ID and Client Secret, then directs them to authorize the app via browser redirect.
3. If `--no-store-key` is NOT specified, credentials and access/refresh tokens are saved to the key file with file permission `600` (read/write only by owner) for security.
4. If `--no-store-key` IS specified, the credentials are used in memory for the current session and never stored.
5. In addition to credentials, a track metadata cache (`cache` file) stores track durations and titles to optimize performance and prevent redundant API queries.

---

## CSV Sheet Formatting Rules

The CSV sheet represents a matrix where:
- Row 0 (excluding column 0) defines the **Playlists** and their properties.
- Column 0 (excluding row 0) defines the **Tracks** and their properties.
- Inner cells define the track's presence and 1-based order in each playlist.

### 1. Playlist Syntax (Row 0, starting at Column 1)
Playlist definition cells can contain multiple space-separated parameters:
- **Identifier** (Required unless `#ignore` is present):
  - `#playlist:<ID>` or `#playlist:<URL>` (e.g. `#playlist:43TtjGF050gzkar4IPmsLN` or `#playlist:https://open.spotify.com/playlist/43TtjGF050gzkar4IPmsLN`).
  - The tool automatically extracts the alphanumeric ID. If no playlist ID can be parsed and the playlist is not ignored, the tool will exit with an error.
- **Title Check**:
  - `#title:<EXPECTED_TITLE>` (can also use `@` or `!` as separators, e.g. `#title:@My Rock Hits@`).
  - If defined, the tool verifies that Spotify's title matches this expected title. If there is a mismatch, the tool will stop with a validation error.
- **Strict Check**:
  - `#strict`: If set, enables strict validation: sequence numbers must start at 1 and have no gaps, duplicate values raise errors, and empty or invalid cells trigger errors.
- **Ignore**:
  - `#ignore`: Ignores this playlist completely. (Takes precedence over `#strict` and `--strict`).

### 2. Track Syntax (Column 0, starting at Row 1)
Track definition cells can contain multiple space-separated parameters:
- **Identifier** (Required unless `#ignore` is present):
  - `#track:<ID>` or `#track:<URL>` (e.g. `#track:3BDidzS8avudzMj1G9ZZaz`).
  - The tool automatically extracts the alphanumeric ID. If no track ID can be parsed and the track is not ignored, the tool will exit with an error.
- **Title Check**:
  - `#title:<EXPECTED_TITLE>` (e.g., `#title:<Song One>`).
  - If defined, the tool verifies that Spotify's track title matches this expected title. If there is a mismatch, the tool will stop with a validation error.
- **Ignore**:
  - `#ignore`: Ignores this track completely.

### 3. Inner Cells
For Playlist `p` and Track `t`:
- `#no`: Explicitly marks that track `t` is not in playlist `p`.
- Positive Integer: Indicates the target ordering.
- Empty cell:
  - If playlist `p` is run in strict mode (either `#strict` is in header or `--strict` global CLI flag is set) -> Raises strict validation error.
  - Otherwise -> Treated as `#no`.
- Invalid string:
  - If playlist `p` is run in strict mode -> Raises validation error.
  - Otherwise -> Treated as `#no`.

### 4. Non-Strict Behavior (Default)
When strict mode is not active:
- Sequence numbers do not have to be continuous or start at 1. Gaps are allowed.
- Empty and invalid cells are treated as `#no`.
- Duplicate sequence numbers are allowed. Multiple tracks with the same number are stably randomized using the playlist ID as seed.
- All track indices are normalized sequentially (1, 2, 3...) when sent to Spotify.

---

## Output Format

For each active (non-ignored) playlist, the tool outputs the details of its tracks sorted by their assigned order number:

```
Playlist: <Playlist Name or ID> (N/A, <Number of Tracks> tracks)
1 - N/A - Track: <Track Name or ID>
2 - N/A - Track: <Track Name or ID>
...
```

*Note: The tool displays formatted durations (e.g. "3:00", "1:20:45") for tracks and playlists when available, falling back to "N/A" if unavailable.*

---

## Spotify Client Mocking (Dry Run)
When running in dry-run mode (`diff`), the tool emulates Spotify interactions using `OfflineSpotifyClient`:
- It returns track metadata with `name` set to the track's `#title` field (if defined in the CSV) or its ID (if `#title` is omitted), and `duration_ms` is resolved as `N/A`.
- It returns playlist metadata with `name` set to the playlist's `#title` field (if defined in the CSV) or its ID.
- If a dry-run scenario provides a mismatched Spotify mock title, the tool halts immediately with an error (e.g., `Error: Track title mismatch for ID 't1'. Spotify source of truth is 'Wrong Name', but the CSV has '#title:<Song One>'`).

---

## Initializing a CSV Sheet using `dump`

If you want to quickly build a CSV spreadsheet for an existing Spotify playlist or album, you can run the tool with the `dump` subcommand:

```bash
playlister dump <PLAYLIST_OR_ALBUM_ID_OR_URL>
```

This will authenticate with Spotify, retrieve the playlist/album details and all of its tracks, and output them to `stdout` formatted as CSV directives.

For a playlist:
```text
#playlist:43TtjGF050gzkar4IPmsLN #title:<My Cool Playlist>

#track:2TpxZ7JUBn3uw46yR768g0 #title:<Song One Name>
#track:1xLMxG745VdGkXW4G4tP1Z #title:<Song Two Name>
```

For an album:
```text
#album:3xbwfDBLL6oQI3Yu9CYX1v #title:<My Cool Album>

#track:2TpxZ7JUBn3uw46yR768g0 #title:<Song One Name>
#track:1xLMxG745VdGkXW4G4tP1Z #title:<Song Two Name>
```

You can redirect this output to a file or copy-paste it directly to set up Column 0 and Row 0 of your CSV matrix. (Note: For albums, the header uses `#album:...` for identification, though you will need to replace it with a `#playlist:...` directive containing your own target playlist ID when writing a CSV to sync back to Spotify).
