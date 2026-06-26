import unittest
import tempfile
import os
import json
from unittest.mock import patch
from playlister_lib.key_store import get_api_key, resolve_key_path

class TestKeyStore(unittest.TestCase):
    def test_resolve_key_path(self):
        self.assertEqual(resolve_key_path("/tmp/test_key"), "/tmp/test_key")
        default_path = resolve_key_path(None)
        self.assertTrue(default_path.endswith(".playlister"))

    @patch('playlister_lib.key_store._request_token', return_value=("mocked_access_token", "mocked_refresh_token", 3600))
    @patch('builtins.input')
    def test_interactive_prompt_save(self, mock_input, mock_request_token):
        mock_input.side_effect = ['my_client_id', 'my_client_secret', 'http://127.0.0.1:8000/callback', 'http://127.0.0.1:8000/callback?code=auth_code']
        with tempfile.TemporaryDirectory() as tmpdir:
            key_dir = os.path.join(tmpdir, "key_store_dir")
            key = get_api_key(key_dir=key_dir, no_store_key=False)
            self.assertEqual(key, "mocked_access_token")
            keys_file = os.path.join(key_dir, "keys")
            self.assertTrue(os.path.exists(keys_file))
            
            with open(keys_file, "r") as f:
                content = json.load(f)
            self.assertEqual(content["client_id"], "my_client_id")
            self.assertEqual(content["client_secret"], "my_client_secret")
            self.assertEqual(content["redirect_uri"], "http://127.0.0.1:8000/callback")
            self.assertEqual(content["access_token"], "mocked_access_token")
            self.assertEqual(content["refresh_token"], "mocked_refresh_token")
            
            mode = os.stat(keys_file).st_mode & 0o777
            self.assertEqual(mode, 0o600)

    @patch('playlister_lib.key_store._request_token', return_value=("mocked_access_token", "mocked_refresh_token", 3600))
    @patch('builtins.input')
    def test_interactive_prompt_no_save(self, mock_input, mock_request_token):
        mock_input.side_effect = ['my_client_id', 'my_client_secret', 'http://127.0.0.1:8000/callback', 'http://127.0.0.1:8000/callback?code=auth_code']
        with tempfile.TemporaryDirectory() as tmpdir:
            key_dir = os.path.join(tmpdir, "key_store_dir")
            key = get_api_key(key_dir=key_dir, no_store_key=True)
            self.assertEqual(key, "mocked_access_token")
            self.assertFalse(os.path.exists(os.path.join(key_dir, "keys")))

    @patch('playlister_lib.key_store._request_token', return_value=("mocked_access_token", "mocked_refresh_token", 3600))
    @patch('builtins.input')
    def test_interactive_prompt_default_redirect(self, mock_input, mock_request_token):
        # Empty string for redirect URI input should fallback to default
        mock_input.side_effect = ['my_client_id', 'my_client_secret', '', 'http://127.0.0.1:8000/callback?code=auth_code']
        with tempfile.TemporaryDirectory() as tmpdir:
            key_dir = os.path.join(tmpdir, "key_store_dir")
            key = get_api_key(key_dir=key_dir, no_store_key=False)
            self.assertEqual(key, "mocked_access_token")
            keys_file = os.path.join(key_dir, "keys")
            with open(keys_file, "r") as f:
                content = json.load(f)
            self.assertEqual(content["redirect_uri"], "http://127.0.0.1:8000/callback")

    @patch('playlister_lib.key_store.refresh_spotify_token')
    def test_cached_token_scopes_match(self, mock_refresh):
        import time
        with tempfile.TemporaryDirectory() as tmpdir:
            key_dir = os.path.join(tmpdir, "key_store_dir")
            os.makedirs(key_dir, exist_ok=True)
            keys_file = os.path.join(key_dir, "keys")
            scopes = "playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative user-read-private"
            data = {
                "client_id": "cid",
                "client_secret": "csec",
                "redirect_uri": "http://127.0.0.1:8000/callback",
                "access_token": "cached_token",
                "expires_at": time.time() + 3600,
                "refresh_token": "ref_token",
                "scopes": scopes
            }
            with open(keys_file, "w") as f:
                json.dump(data, f)
            
            with patch('builtins.input') as mock_input:
                key = get_api_key(key_dir=key_dir, no_store_key=False)
                self.assertEqual(key, "cached_token")
                mock_input.assert_not_called()
                mock_refresh.assert_not_called()

    @patch('playlister_lib.key_store.refresh_spotify_token', return_value=("new_access", "new_ref", 3600))
    def test_refresh_token_scopes_match(self, mock_refresh):
        import time
        with tempfile.TemporaryDirectory() as tmpdir:
            key_dir = os.path.join(tmpdir, "key_store_dir")
            os.makedirs(key_dir, exist_ok=True)
            keys_file = os.path.join(key_dir, "keys")
            scopes = "playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative user-read-private"
            data = {
                "client_id": "cid",
                "client_secret": "csec",
                "redirect_uri": "http://127.0.0.1:8000/callback",
                "access_token": "cached_token",
                "expires_at": time.time() - 3600,
                "refresh_token": "ref_token",
                "scopes": scopes
            }
            with open(keys_file, "w") as f:
                json.dump(data, f)
            
            with patch('builtins.input') as mock_input:
                key = get_api_key(key_dir=key_dir, no_store_key=False)
                self.assertEqual(key, "new_access")
                mock_input.assert_not_called()
                mock_refresh.assert_called_once_with("cid", "csec", "ref_token")

    @patch('playlister_lib.key_store._request_token', return_value=("new_access", "new_ref", 3600))
    @patch('builtins.input')
    def test_reprompt_when_scopes_mismatch(self, mock_input, mock_request_token):
        import time
        with tempfile.TemporaryDirectory() as tmpdir:
            key_dir = os.path.join(tmpdir, "key_store_dir")
            os.makedirs(key_dir, exist_ok=True)
            keys_file = os.path.join(key_dir, "keys")
            data = {
                "client_id": "cid",
                "client_secret": "csec",
                "redirect_uri": "http://127.0.0.1:8000/callback",
                "access_token": "cached_token",
                "expires_at": time.time() + 3600,
                "refresh_token": "ref_token",
                "scopes": "playlist-modify-public"
            }
            with open(keys_file, "w") as f:
                json.dump(data, f)
            
            mock_input.side_effect = ['http://127.0.0.1:8000/callback?code=new_code']
            key = get_api_key(key_dir=key_dir, no_store_key=False)
            self.assertEqual(key, "new_access")
            mock_input.assert_called_once()

    def test_migrate_if_needed_success(self):
        from playlister_lib.key_store import migrate_if_needed
        with tempfile.TemporaryDirectory() as tmpdir:
            legacy_file = os.path.join(tmpdir, "legacy_store")
            dummy_data = {"key": "val"}
            with open(legacy_file, "w") as f:
                json.dump(dummy_data, f)
            
            self.assertTrue(os.path.isfile(legacy_file))
            migrate_if_needed(legacy_file)
            
            # Now legacy_file should be a directory, and legacy_file/keys should contain the data
            self.assertTrue(os.path.isdir(legacy_file))
            keys_file = os.path.join(legacy_file, "keys")
            self.assertTrue(os.path.exists(keys_file))
            with open(keys_file, "r") as f:
                self.assertEqual(json.load(f), dummy_data)

    def test_load_cache_invalid_json(self):
        from playlister_lib.key_store import load_cache
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "cache_dir"), exist_ok=True)
            cache_path = os.path.join(tmpdir, "cache_dir", "cache")
            with open(cache_path, "w") as f:
                f.write("{invalid_json}")
            
            # Should fail gracefully and return empty dict
            cache = load_cache(os.path.join(tmpdir, "cache_dir"))
            self.assertEqual(cache, {})

    def test_load_cache_io_error(self):
        from playlister_lib.key_store import load_cache
        with patch('os.open', side_effect=PermissionError("Denied")):
            cache = load_cache("/tmp/nonexistent")
            self.assertEqual(cache, {})

if __name__ == "__main__":
    unittest.main()
