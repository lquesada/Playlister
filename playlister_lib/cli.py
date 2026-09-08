import argparse

def parse_args(args=None):
    epilog_text = """
CSV Sheet Structure:
  - Row 0 defines the columns. Columns without playlist directives are TRACK DESCRIPTORS.
  - Columns with playlist directives (#playlist, #spotifyplaylist, #youtubeplaylist) are PLAYLISTS.
  - Rows 1+ define the TRACKS and their order sequence.
  - Inner cells contain positive integers (1-based order) or '#no'.

Playlist Directives (Row 0 cells):
  Multiple space-separated directives can be specified in each cell:
  - #spotifyplaylist:<ID_or_URL> - Spotify playlist ID or URL (alias: #playlist:...).
  - #youtubeplaylist:<ID_or_URL> - YouTube playlist ID or URL (alias: #ytplaylist:...).
  - #spotifytitle:<EXPECTED_TITLE> - Expected Spotify playlist title.
  - #youtubetitle:<EXPECTED_TITLE> - Expected YouTube playlist title.
  - #title:<EXPECTED_TITLE>        - General expected title. Quotes allowed: <Title>, @Title@, !Title!.
  - #strict                        - Restricts check (errors on gaps, invalid/empty cells).
  - #ignore                        - Ignores this playlist completely.
  Note: A single column can specify BOTH #spotifyplaylist and #youtubeplaylist to sync both services!

Track Directives (Row 1+ cells in any descriptor column):
  Any column without a playlist directive in Row 0 is processed as a track descriptor column.
  Directives can be placed across multiple columns or combined in a single cell:
  - #spotifytrack:<ID_or_URL>   - Spotify track ID or URL (alias: #track:...).
  - #youtubetrack:<ID_or_URL>   - YouTube video ID or URL (alias: #yttrack:...).
  - #spotifytitle:<EXPECTED_TITLE> - Expected Spotify track title.
  - #youtubetitle:<EXPECTED_TITLE> - Expected YouTube video title.
  - #title:<EXPECTED_TITLE>        - General expected title.
  - #ignore                        - Ignores this track completely.
"""

    # Common parent parser for global/root options
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "--key-dir", "--key_dir",
        default=None,
        help="Alternative directory for credentials and cache storage"
    )
    parent_parser.add_argument(
        "--no-store-key", "--no_store_key",
        action="store_true",
        help="Do not store credentials in the credentials directory"
    )
    parent_parser.add_argument(
        "--strict",
        action="store_true",
        help="Consider all playlists strict"
    )
    parent_parser.add_argument(
        "--service",
        choices=["all", "spotify", "youtube"],
        default="all",
        help="Target music service (default: all)"
    )
    parent_parser.add_argument(
        "--spotify",
        action="store_true",
        help="Target Spotify only (alias for --service spotify)"
    )
    parent_parser.add_argument(
        "--youtube",
        action="store_true",
        help="Target YouTube only (alias for --service youtube)"
    )
    parent_parser.add_argument(
        "--youtube-client-secrets", "--youtube_client_secrets",
        default=None,
        help="Path to Google Cloud client_secrets.json file for YouTube API"
    )

    parser = argparse.ArgumentParser(
        description="Spotify & YouTube Playlister CSV manager.",
        epilog=epilog_text,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Subcommand to run")

    # 1. diff
    diff_parser = subparsers.add_parser(
        "diff",
        parents=[parent_parser],
        help="Calculate diff between CSV sheet and Spotify/YouTube playlists (dry run)"
    )
    diff_parser.add_argument("csv_file", help="Path to playlists/tracks CSV file")

    # 2. push
    push_parser = subparsers.add_parser(
        "push",
        parents=[parent_parser],
        help="Apply CSV sheet changes to Spotify and/or YouTube"
    )
    push_parser.add_argument("csv_file", help="Path to playlists/tracks CSV file")
    push_parser.add_argument(
        "--auto-approve", "--auto_approve",
        action="store_true",
        help="Automatically approve all proposed changes without prompting"
    )
    push_parser.add_argument(
        "--remove-dupes", "--remove_dupes",
        action="store_true",
        help="Remove duplicate tracks from playlists"
    )

    # 3. check
    check_parser = subparsers.add_parser(
        "check",
        parents=[parent_parser],
        help="Verify expected titles of playlists and tracks against Spotify and YouTube"
    )
    check_parser.add_argument("csv_file", help="Path to playlists/tracks CSV file")

    # 4. print
    print_parser = subparsers.add_parser(
        "print",
        parents=[parent_parser],
        help="Parse and print the local CSV sheet with track validation"
    )
    print_parser.add_argument("csv_file", help="Path to playlists/tracks CSV file")

    # 5. dump
    dump_parser = subparsers.add_parser(
        "dump",
        parents=[parent_parser],
        help="Dump Spotify or YouTube playlist/album tracks to CSV directive format"
    )
    dump_parser.add_argument(
        "playlist_or_album",
        help="Spotify/YouTube playlist or album ID / URL"
    )

    # 6. test-keys
    test_keys_parser = subparsers.add_parser(
        "test-keys",
        parents=[parent_parser],
        help="Test Spotify and/or YouTube API connection and credentials"
    )
    test_keys_parser.add_argument(
        "--local",
        action="store_true",
        help="Verify local credentials file structure only"
    )

    # 7. clear-keys
    subparsers.add_parser(
        "clear-keys",
        parents=[parent_parser],
        help="Delete stored Spotify and/or YouTube credentials"
    )

    # 8. clear-cache
    subparsers.add_parser(
        "clear-cache",
        parents=[parent_parser],
        help="Purge local track metadata cache"
    )

    # 9. clear-all
    subparsers.add_parser(
        "clear-all",
        parents=[parent_parser],
        help="Delete stored credentials and purge cache"
    )

    parsed = parser.parse_args(args)
    return parsed
