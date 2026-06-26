import urllib.request
import urllib.error
import urllib.parse
import json

class SpotifyException(Exception):
    def __init__(self, status_code, code, message, headers=None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers
        super().__init__(f"http status: {status_code}, code:{code} - {message}")

class Spotify:
    """
    A lightweight, pure Python stdlib implementation of spotipy.Spotify.
    Uses urllib.request to interact with the real Spotify API.
    """
    def __init__(self, auth=None, requests_session=True, client_credentials_manager=None, proxies=None, requests_timeout=None, status_forcelist=None, retries=3, backoff_factor=0.3, user_agent=None):
        self.auth = auth

    def _request(self, method, url, body=None):
        headers = {
            "Authorization": f"Bearer {self.auth}",
            "Content-Type": "application/json"
        }
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as response:
                res_body = response.read().decode("utf-8")
                return json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as e:
            res_body = e.read().decode("utf-8") if e.fp else ""
            try:
                err_data = json.loads(res_body)
                msg = err_data.get("error", {}).get("message", str(e))
            except Exception:
                msg = res_body or str(e)
            raise SpotifyException(e.code, -1, msg)
        except Exception as e:
            raise SpotifyException(500, -1, str(e))

    def track(self, track_id, market="from_token"):
        tid = track_id.split(':')[-1]
        url = f"https://api.spotify.com/v1/tracks/{tid}"
        if market:
            url += f"?market={market}"
        return self._request("GET", url)

    def playlist(self, playlist_id, fields=None, market="from_token", additional_types=('track',)):
        pid = playlist_id.split(':')[-1]
        url = f"https://api.spotify.com/v1/playlists/{pid}"
        params = []
        if fields:
            params.append(f"fields={urllib.parse.quote(fields)}")
        if market:
            params.append(f"market={market}")
        if additional_types:
            types_str = ",".join(additional_types)
            params.append(f"additional_types={urllib.parse.quote(types_str)}")
        if params:
            url += "?" + "&".join(params)
        return self._request("GET", url)

    def playlist_tracks(self, playlist_id, limit=100, offset=0, fields=None, market="from_token", additional_types=('track',)):
        pid = playlist_id.split(':')[-1]
        url = f"https://api.spotify.com/v1/playlists/{pid}/items"
        params = [f"limit={limit}", f"offset={offset}"]
        if fields:
            params.append(f"fields={urllib.parse.quote(fields)}")
        if market:
            params.append(f"market={market}")
        if additional_types:
            types_str = ",".join(additional_types)
            params.append(f"additional_types={urllib.parse.quote(types_str)}")
        url += "?" + "&".join(params)
        return self._request("GET", url)

    def next(self, result):
        if not result or not result.get('next'):
            return None
        return self._request("GET", result['next'])

    def playlist_remove_all_occurrences_of_items(self, playlist_id, items, snapshot_id=None):
        pid = playlist_id.split(':')[-1]
        url = f"https://api.spotify.com/v1/playlists/{pid}/items"
        uris = [f"spotify:track:{item}" if not item.startswith("spotify:") else item for item in items]
        body = {"items": [{"uri": uri} for uri in uris]}
        if snapshot_id:
            body["snapshot_id"] = snapshot_id
        return self._request("DELETE", url, body=body)

    def playlist_add_items(self, playlist_id, items, position=None):
        pid = playlist_id.split(':')[-1]
        url = f"https://api.spotify.com/v1/playlists/{pid}/items"
        uris = [f"spotify:track:{item}" if not item.startswith("spotify:") else item for item in items]
        body = {"uris": uris}
        if position is not None:
            body["position"] = position
        return self._request("POST", url, body=body)

    def playlist_reorder_items(self, playlist_id, range_start, insert_before, range_length=1, snapshot_id=None):
        pid = playlist_id.split(':')[-1]
        url = f"https://api.spotify.com/v1/playlists/{pid}/items"
        body = {
            "range_start": range_start,
            "insert_before": insert_before,
            "range_length": range_length
        }
        if snapshot_id:
            body["snapshot_id"] = snapshot_id
        return self._request("PUT", url, body=body)

    def album(self, album_id, market="from_token"):
        aid = album_id.split(':')[-1]
        url = f"https://api.spotify.com/v1/albums/{aid}"
        if market:
            url += f"?market={market}"
        return self._request("GET", url)

    def album_tracks(self, album_id, limit=50, offset=0, market="from_token"):
        aid = album_id.split(':')[-1]
        url = f"https://api.spotify.com/v1/albums/{aid}/tracks"
        params = [f"limit={limit}", f"offset={offset}"]
        if market:
            params.append(f"market={market}")
        url += "?" + "&".join(params)
        return self._request("GET", url)

    def current_user(self):
        return self._request("GET", "https://api.spotify.com/v1/me")
