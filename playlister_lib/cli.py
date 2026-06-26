import argparse

def parse_args(args=None):
    epilog_text = """
CSV Sheet Structure:
  - Row 0 (starting at Column 1) defines the PLAYLISTS.
  - Column 0 (starting at Row 1) defines the TRACKS.
  - Inner cells contain positive integers (1-based order) or '#no'.

Playlist Fields & Directives (Row 0 cells):
  Multiple space-separated directives can be specified in each cell:
  - #playlist:<ID_or_URL>       - (Required) Spotify playlist ID or URL.
  - #title:<EXPECTED_TITLE>     - (Optional) Expected title. Quotes allowed: <Title>, @Title@, !Title!. Mismatches trigger errors.
  - #allowmissing               - (Optional) Allows gaps/missing sequence numbers.
  - #allowinvalid               - (Optional) Invalid cell inputs fallback to '#no' instead of raising an error.
  - #strict                     - (Optional) Empty cells raise an error instead of falling back to '#no'.
  - #ignore                     - (Optional) Ignores this playlist completely.

Track Fields & Directives (Column 0 cells):
  Multiple space-separated directives can be specified in each cell:
  - #track:<ID_or_URL>          - (Required) Spotify track ID or URL.
  - #title:<EXPECTED_TITLE>     - (Optional) Expected title. Quotes allowed: <Title>, @Title@, !Title!. Mismatches trigger errors.
  - #ignore                     - (Optional) Ignores this track completely.
"""

    # Common parent parser for global/root options
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "--key-dir", "--key_dir",
        default=None,
        help="Alternative directory for Spotify credentials and cache storage"
    )
    parent_parser.add_argument(
        "--no-store-key", "--no_store_key",
        action="store_true",
        help="Do not store credentials in the credentials directory"
    )

    parser = argparse.ArgumentParser(
        description="Spotify Playlister CSV manager.",
        epilog=epilog_text,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Subcommand to run")

    # 1. diff
    diff_parser = subparsers.add_parser(
        "diff",
        parents=[parent_parser],
        help="Calculate diff between CSV sheet and Spotify playlists (dry run)"
    )
    diff_parser.add_argument("csv_file", help="Path to playlists/tracks CSV file")

    # 2. push
    push_parser = subparsers.add_parser(
        "push",
        parents=[parent_parser],
        help="Apply CSV sheet changes to Spotify"
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
        help="Verify expected titles of playlists and tracks against Spotify"
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
        help="Dump Spotify playlist/album tracks to CSV directive format"
    )
    dump_parser.add_argument(
        "playlist_or_album",
        help="Spotify playlist or album ID / URL"
    )

    # 6. test-keys
    test_keys_parser = subparsers.add_parser(
        "test-keys",
        parents=[parent_parser],
        help="Test Spotify API connection and credentials"
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
        help="Delete stored Spotify credentials"
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
