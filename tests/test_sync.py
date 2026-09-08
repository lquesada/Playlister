import unittest
from unittest.mock import patch, MagicMock
import io
import sys
from playlister_lib.main import main
from playlister_lib.parser import parse_csv_sheet

class StatefulMockSpotify:
    def __init__(self):
        # playlist_id -> { "name": name, "tracks": [track_ids] }
        self.playlists = {
            "p1": {"name": "Hits 2026", "tracks": ["t1", "t2"]},
            "p2": {"name": "Soft Pop", "tracks": ["t3", "t1"]}
        }
        # album_id -> { "name": name, "tracks": [track_ids] }
        self.albums = {
            "a1": {"name": "Hits Album 2026", "tracks": ["t1", "t2"]}
        }
        # track_id -> name
        self.tracks_meta = {
            "t1": "Song One",
            "t2": "Song Two",
            "t3": "Song Three",
            "t4": "Song Four"
        }

    def playlist(self, playlist_id, fields=None):
        if playlist_id not in self.playlists:
            raise Exception("Playlist not found")
        return {"name": self.playlists[playlist_id]["name"]}

    def playlist_tracks(self, playlist_id):
        if playlist_id not in self.playlists:
            raise Exception("Playlist not found")
        track_ids = self.playlists[playlist_id]["tracks"]
        items = []
        for tid in track_ids:
            items.append({
                "track": {
                    "id": tid,
                    "name": self.tracks_meta.get(tid, tid),
                    "duration_ms": 180000
                }
            })
        return {"items": items, "next": None}

    def track(self, track_id):
        return {
            "name": self.tracks_meta.get(track_id, track_id),
            "duration_ms": 180000
        }

    def playlist_remove_all_occurrences_of_items(self, playlist_id, items):
        for item in items:
            while item in self.playlists[playlist_id]["tracks"]:
                self.playlists[playlist_id]["tracks"].remove(item)
        return {"status": "ok"}

    def playlist_add_items(self, playlist_id, items):
        self.playlists[playlist_id]["tracks"].extend(items)
        return {"status": "ok"}

    def playlist_reorder_items(self, playlist_id, range_start, insert_before):
        tracks = self.playlists[playlist_id]["tracks"]
        item = tracks.pop(range_start)
        tracks.insert(insert_before, item)
        return {"status": "ok"}

    def album(self, album_id, market="from_token"):
        if album_id not in self.albums:
            raise Exception("Album not found")
        return {"name": self.albums[album_id]["name"]}

    def album_tracks(self, album_id, limit=50, offset=0, market="from_token"):
        if album_id not in self.albums:
            raise Exception("Album not found")
        track_ids = self.albums[album_id]["tracks"]
        items = []
        for tid in track_ids:
            items.append({
                "id": tid,
                "name": self.tracks_meta.get(tid, tid),
                "duration_ms": 180000
            })
        return {"items": items, "next": None}

    def current_user(self):
        return {"display_name": "Test User", "id": "test_user_id"}

class TestSync(unittest.TestCase):
    def setUp(self):
        self.sleep_patcher = patch('time.sleep', return_value=None)
        self.mock_sleep = self.sleep_patcher.start()
        # Skip patching resolve_key_path for tests that test directory/file deletion
        if self._testMethodName in ("test_clear_keys_and_clear_cache_subcommand", "test_delete_key_execution"):
            self.resolve_patcher = None
            return
        import tempfile
        self.tmp_key_dir = tempfile.mkdtemp()
        self.resolve_patcher = patch('playlister_lib.key_store.resolve_key_path', return_value=self.tmp_key_dir)
        self.mock_resolve = self.resolve_patcher.start()

    def tearDown(self):
        if hasattr(self, 'sleep_patcher') and self.sleep_patcher:
            self.sleep_patcher.stop()
        if hasattr(self, 'resolve_patcher') and self.resolve_patcher:
            self.resolve_patcher.stop()
            import shutil
            shutil.rmtree(self.tmp_key_dir)

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_api_key', return_value='mock_key')
    @patch('builtins.input', return_value='y')
    @patch('spotipy.Spotify')
    def test_sync_execution(self, mock_spotify_cls, mock_input, mock_key, mock_args):
        # Configure mock arguments
        mock_args.return_value = MagicMock(
            csv_file="dummy.csv",
            execute=True,
            local=False,
            auto_approve=False,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False
        )
        
        # Initialize stateful mock
        spotify_mock = StatefulMockSpotify()
        mock_spotify_cls.return_value = spotify_mock
        
        # CSV file content:
        # p1 should have: t1 at 1, t3 at 2. (Current is: t1, t2)
        # So: remove t2, add t3, reorder to t1, t3.
        csv_data = (
            ",#playlist:p1 #title:<Hits 2026>\n"
            "#track:t1 #title:<Song One>,1\n"
            "#track:t2 #title:<Song Two> #ignore,2\n" # t2 is ignored
            "#track:t3 #title:<Song Three>,2\n"
        )
        
        with patch('builtins.open', return_value=io.StringIO(csv_data)):
            main()
            
        # Check final state on mock Spotify
        # p1 tracks should now be exactly ['t1', 't3']
        self.assertEqual(spotify_mock.playlists["p1"]["tracks"], ["t1", "t3"])

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_api_key', return_value='mock_key')
    @patch('spotipy.Spotify')
    def test_sync_duplicate_error(self, mock_spotify_cls, mock_key, mock_args):
        mock_args.return_value = MagicMock(
            csv_file="dummy.csv",
            execute=True,
            local=False,
            auto_approve=False,
            remove_dupes=False,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False
        )
        
        spotify_mock = StatefulMockSpotify()
        spotify_mock.playlists["p1"]["tracks"] = ["t1", "t1", "t2"]
        mock_spotify_cls.return_value = spotify_mock
        
        csv_data = (
            ",#playlist:p1 #title:<Hits 2026>\n"
            "#track:t1 #title:<Song One>,1\n"
            "#track:t2 #title:<Song Two>,2\n"
        )
        
        with patch('builtins.open', return_value=io.StringIO(csv_data)):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_api_key', return_value='mock_key')
    @patch('builtins.input', return_value='y')
    @patch('spotipy.Spotify')
    def test_sync_duplicate_cleanup(self, mock_spotify_cls, mock_input, mock_key, mock_args):
        mock_args.return_value = MagicMock(
            csv_file="dummy.csv",
            execute=True,
            local=False,
            auto_approve=False,
            remove_dupes=True,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False
        )
        
        spotify_mock = StatefulMockSpotify()
        spotify_mock.playlists["p1"]["tracks"] = ["t1", "t1", "t2"]
        mock_spotify_cls.return_value = spotify_mock
        
        csv_data = (
            ",#playlist:p1 #title:<Hits 2026>\n"
            "#track:t1 #title:<Song One>,1\n"
            "#track:t2 #title:<Song Two>,2\n"
        )
        
        with patch('builtins.open', return_value=io.StringIO(csv_data)):
            main()
            
        self.assertEqual(spotify_mock.playlists["p1"]["tracks"], ["t1", "t2"])

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_api_key', return_value='mock_key')
    @patch('spotipy.Spotify')
    def test_dump_execution(self, mock_spotify_cls, mock_key, mock_args):
        mock_args.return_value = MagicMock(
            csv_file=None,
            execute=False,
            local=False,
            auto_approve=False,
            remove_dupes=False,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump="https://open.spotify.com/playlist/p1?si=xyz",
            delete_key=False
        )
        
        spotify_mock = StatefulMockSpotify()
        mock_spotify_cls.return_value = spotify_mock
        
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
            
        expected = (
            "#playlist:p1 #title:<Hits 2026>\n\n"
            "#track:t1 #title:<Song One>\n"
            "#track:t2 #title:<Song Two>\n"
        )
        self.assertEqual(output, expected)

    @patch('playlister_lib.main.parse_args')
    def test_delete_key_execution(self, mock_args):
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_key_file = os.path.join(tmpdir, ".playlister_temp")
            with open(temp_key_file, "w") as f:
                f.write("dummy credentials")
            self.assertTrue(os.path.exists(temp_key_file))
            
            mock_args.return_value = MagicMock(
                csv_file=None,
                execute=False,
                local=False,
                auto_approve=False,
                remove_dupes=False,
                test_api_key=False,
                key_dir=temp_key_file,
                no_store_key=False,
                dump=None,
                delete_key=True
            )
            
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            self.assertFalse(os.path.exists(temp_key_file))

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_api_key', return_value='mock_key')
    @patch('builtins.input', return_value='y')
    @patch('spotipy.Spotify')
    def test_sync_reorder_length_mismatch_guard(self, mock_spotify_cls, mock_input, mock_key, mock_args):
        mock_args.return_value = MagicMock(
            csv_file="dummy.csv",
            execute=True,
            local=False,
            auto_approve=False,
            remove_dupes=False,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False
        )
        
        # Initialize stateful mock
        spotify_mock = StatefulMockSpotify()
        # Mock playlist_add_items to do nothing, simulating Spotify delay or failure
        spotify_mock.playlist_add_items = MagicMock(return_value={"status": "ok"})
        mock_spotify_cls.return_value = spotify_mock
        
        csv_data = (
            ",#playlist:p1 #title:<Hits 2026>\n"
            "#track:t1 #title:<Song One>,1\n"
            "#track:t2 #title:<Song Two>,2\n"
            "#track:t3 #title:<Song Three>,3\n"
        )
        
        with patch('builtins.open', return_value=io.StringIO(csv_data)):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

    @patch('playlister_lib.main.parse_args')
    def test_local_validation(self, mock_args):
        mock_args.return_value = MagicMock(
            csv_file="dummy.csv",
            execute=False,
            local=True,
            auto_approve=False,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False
        )
        
        csv_data = (
            ",#playlist:p1 #title:<Hits 2026>\n"
            "#track:t1 #title:<Song One>,1\n"
            "#track:t2 #title:<Song Two>,2\n"
        )
        
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            with patch('builtins.open', return_value=io.StringIO(csv_data)):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, 0)
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        self.assertIn("Local validation completed. No errors found.", output)
        self.assertIn("Playlist [Spotify]: Hits 2026 (Local, 2 tracks)", output)

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_api_key', return_value='mock_key')
    @patch('spotipy.Spotify')
    def test_dry_run_online_diffing(self, mock_spotify_cls, mock_key, mock_args):
        mock_args.return_value = MagicMock(
            csv_file="dummy.csv",
            execute=False,
            local=False,
            auto_approve=False,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False
        )
        
        spotify_mock = StatefulMockSpotify()
        mock_spotify_cls.return_value = spotify_mock
        
        csv_data = (
            ",#playlist:p1 #title:<Hits 2026>\n"
            "#track:t1 #title:<Song One>,1\n"
            "#track:t3 #title:<Song Three>,2\n"
        )
        
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            with patch('builtins.open', return_value=io.StringIO(csv_data)):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, 0)
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        self.assertIn("Dry run completed. No changes applied.", output)
        self.assertIn("Proposed changes:", output)
        self.assertIn("Remove:", output)
        self.assertIn("Add:", output)

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_api_key', return_value='mock_key')
    @patch('spotipy.Spotify')
    def test_sync_execution_auto_approve(self, mock_spotify_cls, mock_key, mock_args):
        mock_args.return_value = MagicMock(
            csv_file="dummy.csv",
            execute=True,
            local=False,
            auto_approve=True,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False
        )
        
        spotify_mock = StatefulMockSpotify()
        mock_spotify_cls.return_value = spotify_mock
        
        csv_data = (
            ",#playlist:p1 #title:<Hits 2026>\n"
            "#track:t1 #title:<Song One>,1\n"
            "#track:t3 #title:<Song Three>,2\n"
        )
        
        # Should not prompt for input due to auto_approve=True
        with patch('builtins.open', return_value=io.StringIO(csv_data)):
            main()
            
        self.assertEqual(spotify_mock.playlists["p1"]["tracks"], ["t1", "t3"])

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_api_key', return_value='mock_key')
    @patch('spotipy.Spotify')
    def test_dump_album_execution(self, mock_spotify_cls, mock_key, mock_args):
        mock_args.return_value = MagicMock(
            csv_file=None,
            execute=False,
            local=False,
            auto_approve=False,
            remove_dupes=False,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump="https://open.spotify.com/album/a1?si=xyz",
            delete_key=False
        )
        
        spotify_mock = StatefulMockSpotify()
        mock_spotify_cls.return_value = spotify_mock
        
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
            
        expected = (
            "#album:a1 #title:<Hits Album 2026>\n\n"
            "#track:t1 #title:<Song One>\n"
            "#track:t2 #title:<Song Two>\n"
        )
        self.assertEqual(output, expected)

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_api_key', return_value='mock_key')
    @patch('spotipy.Spotify')
    def test_check_all_success(self, mock_spotify_cls, mock_key, mock_args):
        mock_args.return_value = MagicMock(
            csv_file="dummy.csv",
            execute=False,
            local=False,
            auto_approve=False,
            remove_dupes=False,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False,
            check_all=True
        )
        spotify_mock = StatefulMockSpotify()
        mock_spotify_cls.return_value = spotify_mock
        
        csv_data = (
            ",#playlist:p1 #title:<Hits 2026>\n"
            "#track:t1 #title:<Song One>,1\n"
            "#track:t4 #title:<Song Four>,\n"
        )
        
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            with patch('builtins.open', return_value=io.StringIO(csv_data)):
                with self.assertRaises(SystemExit) as cm:
                    main()
            self.assertEqual(cm.exception.code, 0)
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
            
        self.assertIn("All playlist and track titles verified successfully.", output)

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_api_key', return_value='mock_key')
    @patch('spotipy.Spotify')
    def test_check_all_playlist_title_mismatch(self, mock_spotify_cls, mock_key, mock_args):
        mock_args.return_value = MagicMock(
            csv_file="dummy.csv",
            execute=False,
            local=False,
            auto_approve=False,
            remove_dupes=False,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False,
            check_all=True
        )
        spotify_mock = StatefulMockSpotify()
        mock_spotify_cls.return_value = spotify_mock
        
        csv_data = (
            ",#playlist:p1 #title:<Wrong Playlist Title>\n"
            "#track:t1 #title:<Song One>,1\n"
        )
        
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            with patch('builtins.open', return_value=io.StringIO(csv_data)):
                with self.assertRaises(SystemExit) as cm:
                    main()
            self.assertEqual(cm.exception.code, 1)
            error_output = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr
            
        self.assertIn("Playlist title mismatch for ID 'p1'", error_output)

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_api_key', return_value='mock_key')
    @patch('spotipy.Spotify')
    def test_check_all_unused_track_title_mismatch(self, mock_spotify_cls, mock_key, mock_args):
        mock_args.return_value = MagicMock(
            csv_file="dummy.csv",
            execute=False,
            local=False,
            auto_approve=False,
            remove_dupes=False,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False,
            check_all=True
        )
        spotify_mock = StatefulMockSpotify()
        mock_spotify_cls.return_value = spotify_mock
        
        csv_data = (
            ",#playlist:p1 #title:<Hits 2026>\n"
            "#track:t1 #title:<Song One>,1\n"
            "#track:t4 #title:<Wrong Track Title>,\n"
        )
        
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            with patch('builtins.open', return_value=io.StringIO(csv_data)):
                with self.assertRaises(SystemExit) as cm:
                    main()
            self.assertEqual(cm.exception.code, 1)
            error_output = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr
            
        self.assertIn("Track title mismatch for ID 't4'", error_output)

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_api_key', return_value='mock_key')
    @patch('spotipy.Spotify')
    def test_test_api_key_online_success(self, mock_spotify_cls, mock_key, mock_args):
        mock_args.return_value = MagicMock(
            csv_file=None,
            execute=False,
            local=False,
            auto_approve=False,
            remove_dupes=False,
            test_api_key=True,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False
        )
        spotify_mock = StatefulMockSpotify()
        mock_spotify_cls.return_value = spotify_mock
        
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
            
        self.assertIn("Credentials verification: success (online check passed for user: Test User)", output)

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_api_key', return_value='mock_key')
    @patch('spotipy.Spotify')
    def test_test_api_key_online_failure(self, mock_spotify_cls, mock_key, mock_args):
        mock_args.return_value = MagicMock(
            csv_file=None,
            execute=False,
            local=False,
            auto_approve=False,
            remove_dupes=False,
            test_api_key=True,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False
        )
        spotify_mock = StatefulMockSpotify()
        spotify_mock.current_user = MagicMock(side_effect=Exception("API connection error"))
        mock_spotify_cls.return_value = spotify_mock
        
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)
            error_output = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr
            
        self.assertIn("Credentials verification failed online: API connection error", error_output)

    @patch('playlister_lib.main.parse_args')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=True)
    @patch('shutil.rmtree')
    @patch('playlister_lib.key_store.clear_cache_file')
    def test_clear_keys_and_clear_cache_subcommand(self, mock_clear_cache, mock_rmtree, mock_isdir, mock_exists, mock_args):
        mock_args.return_value = MagicMock(
            command="clear-all",
            csv_file=None,
            dry_run=False,
            execute=False,
            auto_approve=False,
            remove_dupes=False,
            test_api_key=False,
            key_dir="/dummy/dir",
            no_store_key=False,
            dump=None,
            delete_key=True,
            clear_cache=True
        )
        
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 0)
        mock_rmtree.assert_called_once_with("/dummy/dir")
        mock_clear_cache.assert_called_once_with("/dummy/dir")

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_api_key', return_value='mock_key')
    @patch('spotipy.Spotify')
    def test_sync_with_unicode(self, mock_spotify_cls, mock_key, mock_args):
        mock_args.return_value = MagicMock(
            command="diff",
            csv_file="dummy.csv",
            dry_run=True,
            execute=False,
            auto_approve=False,
            remove_dupes=False,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False
        )
        # Playlist and tracks with UTF-8 / Emoji names
        csv_data = (
            ",#playlist:p1 #title:<Café Music ☕>\n"
            "#track:t1 #title:<Bossa Nova 🎶>,1\n"
        )
        spotify_mock = StatefulMockSpotify()
        spotify_mock.playlists = {
            "p1": {"name": "Café Music ☕", "tracks": ["t1"]}
        }
        spotify_mock.tracks_meta = {
            "t1": "Bossa Nova 🎶"
        }
        mock_spotify_cls.return_value = spotify_mock
        
        with patch('builtins.open', return_value=io.StringIO(csv_data)):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_api_key', return_value='mock_key')
    @patch('spotipy.Spotify')
    def test_sync_with_missing_items_key(self, mock_spotify_cls, mock_key, mock_args):
        mock_args.return_value = MagicMock(
            command="diff",
            csv_file="dummy.csv",
            dry_run=True,
            execute=False,
            auto_approve=False,
            remove_dupes=False,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False
        )
        # Use Real Title "Hits 2026" from StatefulMockSpotify for p1 to avoid title mismatch
        csv_data = (
            ",#playlist:p1 #title:<Hits 2026>\n"
            "#track:t1 #title:<Song One>,1\n"
        )
        spotify_mock = StatefulMockSpotify()
        # Mock playlist_tracks returning a dict without "items" key
        spotify_mock.playlist_tracks = MagicMock(return_value={})
        mock_spotify_cls.return_value = spotify_mock
        
        with patch('builtins.open', return_value=io.StringIO(csv_data)):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_api_key', return_value='mock_key')
    @patch('builtins.input', return_value='y')
    @patch('spotipy.Spotify')
    def test_duplicate_tracks_removal_workflow(self, mock_spotify_cls, mock_input, mock_key, mock_args):
        mock_args.return_value = MagicMock(
            command="push",
            csv_file="dummy.csv",
            dry_run=False,
            execute=True,
            auto_approve=True,
            remove_dupes=True,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False
        )
        # Use real title "Hits 2026" and tracks matching p1
        csv_data = (
            ",#playlist:p1 #title:<Hits 2026>\n"
            "#track:t1 #title:<Song One>,1\n"
            "#track:t2 #title:<Song Two>,2\n"
        )
        spotify_mock = StatefulMockSpotify()
        # Playlist initially contains duplicate of t1
        spotify_mock.playlists = {
            "p1": {"name": "Hits 2026", "tracks": ["t1", "t1", "t2"]}
        }
        spotify_mock.tracks_meta = {
            "t1": "Song One",
            "t2": "Song Two"
        }
        mock_spotify_cls.return_value = spotify_mock
        
        with patch('builtins.open', return_value=io.StringIO(csv_data)):
            main()
            
        # Verify duplicates are removed and final playlist is exactly ['t1', 't2']
        self.assertEqual(spotify_mock.playlists["p1"]["tracks"], ["t1", "t2"])

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_api_key', return_value='mock_key')
    @patch('builtins.input')
    @patch('spotipy.Spotify')
    def test_sync_multiple_playlists_interactive(self, mock_spotify_cls, mock_input, mock_key, mock_args):
        mock_args.return_value = MagicMock(
            command="push",
            csv_file="dummy.csv",
            dry_run=False,
            execute=True,
            auto_approve=False,
            remove_dupes=False,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False
        )
        # Mock inputs: 'y' for p1, 'n' for p2
        mock_input.side_effect = ['y', 'n']

        spotify_mock = StatefulMockSpotify()
        # Both p1 and p2 exist and need changes
        spotify_mock.playlists = {
            "p1": {"name": "Hits 2026", "tracks": ["t1", "t2"]},
            "p2": {"name": "Soft Pop", "tracks": ["t3", "t1"]}
        }
        mock_spotify_cls.return_value = spotify_mock

        csv_data = (
            ",#playlist:p1 #title:<Hits 2026>,#playlist:p2 #title:<Soft Pop>\n"
            "#track:t1 #title:<Song One>,1,ignore\n"
            "#track:t2 #title:<Song Two>,ignore,ignore\n"
            "#track:t3 #title:<Song Three>,ignore,1\n"
        )

        # Intercept stdout at input calls to verify sequential prompting
        stdout_records = []
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            def mock_input_side_effect(prompt):
                stdout_records.append(sys.stdout.getvalue())
                if len(stdout_records) == 1:
                    return 'y'
                return 'n'
            
            mock_input.side_effect = mock_input_side_effect
            
            with patch('builtins.open', return_value=io.StringIO(csv_data)):
                main()
        except SystemExit as e:
            self.assertEqual(e.code, 0)
        finally:
            sys.stdout = old_stdout

        # Verify that when p1 was prompted, p2's diff had NOT been printed yet
        self.assertEqual(len(stdout_records), 2)
        self.assertIn("Playlist [Spotify]: Hits 2026", stdout_records[0])
        self.assertNotIn("Playlist [Spotify]: Soft Pop", stdout_records[0])

        # Verify that when p2 was prompted, p1's sync was complete/outputted, and p2's diff was printed
        self.assertIn("Playlist [Spotify]: Hits 2026", stdout_records[1])
        self.assertIn("Playlist [Spotify]: Soft Pop", stdout_records[1])
        self.assertIn("Playlist [Spotify] Hits 2026 successfully synced.", stdout_records[1])

        # p1 should be updated (remove t2, so tracks is ['t1'])
        self.assertEqual(spotify_mock.playlists["p1"]["tracks"], ["t1"])
        # p2 should NOT be updated (tracks remain ['t3', 't1'])
        self.assertEqual(spotify_mock.playlists["p2"]["tracks"], ["t3", "t1"])


class StatefulMockYouTube:
    def __init__(self):
        self.playlists = {
            "PL1": {"name": "YT Hits 2026", "items": [
                {"item_id": "it1", "video_id": "vid1", "title": "Song One Video"},
                {"item_id": "it2", "video_id": "vid2", "title": "Song Two Video"}
            ]}
        }
        self.video_meta = {
            "vid1": {"name": "Song One Video", "duration_ms": 180000},
            "vid2": {"name": "Song Two Video", "duration_ms": 180000},
            "vid3": {"name": "Song Three Video", "duration_ms": 180000}
        }
        self._counter = 10

    def get_playlist(self, playlist_id):
        if playlist_id not in self.playlists:
            raise Exception("Playlist not found")
        return {"id": playlist_id, "name": self.playlists[playlist_id]["name"]}

    def get_playlist_items(self, playlist_id):
        if playlist_id not in self.playlists:
            raise Exception("Playlist not found")
        return list(self.playlists[playlist_id]["items"])

    def get_video_details(self, video_ids):
        return {vid: self.video_meta.get(vid, {"name": vid, "duration_ms": 180000}) for vid in video_ids}

    def remove_playlist_item(self, playlist_item_id):
        for p in self.playlists.values():
            p["items"] = [it for it in p["items"] if it["item_id"] != playlist_item_id]

    def add_playlist_item(self, playlist_id, video_id, position=None):
        self._counter += 1
        item_id = f"it{self._counter}"
        item = {
            "item_id": item_id,
            "video_id": video_id,
            "title": self.video_meta.get(video_id, {}).get("name", video_id)
        }
        if position is not None:
            self.playlists[playlist_id]["items"].insert(position, item)
        else:
            self.playlists[playlist_id]["items"].append(item)

    def reorder_playlist_item(self, playlist_item_id, playlist_id, video_id, position):
        items = self.playlists[playlist_id]["items"]
        found_idx = None
        for idx, it in enumerate(items):
            if it["item_id"] == playlist_item_id:
                found_idx = idx
                break
        if found_idx is not None:
            it = items.pop(found_idx)
            items.insert(position, it)

    def get_current_user_info(self):
        return {"id": "test_channel", "display_name": "Test Channel"}


class TestYouTubeSync(unittest.TestCase):
    def setUp(self):
        self.sleep_patcher = patch('time.sleep', return_value=None)
        self.mock_sleep = self.sleep_patcher.start()

    def tearDown(self):
        if hasattr(self, 'sleep_patcher') and self.sleep_patcher:
            self.sleep_patcher.stop()

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_youtube_api_key', return_value='mock_yt_key')
    @patch('playlister_lib.main.YouTubeClient')
    def test_youtube_diff_dry_run(self, mock_yt_cls, mock_key, mock_args):
        yt_mock = StatefulMockYouTube()
        mock_yt_cls.return_value = yt_mock

        mock_args.return_value = MagicMock(
            command="diff",
            csv_file="dummy_yt.csv",
            dry_run=True,
            execute=False,
            auto_approve=False,
            remove_dupes=False,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False,
            service="youtube",
            spotify=False,
            youtube=True
        )

        csv_data = (
            ",#youtubeplaylist:PL1 #youtubetitle:<YT Hits 2026>\n"
            "#youtubetrack:vid1 #youtubetitle:<Song One Video>,1\n"
            "#youtubetrack:vid3 #youtubetitle:<Song Three Video>,2\n"
        )

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            with patch('builtins.open', return_value=io.StringIO(csv_data)):
                main()
        except SystemExit as e:
            self.assertEqual(e.code, 0)
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        self.assertIn("Playlist [YouTube]: YT Hits 2026", output)
        self.assertIn("- Remove:", output)
        self.assertIn("Song Two Video (vid2)", output)
        self.assertIn("+ Add:", output)
        self.assertIn("Song Three Video (vid3)", output)
        self.assertIn("Dry run completed. No changes applied.", output)

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_youtube_api_key', return_value='mock_yt_key')
    @patch('playlister_lib.main.YouTubeClient')
    def test_youtube_push_apply(self, mock_yt_cls, mock_key, mock_args):
        yt_mock = StatefulMockYouTube()
        mock_yt_cls.return_value = yt_mock

        mock_args.return_value = MagicMock(
            command="push",
            csv_file="dummy_yt.csv",
            dry_run=False,
            execute=True,
            auto_approve=True,
            remove_dupes=False,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False,
            service="youtube",
            spotify=False,
            youtube=True
        )

        # Target: vid1 at 1, vid3 at 2 (removes vid2, adds vid3)
        csv_data = (
            ",#youtubeplaylist:PL1 #youtubetitle:<YT Hits 2026>\n"
            "#youtubetrack:vid1 #youtubetitle:<Song One Video>,1\n"
            "#youtubetrack:vid3 #youtubetitle:<Song Three Video>,2\n"
        )

        with patch('builtins.open', return_value=io.StringIO(csv_data)):
            main()

        final_vids = [it["video_id"] for it in yt_mock.playlists["PL1"]["items"]]
        self.assertEqual(final_vids, ["vid1", "vid3"])

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_youtube_api_key', return_value='mock_yt_key')
    @patch('playlister_lib.main.YouTubeClient')
    def test_youtube_dump(self, mock_yt_cls, mock_key, mock_args):
        yt_mock = StatefulMockYouTube()
        mock_yt_cls.return_value = yt_mock

        mock_args.return_value = MagicMock(
            command="dump",
            playlist_or_album="https://www.youtube.com/playlist?list=PL1",
            dump="https://www.youtube.com/playlist?list=PL1",
            key_dir=None,
            no_store_key=False,
            service="youtube",
            spotify=False,
            youtube=True
        )

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            main()
        except SystemExit as e:
            self.assertEqual(e.code, 0)
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        self.assertIn("#youtubeplaylist:PL1 #youtubetitle:<YT Hits 2026>", output)
        self.assertIn("#youtubetrack:vid1 #youtubetitle:<Song One Video>", output)
        self.assertIn("#youtubetrack:vid2 #youtubetitle:<Song Two Video>", output)

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_youtube_api_key', return_value='mock_yt_key')
    @patch('playlister_lib.main.YouTubeClient')
    def test_youtube_push_eventual_consistency_step3_recovery(self, mock_yt_cls, mock_key, mock_args):
        yt_mock = StatefulMockYouTube()
        mock_yt_cls.return_value = yt_mock

        mock_args.return_value = MagicMock(
            command="push",
            csv_file="dummy_yt.csv",
            dry_run=False,
            execute=True,
            auto_approve=True,
            remove_dupes=False,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False,
            service="youtube",
            spotify=False,
            youtube=True
        )

        # Target: vid1 at 1, vid3 at 2 (removes vid2, adds vid3)
        csv_data = (
            ",#youtubeplaylist:PL1 #youtubetitle:<YT Hits 2026>\n"
            "#youtubetrack:vid1 #youtubetitle:<Song One Video>,1\n"
            "#youtubetrack:vid3 #youtubetitle:<Song Three Video>,2\n"
        )

        # Simulate eventual consistency in Step 3:
        # Call 1 (initial diff): normal (returns vid1, vid2)
        # Call 2 (step 3 after add): simulates lagging replica returning only vid1 (count 1 instead of 2)
        # Call 3 (step 3 retry): replica catches up, returns vid1, vid3 (count 2)
        # Call 4 (step 4 verify): returns vid1, vid3
        orig_get_items = yt_mock.get_playlist_items
        call_count = [0]
        def lagging_get_items(playlist_id):
            call_count[0] += 1
            real_items = orig_get_items(playlist_id)
            if call_count[0] == 2:
                # Simulate lagging read endpoint missing the newly added item
                return [it for it in real_items if it["video_id"] != "vid3"]
            return real_items

        yt_mock.get_playlist_items = lagging_get_items

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            with patch('builtins.open', return_value=io.StringIO(csv_data)):
                main()
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        self.assertIn("Waiting for YouTube playlist changes to propagate...", output)
        self.assertIn("Playlist [YouTube] YT Hits 2026 successfully synced.", output)
        final_vids = [it["video_id"] for it in orig_get_items("PL1")]
        self.assertEqual(final_vids, ["vid1", "vid3"])

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_youtube_api_key', return_value='mock_yt_key')
    @patch('playlister_lib.main.YouTubeClient')
    def test_youtube_push_eventual_consistency_step4_recovery(self, mock_yt_cls, mock_key, mock_args):
        yt_mock = StatefulMockYouTube()
        mock_yt_cls.return_value = yt_mock

        mock_args.return_value = MagicMock(
            command="push",
            csv_file="dummy_yt.csv",
            dry_run=False,
            execute=True,
            auto_approve=True,
            remove_dupes=False,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False,
            service="youtube",
            spotify=False,
            youtube=True
        )

        # Target: reorder vid2 to position 1, vid1 to position 2
        csv_data = (
            ",#youtubeplaylist:PL1 #youtubetitle:<YT Hits 2026>\n"
            "#youtubetrack:vid2 #youtubetitle:<Song Two Video>,1\n"
            "#youtubetrack:vid1 #youtubetitle:<Song One Video>,2\n"
        )

        # Simulate eventual consistency in Step 4:
        # Call 1 (initial diff): returns vid1, vid2
        # Call 2 (step 3 reorder check): returns vid1, vid2 (reordering runs to move vid2)
        # Call 3 (step 4 verification first attempt): returns stale pre-reorder order [vid1, vid2]
        # Call 4 (step 4 verification retry): replica catches up, returns reordered [vid2, vid1]
        orig_get_items = yt_mock.get_playlist_items
        call_count = [0]
        def lagging_get_items(playlist_id):
            call_count[0] += 1
            real_items = orig_get_items(playlist_id)
            if call_count[0] == 3:
                # Simulate stale read endpoint returning pre-reorder order
                return list(reversed(real_items))
            return real_items

        yt_mock.get_playlist_items = lagging_get_items

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            with patch('builtins.open', return_value=io.StringIO(csv_data)):
                main()
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        self.assertIn("Waiting for YouTube playlist changes to propagate...", output)
        self.assertIn("Playlist [YouTube] YT Hits 2026 successfully synced.", output)
        final_vids = [it["video_id"] for it in orig_get_items("PL1")]
        self.assertEqual(final_vids, ["vid2", "vid1"])

    @patch('playlister_lib.main.parse_args')
    @patch('playlister_lib.main.get_youtube_api_key', return_value='mock_yt_key')
    @patch('playlister_lib.main.YouTubeClient')
    def test_youtube_push_eventual_consistency_exhausted(self, mock_yt_cls, mock_key, mock_args):
        yt_mock = StatefulMockYouTube()
        mock_yt_cls.return_value = yt_mock

        mock_args.return_value = MagicMock(
            command="push",
            csv_file="dummy_yt.csv",
            dry_run=False,
            execute=True,
            auto_approve=True,
            remove_dupes=False,
            test_api_key=False,
            key_dir=None,
            no_store_key=False,
            dump=None,
            delete_key=False,
            service="youtube",
            spotify=False,
            youtube=True
        )

        csv_data = (
            ",#youtubeplaylist:PL1 #youtubetitle:<YT Hits 2026>\n"
            "#youtubetrack:vid1 #youtubetitle:<Song One Video>,1\n"
            "#youtubetrack:vid3 #youtubetitle:<Song Three Video>,2\n"
        )

        # Mock add_playlist_item to do nothing, simulating permanent failure to add
        yt_mock.add_playlist_item = MagicMock(return_value={"id": "dummy"})

        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            with patch('builtins.open', return_value=io.StringIO(csv_data)):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, 1)
        finally:
            err_output = sys.stderr.getvalue()
            sys.stderr = old_stderr

        self.assertIn("Warning: Current playlist tracks count (1) does not match target count (2)", err_output)
        self.assertIn("Error: Sync verification failed for playlist 'PL1'", err_output)


if __name__ == "__main__":
    unittest.main()

