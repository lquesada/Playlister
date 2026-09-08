import unittest
from unittest.mock import patch, MagicMock
import io
import json
import os
import tempfile
from playlister_lib.youtube_client import YouTubeClient, OfflineYouTubeClient, parse_iso8601_duration
from playlister_lib.youtube_auth import (
    load_client_secrets_json,
    resolve_youtube_key_path,
    save_youtube_key_file,
    load_youtube_cache,
    save_youtube_cache,
    clear_youtube_cache_file,
    clear_youtube_keys_file
)

class TestYouTubeClient(unittest.TestCase):
    def test_parse_iso8601_duration(self):
        self.assertEqual(parse_iso8601_duration("PT1H2M30S"), 3750000)
        self.assertEqual(parse_iso8601_duration("PT4M15S"), 255000)
        self.assertEqual(parse_iso8601_duration("PT45S"), 45000)
        self.assertEqual(parse_iso8601_duration("PT2H"), 7200000)
        self.assertEqual(parse_iso8601_duration("P1DT2H"), 93600000)
        self.assertIsNone(parse_iso8601_duration(None))
        self.assertIsNone(parse_iso8601_duration(""))
        self.assertIsNone(parse_iso8601_duration("invalid"))

    @patch("urllib.request.urlopen")
    def test_get_playlist(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "items": [{
                "id": "PL123",
                "snippet": {"title": "Cool Videos", "description": "Desc"},
                "contentDetails": {"itemCount": 5}
            }]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        client = YouTubeClient("fake_token")
        p = client.get_playlist("PL123")
        self.assertEqual(p["id"], "PL123")
        self.assertEqual(p["name"], "Cool Videos")
        self.assertEqual(p["item_count"], 5)

    @patch("urllib.request.urlopen")
    def test_get_playlist_items_paginated(self, mock_urlopen):
        # Page 1
        resp1 = MagicMock()
        resp1.status = 200
        resp1.read.return_value = json.dumps({
            "items": [{
                "id": "item1",
                "snippet": {
                    "resourceId": {"videoId": "vid1"},
                    "title": "Video 1",
                    "position": 0
                }
            }],
            "nextPageToken": "token2"
        }).encode("utf-8")

        # Page 2
        resp2 = MagicMock()
        resp2.status = 200
        resp2.read.return_value = json.dumps({
            "items": [{
                "id": "item2",
                "snippet": {
                    "resourceId": {"videoId": "vid2"},
                    "title": "Video 2",
                    "position": 1
                }
            }]
        }).encode("utf-8")

        mock_urlopen.return_value.__enter__.side_effect = [resp1, resp2]

        client = YouTubeClient("fake_token")
        items = client.get_playlist_items("PL123")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["video_id"], "vid1")
        self.assertEqual(items[1]["video_id"], "vid2")

    @patch("urllib.request.urlopen")
    def test_get_video_details(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "items": [{
                "id": "vid1",
                "snippet": {"title": "Song One Video"},
                "contentDetails": {"duration": "PT3M30S"}
            }]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        client = YouTubeClient("fake_token")
        details = client.get_video_details(["vid1"])
        self.assertIn("vid1", details)
        self.assertEqual(details["vid1"]["name"], "Song One Video")
        self.assertEqual(details["vid1"]["duration_ms"], 210000)

    @patch("urllib.request.urlopen")
    def test_add_remove_reorder(self, mock_urlopen):
        resp_add = MagicMock(status=200)
        resp_add.read.return_value = b'{"id": "new_item"}'
        resp_del = MagicMock(status=204)
        resp_del.read.return_value = b''
        resp_put = MagicMock(status=200)
        resp_put.read.return_value = b'{"id": "reordered_item"}'

        mock_urlopen.return_value.__enter__.side_effect = [resp_add, resp_del, resp_put]

        client = YouTubeClient("fake_token")
        res_add = client.add_playlist_item("PL123", "vid1")
        self.assertIsNotNone(res_add)

        client.remove_playlist_item("item1")
        res_put = client.reorder_playlist_item("item1", "PL123", "vid1", position=0)
        self.assertIsNotNone(res_put)

    def test_offline_client(self):
        client = OfflineYouTubeClient()
        p = client.get_playlist("PL123")
        self.assertEqual(p["id"], "PL123")
        self.assertEqual(client.get_playlist_items("PL123"), [])
        details = client.get_video_details(["vid1"])
        self.assertEqual(details["vid1"]["duration_ms"], 180000)

    @patch("urllib.request.urlopen")
    def test_quota_exceeded_error(self, mock_urlopen):
        import urllib.error
        from playlister_lib.youtube_client import YouTubeQuotaExceededError
        err_json = json.dumps({
            "error": {
                "code": 403,
                "message": "The request cannot be completed because you have exceeded your quota.",
                "errors": [{"reason": "quotaExceeded"}]
            }
        }).encode("utf-8")

        mock_err = urllib.error.HTTPError(
            url="https://www.googleapis.com/youtube/v3/playlistItems",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=io.BytesIO(err_json)
        )
        mock_urlopen.side_effect = mock_err

        client = YouTubeClient("fake_token")
        with self.assertRaises(YouTubeQuotaExceededError) as ctx:
            client.add_playlist_item("PL123", "vid1")
        self.assertIn("YouTube daily API quota exceeded", str(ctx.exception))



class TestYouTubeAuth(unittest.TestCase):
    def test_load_client_secrets_json(self):
        data = {
            "installed": {
                "client_id": "test_cid.apps.googleusercontent.com",
                "client_secret": "test_csecret",
                "redirect_uris": ["http://127.0.0.1:8080"]
            }
        }
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            cid, csec, redir = load_client_secrets_json(temp_path)
            self.assertEqual(cid, "test_cid.apps.googleusercontent.com")
            self.assertEqual(csec, "test_csecret")
            self.assertEqual(redir, "http://127.0.0.1:8080")
        finally:
            os.remove(temp_path)

    def test_keys_and_cache_io(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Keys
            save_youtube_key_file(temp_dir, {"access_token": "abc", "refresh_token": "def"}, silent=True)
            keys_file = os.path.join(temp_dir, "youtube_keys")
            self.assertTrue(os.path.exists(keys_file))

            clear_youtube_keys_file(temp_dir)
            self.assertFalse(os.path.exists(keys_file))

            # Cache
            save_youtube_cache(temp_dir, {"vid1": {"name": "Test Video"}})
            cached = load_youtube_cache(temp_dir)
            self.assertEqual(cached.get("vid1", {}).get("name"), "Test Video")

            clear_youtube_cache_file(temp_dir)
            cached_empty = load_youtube_cache(temp_dir)
            self.assertEqual(cached_empty, {})

if __name__ == "__main__":
    unittest.main()
