import unittest
import io
from playlister_lib.parser import parse_csv_sheet, PlaylistData, TrackData, PlaylisterError

class TestParser(unittest.TestCase):
    def test_parse_success(self):
        csv_data = (
            ",#playlist:43TtjGF050gzkar4IPmsLN #title:<Playlist 1> #allowmissing,#playlist:https://open.spotify.com/playlist/abc123xyz #strict\n"
            "#track:3BDidzS8avudzMj1G9ZZaz #title:<Track 1>,1,#no\n"
            "#track:https://open.spotify.com/track/t2_id #title:@Track 2@,3,1\n"
            "#track:t3 #title:!Track 3! #ignore,4,2\n"
        )
        playlists, tracks, matrix = parse_csv_sheet(io.StringIO(csv_data))
        
        self.assertEqual(len(playlists), 2)
        self.assertEqual(playlists[0].id, "43TtjGF050gzkar4IPmsLN")
        self.assertEqual(playlists[0].title, "Playlist 1")
        self.assertTrue(playlists[0].allow_missing)
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
        self.assertEqual(matrix["43TtjGF050gzkar4IPmsLN"]["t2_id"], 3)
        self.assertEqual(matrix["abc123xyz"]["3BDidzS8avudzMj1G9ZZaz"], "#no")
        self.assertEqual(matrix["abc123xyz"]["t2_id"], 1)

    def test_missing_playlist_id(self):
        csv_data = ",#title:<Playlist 1>\n#track:t1,1\n"
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data))
        self.assertIn("misses a valid playlist ID", str(ctx.exception))

    def test_missing_track_id(self):
        csv_data = ",#playlist:p1\n#title:<Track 1>,1\n"
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data))
        self.assertIn("misses a valid track ID", str(ctx.exception))

    def test_sequence_error_without_allowmissing(self):
        # Gaps are not allowed by default
        csv_data = (
            ",#playlist:p1\n"
            "#track:t1,1\n"
            "#track:t2,3\n"
        )
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data))
        self.assertIn("Sequence violation", str(ctx.exception))

    def test_sequence_success_with_allowmissing(self):
        csv_data = (
            ",#playlist:p1 #allowmissing\n"
            "#track:t1,1\n"
            "#track:t2,3\n"
        )
        playlists, tracks, matrix = parse_csv_sheet(io.StringIO(csv_data))
        self.assertEqual(matrix["p1"]["t1"], 1)
        self.assertEqual(matrix["p1"]["t2"], 3)

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
        # Without allowinvalid, "potato" triggers an error
        csv_data = (
            ",#playlist:p1\n"
            "#track:t1,1\n"
            "#track:t2,potato\n"
        )
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data))
        self.assertEqual("Invalid input 'potato' at row 2 (track 't2') and column 1 (playlist 'p1').", str(ctx.exception))

        # With allowinvalid, "potato" is treated as "#no"
        csv_data_ok = (
            ",#playlist:p1 #allowinvalid\n"
            "#track:t1,1\n"
            "#track:t2,potato\n"
        )
        playlists, tracks, matrix = parse_csv_sheet(io.StringIO(csv_data_ok))
        self.assertEqual(matrix["p1"]["t2"], "#no")

    def test_duplicate_order_positions(self):
        csv_data = (
            ",#playlist:p1\n"
            "#track:t1,1\n"
            "#track:t2,1\n"
        )
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data))
        self.assertEqual("Duplicate track order positions in playlist 'p1' at column 1", str(ctx.exception))

    def test_error_message_with_playlist_title(self):
        csv_data = (
            ",#playlist:p1 #title:<My Playlist>\n"
            "#track:t1,1\n"
            "#track:t2,1\n"
        )
        with self.assertRaises(PlaylisterError) as ctx:
            parse_csv_sheet(io.StringIO(csv_data))
        self.assertEqual("Duplicate track order positions in playlist 'My Playlist' ('p1') at column 1", str(ctx.exception))

    def test_directives_order(self):
        # Directives in different orders should be parsed correctly
        csv_data = (
            ",#allowmissing #title:<Hello> #playlist:p1\n"
            "#track:t1,1\n"
        )
        playlists, tracks, matrix = parse_csv_sheet(io.StringIO(csv_data))
        self.assertEqual(len(playlists), 1)
        self.assertEqual(playlists[0].id, "p1")
        self.assertEqual(playlists[0].title, "Hello")
        self.assertTrue(playlists[0].allow_missing)

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
            ",#playlist:p1\n"
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

if __name__ == "__main__":
    unittest.main()
