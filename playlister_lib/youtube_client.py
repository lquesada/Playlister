import urllib.request
import urllib.parse
import json
import re

def parse_iso8601_duration(dur_str):
    """
    Parse an ISO 8601 duration string (e.g. PT1H2M30S, PT4M15S, PT45S) into milliseconds.
    """
    if not dur_str or not isinstance(dur_str, str):
        return None
    pattern = re.compile(r'P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?')
    match = pattern.match(dur_str)
    if not match:
        return None
    days, hours, minutes, seconds = match.groups()
    total_seconds = 0
    if days:
        total_seconds += int(days) * 86400
    if hours:
        total_seconds += int(hours) * 3600
    if minutes:
        total_seconds += int(minutes) * 60
    if seconds:
        total_seconds += int(seconds)
    return total_seconds * 1000

class YouTubeQuotaExceededError(Exception):
    pass

class YouTubeClient:
    BASE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(self, auth_token):
        self.auth_token = auth_token

    def _request(self, endpoint, query_params=None, method="GET", body=None):
        url = f"{self.BASE_URL}/{endpoint}"
        if query_params:
            url += "?" + urllib.parse.urlencode(query_params)

        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Accept": "application/json"
        }
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                if status == 204:
                    return None
                resp_text = resp.read().decode("utf-8")
                if not resp_text:
                    return None
                return json.loads(resp_text)
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8") if e.fp else str(e)
            try:
                err_json = json.loads(err_msg)
                error_obj = err_json.get("error", {})
                message = error_obj.get("message", err_msg)
                errors = error_obj.get("errors", [])
                for item in errors:
                    if item.get("reason") in ("quotaExceeded", "rateLimitExceeded"):
                        raise YouTubeQuotaExceededError(f"YouTube daily API quota exceeded: {message}")
                if "quota" in message.lower() and e.code == 403:
                    raise YouTubeQuotaExceededError(f"YouTube daily API quota exceeded: {message}")
            except YouTubeQuotaExceededError:
                raise
            except Exception:
                message = err_msg
            raise Exception(f"YouTube API Error ({e.code}): {message}") from e

    def get_current_user_info(self):
        res = self._request("channels", query_params={"part": "snippet", "mine": "true"})
        items = res.get("items", []) if res else []
        if items:
            snippet = items[0].get("snippet", {})
            return {
                "id": items[0].get("id"),
                "display_name": snippet.get("title", "YouTube User")
            }
        return {"id": "me", "display_name": "Authenticated YouTube User"}

    def get_playlist(self, playlist_id):
        res = self._request("playlists", query_params={"part": "snippet,contentDetails", "id": playlist_id})
        items = res.get("items", []) if res else []
        if not items:
            raise Exception(f"Playlist '{playlist_id}' not found on YouTube.")
        item = items[0]
        snippet = item.get("snippet", {})
        content_details = item.get("contentDetails", {})
        return {
            "id": playlist_id,
            "name": snippet.get("title", "Unknown"),
            "description": snippet.get("description", ""),
            "item_count": content_details.get("itemCount", 0)
        }

    def get_playlist_items(self, playlist_id):
        items = []
        page_token = None
        while True:
            params = {
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": 50
            }
            if page_token:
                params["pageToken"] = page_token

            res = self._request("playlistItems", query_params=params)
            res_items = res.get("items", []) if res else []
            for item in res_items:
                snippet = item.get("snippet", {})
                resource_id = snippet.get("resourceId", {})
                video_id = resource_id.get("videoId")
                if video_id:
                    items.append({
                        "item_id": item.get("id"),
                        "video_id": video_id,
                        "title": snippet.get("title", "Unknown"),
                        "position": snippet.get("position", 0)
                    })
            page_token = res.get("nextPageToken") if res else None
            if not page_token:
                break
        return items

    def get_video_details(self, video_ids):
        if not video_ids:
            return {}
        details = {}
        # Max 50 IDs per request
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i + 50]
            params = {
                "part": "snippet,contentDetails",
                "id": ",".join(batch)
            }
            res = self._request("videos", query_params=params)
            for item in (res.get("items", []) if res else []):
                vid = item.get("id")
                snippet = item.get("snippet", {})
                content_details = item.get("contentDetails", {})
                dur_str = content_details.get("duration")
                details[vid] = {
                    "name": snippet.get("title", "Unknown"),
                    "duration_ms": parse_iso8601_duration(dur_str)
                }
        return details

    def add_playlist_item(self, playlist_id, video_id, position=None):
        snippet = {
            "playlistId": playlist_id,
            "resourceId": {
                "kind": "youtube#video",
                "videoId": video_id
            }
        }
        if position is not None:
            snippet["position"] = position
        body = {"snippet": snippet}
        return self._request("playlistItems", query_params={"part": "snippet"}, method="POST", body=body)

    def remove_playlist_item(self, playlist_item_id):
        return self._request("playlistItems", query_params={"id": playlist_item_id}, method="DELETE")

    def reorder_playlist_item(self, playlist_item_id, playlist_id, video_id, position):
        body = {
            "id": playlist_item_id,
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                },
                "position": position
            }
        }
        return self._request("playlistItems", query_params={"part": "snippet"}, method="PUT", body=body)


class OfflineYouTubeClient:
    def __init__(self, playlists=None, tracks=None):
        self.playlists = playlists or []
        self.tracks = tracks or []

    def get_playlist(self, playlist_id):
        for p in self.playlists:
            if getattr(p, "youtube_id", None) == playlist_id or getattr(p, "id", None) == playlist_id:
                return {"id": playlist_id, "name": getattr(p, "youtube_title", None) or getattr(p, "title", None) or playlist_id}
        return {"id": playlist_id, "name": playlist_id}

    def get_playlist_items(self, playlist_id):
        return []

    def get_video_details(self, video_ids):
        return {vid: {"name": vid, "duration_ms": 180000} for vid in video_ids}
