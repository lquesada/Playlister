class OfflineSpotifyClient:
    def __init__(self, playlists=None, tracks=None):
        self.playlists_map = {}
        self.tracks_map = {}
        
        if playlists:
            for p in playlists:
                self.playlists_map[p.id] = p.title if p.title else p.id
        if tracks:
            for t in tracks:
                self.tracks_map[t.id] = t.title if t.title else t.id

    def track(self, track_id):
        name = self.tracks_map.get(track_id, track_id)
        return {
            "name": name,
            "duration_ms": None
        }

    def playlist(self, playlist_id):
        name = self.playlists_map.get(playlist_id, playlist_id)
        return {
            "name": name,
            "tracks": {"total": 0}
        }

    def playlist_replace_items(self, playlist_id, track_ids):
        # Simulate updating the playlist
        return {"status": "ok"}
