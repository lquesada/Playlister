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
        # Skip patching resolve_key_path for tests that test directory/file deletion
        if self._testMethodName in ("test_clear_keys_and_clear_cache_subcommand", "test_delete_key_execution"):
            self.resolve_patcher = None
            return
        import tempfile
        self.tmp_key_dir = tempfile.mkdtemp()
        self.resolve_patcher = patch('playlister_lib.key_store.resolve_key_path', return_value=self.tmp_key_dir)
        self.mock_resolve = self.resolve_patcher.start()

    def tearDown(self):
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
        self.assertIn("Playlist: Hits 2026 (Local, 2 tracks)", output)

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

if __name__ == "__main__":
    unittest.main()
