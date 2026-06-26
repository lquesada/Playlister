import unittest

class TestVendorImport(unittest.TestCase):
    def test_import_spotipy(self):
        try:
            import spotipy
            import spotipy.client
            from spotipy import Spotify
        except Exception as e:
            self.fail(f"Failed to import vendored spotipy: {e}")

if __name__ == "__main__":
    unittest.main()
