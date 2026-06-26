import unittest
from playlister_lib.mock_client import OfflineSpotifyClient
from playlister_lib.parser import PlaylistData, TrackData

class TestMockClient(unittest.TestCase):
    def test_offline_retrieval(self):
        p = PlaylistData("#playlist:p1 #title:<Cool Hits>")
        t = TrackData("#track:t1 #title:<Awesome Song>")
        client = OfflineSpotifyClient(playlists=[p], tracks=[t])
        
        # Query track details
        track_info = client.track("t1")
        self.assertEqual(track_info["name"], "Awesome Song")
        self.assertIsNone(track_info["duration_ms"])
        
        # Query playlist details
        playlist_info = client.playlist("p1")
        self.assertEqual(playlist_info["name"], "Cool Hits")

if __name__ == "__main__":
    unittest.main()
