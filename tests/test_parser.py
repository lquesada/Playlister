import unittest
import io
from playlister_lib.parser import parse_csv_sheet, PlaylistData, TrackData, PlaylisterError

class TestParser(unittest.TestCase):
    def test_parse_success(self):
        csv_data = (
            ",#playlist:43TtjGF050gzkar4IPmsLN #title:<Playlist 1>,#playlist:https://open.spotify.com/playlist/abc123xyz #strict\n"
            "#track:3BDidzS8avudzMj1G9ZZaz #title:<Track 1>,1,#no\n"
            "#track:https://open.spotify.com/track/t2_id #title:@Track 2@,3,1\n"
            "#track:t3 #title:!Track 3! #ignore,4,2\n"
        )
        playlists, tracks, matrix = parse_csv_sheet(io.StringIO(csv_data))
        
        self.assertEqual(len(playlists), 2)
        self.assertEqual(playlists[0].id, "43TtjGF050gzkar4IPmsLN")
        self.assertEqual(playlists[0].title, "Playlist 1")
        self.assertFalse(playlists[0].strict)
        
        self.assertEqual(playlists[1].id, "abc123xyz")
        self.assertTrue(playlists[1].strict)
        
        # Ignored track should not be in tracks list
        self.assertEqual(len(tracks), 2)
        self.assertEqual(tracks[0].id, "3BDidzS8avudzMj1G9ZZaz")
        self.assertEqual(tracks[0].title, "Track 1")
        self.assertEqual(tracks[1].id, "t2_id")
        self.assertEqual(tracks[1].title, "Track 2")
        self.assertEqual(matrix["43TtjGF050gzkar4IPmsLN"]["3BDidzS8avudzMj1G9ZZaz"], 1)
        self.assertEqual(matrix["43TtjGF050gzkar4IPmsLN"]["t2_id"], 2)
        self.assertEqual(matrix["abc123xyz"]["3BDidzS8avudzMj1G9ZZaz"], "#no")
        self.assertEqual(matrix["abc123xyz"]["t2_id"], 1)


    def test_missing_playlist_id(self):
        csv_data = ",#playlist #title:<Playlist 1>\n#track:t1,1\n"
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data))
        self.assertIn("misses a valid playlist ID", str(ctx.exception))

    def test_ignore_column_without_playlist(self):
        csv_data = (
            ",#playlist:p1,todo,#playlist:p2 #ignore\n"
            "#track:t1,1,potato,#no\n"
        )
        playlists, tracks, matrix = parse_csv_sheet(io.StringIO(csv_data))
        self.assertEqual(len(playlists), 1)
        self.assertEqual(playlists[0].id, "p1")

    def test_missing_track_id(self):
        csv_data = ",#playlist:p1\n#title:<Track 1>,1\n"
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data))
        self.assertIn("misses a valid track ID", str(ctx.exception))

    def test_sequence_error_with_strict(self):
        # Gaps are not allowed under strict mode
        csv_data = (
            ",#playlist:p1 #strict\n"
            "#track:t1,1\n"
            "#track:t2,3\n"
        )
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data))
        self.assertIn("Sequence violation", str(ctx.exception))

    def test_sequence_success_without_strict(self):
        csv_data = (
            ",#playlist:p1\n"
            "#track:t1,1\n"
            "#track:t2,3\n"
        )
        playlists, tracks, matrix = parse_csv_sheet(io.StringIO(csv_data))
        self.assertEqual(matrix["p1"]["t1"], 1)
        self.assertEqual(matrix["p1"]["t2"], 2)

    def test_strict_mode_error(self):
        csv_data = (
            ",#playlist:p1 #strict\n"
            "#track:t1,1\n"
            "#track:t2,\n"
        )
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data))
        self.assertEqual("Strict violation at row 2 (track 't2') and column 1 (playlist 'p1'): empty cell.", str(ctx.exception))

    def test_allow_invalid_mode(self):
        # With strict, "potato" triggers an error
        csv_data = (
            ",#playlist:p1 #strict\n"
            "#track:t1,1\n"
            "#track:t2,potato\n"
        )
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data))
        self.assertEqual("Invalid input 'potato' at row 2 (track 't2') and column 1 (playlist 'p1').", str(ctx.exception))

        # Without strict, "potato" is treated as "#no"
        csv_data_ok = (
            ",#playlist:p1\n"
            "#track:t1,1\n"
            "#track:t2,potato\n"
        )
        playlists, tracks, matrix = parse_csv_sheet(io.StringIO(csv_data_ok))
        self.assertEqual(matrix["p1"]["t2"], "#no")

    def test_duplicate_order_positions(self):
        csv_data = (
            ",#playlist:p1 #strict\n"
            "#track:t1,1\n"
            "#track:t2,1\n"
        )
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data))
        self.assertEqual("Duplicate track order positions in playlist 'p1' at column 1", str(ctx.exception))

    def test_error_message_with_playlist_title(self):
        csv_data = (
            ",#playlist:p1 #title:<My Playlist> #strict\n"
            "#track:t1,1\n"
            "#track:t2,1\n"
        )
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data))
        self.assertEqual("Duplicate track order positions in playlist 'My Playlist' ('p1') at column 1", str(ctx.exception))

    def test_directives_order(self):
        # Directives in different orders should be parsed correctly
        csv_data = (
            ",#strict #title:<Hello> #playlist:p1\n"
            "#track:t1,1\n"
        )
        playlists, tracks, matrix = parse_csv_sheet(io.StringIO(csv_data))
        self.assertEqual(len(playlists), 1)
        self.assertEqual(playlists[0].id, "p1")
        self.assertEqual(playlists[0].title, "Hello")
        self.assertTrue(playlists[0].strict)

    def test_nested_brackets_in_title(self):
        csv_data = (
            ",#playlist:p1 #title:@Hello <world>!@\n"
            "#track:t1,1\n"
        )
        playlists, tracks, matrix = parse_csv_sheet(io.StringIO(csv_data))
        self.assertEqual(playlists[0].title, "Hello <world>!")

    def test_invalid_playlist_and_track_ids(self):
        # Playlist directive with no ID/colon
        csv_data = (
            ",#playlist\n"
            "#track:t1,1\n"
        )
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data))
        self.assertIn("misses a valid playlist ID", str(ctx.exception))

        # Track directive with no ID/colon
        csv_data2 = (
            ",#playlist:p1\n"
            "#track,1\n"
        )
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data2))
        self.assertIn("misses a valid track ID", str(ctx.exception))

    def test_sequence_start_greater_than_1(self):
        # Sequence must start at 1, not 2
        csv_data = (
            ",#playlist:p1 #strict\n"
            "#track:t1,2\n"
        )
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data))
        self.assertIn("Sequence violation in playlist 'p1'", str(ctx.exception))

    def test_empty_and_whitespace_csv(self):
        with self.assertRaises(PlaylisterError):
            parse_csv_sheet(io.StringIO(""))
        
        # Whitespace CSV returns empty lists
        playlists, tracks, matrix = parse_csv_sheet(io.StringIO("   \n   \n"))
        self.assertEqual(playlists, [])
        self.assertEqual(tracks, [])
        self.assertEqual(matrix, {})

    def test_ignore_behavior(self):
        csv_data = (
            ",#playlist:p1,#playlist:p2 #ignore\n"
            "#track:t1,1,#no\n"
            "#track:t2 #ignore,#no,#no\n"
        )
        playlists, tracks, matrix = parse_csv_sheet(io.StringIO(csv_data))
        self.assertEqual(len(playlists), 1)
        self.assertEqual(playlists[0].id, "p1")
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0].id, "t1")

    def test_strict_mode_errors(self):
        # 1. Gaps in order values
        csv_data_gap = ",#playlist:p1 #strict\n#track:t1,2\n"
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data_gap))
        self.assertIn("Sequence violation", str(ctx.exception))

        # 2. Duplicate order positions
        csv_data_dup = ",#playlist:p1 #strict\n#track:t1,1\n#track:t2,1\n"
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data_dup))
        self.assertIn("Duplicate track order positions", str(ctx.exception))

        # 3. Invalid inputs
        csv_data_invalid = ",#playlist:p1 #strict\n#track:t1,potato\n"
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data_invalid))
        self.assertIn("Invalid input 'potato'", str(ctx.exception))

    def test_non_strict_mode_tolerance_and_randomization(self):
        # 1. Gaps are allowed, invalid inputs/empty cells are treated as #no
        csv_data_tol = (
            ",#playlist:p1\n"
            "#track:t1,3\n"
            "#track:t2,potato\n"
            "#track:t3,\n"
        )
        playlists, tracks, matrix = parse_csv_sheet(io.StringIO(csv_data_tol))
        self.assertEqual(matrix["p1"]["t1"], 1) # Normalization resolves it to 1
        self.assertEqual(matrix["p1"]["t2"], "#no")
        self.assertEqual(matrix["p1"]["t3"], "#no")

        # 2. Duplicate order values are stably randomized
        csv_data_rand = (
            ",#playlist:p_seed1\n"
            "#track:t3,5\n"
            "#track:t2,5\n"
            "#track:t1,1\n"
            "#track:t4,5\n"
        )
        # Randomization should be stable and seeded with playlist id
        p, t, m1 = parse_csv_sheet(io.StringIO(csv_data_rand))
        p, t, m2 = parse_csv_sheet(io.StringIO(csv_data_rand))
        self.assertEqual(m1, m2)
        
        # Verify normalization (1 for t1, then 2, 3, 4 for the others)
        self.assertEqual(m1["p_seed1"]["t1"], 1)
        ranks = [m1["p_seed1"][tid] for tid in ["t2", "t3", "t4"]]
        self.assertEqual(sorted(ranks), [2, 3, 4])

if __name__ == "__main__":
    unittest.main()
