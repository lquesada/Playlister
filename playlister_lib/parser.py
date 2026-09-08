import csv
import re
import urllib.parse
import collections
import random

class PlaylisterError(Exception):
    pass

def extract_directive_value(directive, text):
    pattern = rf'(?:^|\s){directive}:([^\s]+)'
    m = re.search(pattern, text)
    if m:
        return m.group(1)
    return None

def extract_title_value(directive, text):
    pattern = rf'(?:^|\s){directive}:(?:<([^>]*)>|@([^@]*)@|!([^!]*)!|"([^"]*)"|\'([^\']*)\'|([^\s]+))'
    m = re.search(pattern, text)
    if m:
        return next(g for g in m.groups() if g is not None)
    return None

def extract_youtube_video_id(val):
    if not val:
        return None
    val = val.strip()
    if "v=" in val:
        parsed = urllib.parse.urlparse(val)
        qs = urllib.parse.parse_qs(parsed.query)
        if "v" in qs and qs["v"]:
            return qs["v"][0]
    clean_val = val.split('?')[0].rstrip('/')
    return clean_val.split('/')[-1]

def extract_youtube_playlist_id(val):
    if not val:
        return None
    val = val.strip()
    if "list=" in val:
        parsed = urllib.parse.urlparse(val)
        qs = urllib.parse.parse_qs(parsed.query)
        if "list" in qs and qs["list"]:
            return qs["list"][0]
    clean_val = val.split('?')[0].rstrip('/')
    return clean_val.split('/')[-1]

def extract_spotify_id(val):
    if not val:
        return None
    clean_val = val.split('?')[0].rstrip('/')
    return clean_val.split('/')[-1]


class PlaylistData:
    def __init__(self, raw_str, service=None):
        self.raw = raw_str.strip()
        self.service = service  # 'spotify', 'youtube', or None
        self.id = None
        self.spotify_id = None
        self.youtube_id = None
        self.title = None
        self.spotify_title = None
        self.youtube_title = None
        self.strict = False
        self.ignore = False
        self.allowmissing = False
        self.col_idx = None
        self._parse()

    @property
    def display_name(self):
        title = self.spotify_title or self.youtube_title or self.title
        id_val = self.spotify_id or self.youtube_id or self.id
        if title:
            return f"'{title}' ('{id_val}')"
        return f"'{id_val}'"

    def _parse(self):
        if re.search(r'(?:^|\s)#ignore\b', self.raw):
            self.ignore = True
        if re.search(r'(?:^|\s)#strict\b', self.raw):
            self.strict = True
        if re.search(r'(?:^|\s)#allowmissing\b', self.raw):
            self.allowmissing = True

        # Extract Spotify playlist ID
        sp_match = extract_directive_value("#spotifyplaylist", self.raw)
        if sp_match:
            self.spotify_id = extract_spotify_id(sp_match)

        # Extract YouTube playlist ID
        yt_match = extract_directive_value("#youtubeplaylist", self.raw) or extract_directive_value("#ytplaylist", self.raw)
        if yt_match:
            self.youtube_id = extract_youtube_playlist_id(yt_match)

        # Generic #playlist directive (backwards compatibility or auto-detection)
        gen_match = extract_directive_value("#playlist", self.raw)
        if gen_match:
            if "youtube.com" in gen_match or "youtu.be" in gen_match:
                if not self.youtube_id:
                    self.youtube_id = extract_youtube_playlist_id(gen_match)
            else:
                if not self.spotify_id:
                    self.spotify_id = extract_spotify_id(gen_match)

        # Titles
        self.spotify_title = extract_title_value("#spotifytitle", self.raw)
        self.youtube_title = extract_title_value("#youtubetitle", self.raw)
        self.title = extract_title_value("#title", self.raw)

        if self.title:
            if not self.spotify_title:
                self.spotify_title = self.title
            if not self.youtube_title:
                self.youtube_title = self.title

        # Determine primary service and ID
        if not self.service:
            if self.spotify_id and not self.youtube_id:
                self.service = "spotify"
            elif self.youtube_id and not self.spotify_id:
                self.service = "youtube"

        if self.service == "spotify":
            self.id = self.spotify_id
            self.title = self.spotify_title or self.title
        elif self.service == "youtube":
            self.id = self.youtube_id
            self.title = self.youtube_title or self.title
        else:
            self.id = self.spotify_id or self.youtube_id
            self.title = self.title or self.spotify_title or self.youtube_title


class TrackData:
    def __init__(self, raw_cells=None, r_idx=None, col_headers=None):
        if raw_cells is None:
            raw_cells = []
        elif isinstance(raw_cells, str):
            raw_cells = [raw_cells]

        self.raw_cells = [c.strip() for c in raw_cells]
        self.raw = " ".join(self.raw_cells)
        self.r_idx = r_idx
        self.id = None
        self.spotify_id = None
        self.youtube_id = None
        self.title = None
        self.spotify_title = None
        self.youtube_title = None
        self.ignore = False
        self._parse(col_headers)

    def _parse(self, col_headers=None):
        # 1. Check for #ignore in any descriptor cell
        for cell in self.raw_cells:
            if re.search(r'(?:^|\s)#ignore\b', cell):
                self.ignore = True
                break

        # 2. Parse directives from all cells
        combined = self.raw

        # Directives
        sp_match = extract_directive_value("#spotifytrack", combined)
        if sp_match:
            self.spotify_id = extract_spotify_id(sp_match)

        yt_match = extract_directive_value("#youtubetrack", combined) or extract_directive_value("#yttrack", combined)
        if yt_match:
            self.youtube_id = extract_youtube_video_id(yt_match)

        gen_match = extract_directive_value("#track", combined)
        if gen_match:
            if "youtube.com" in gen_match or "youtu.be" in gen_match:
                if not self.youtube_id:
                    self.youtube_id = extract_youtube_video_id(gen_match)
            else:
                if not self.spotify_id:
                    self.spotify_id = extract_spotify_id(gen_match)

        self.spotify_title = extract_title_value("#spotifytitle", combined)
        self.youtube_title = extract_title_value("#youtubetitle", combined)
        self.title = extract_title_value("#title", combined)

        # 3. Check column header conventions if cell didn't have explicit directives
        if col_headers and len(col_headers) == len(self.raw_cells):
            for header, cell in zip(col_headers, self.raw_cells):
                if not cell:
                    continue
                header_clean = header.strip().lower()
                if not cell.startswith("#"):
                    if header_clean in ("#spotifytrack", "spotifytrack", "spotify_track", "spotify id", "spotify_id", "spotify"):
                        if not self.spotify_id:
                            self.spotify_id = extract_spotify_id(cell)
                    elif header_clean in ("#youtubetrack", "youtubetrack", "youtube_track", "youtube id", "youtube_id", "youtube", "video_id", "videoid"):
                        if not self.youtube_id:
                            self.youtube_id = extract_youtube_video_id(cell)
                    elif header_clean in ("#spotifytitle", "spotifytitle", "spotify_title"):
                        if not self.spotify_title:
                            self.spotify_title = cell
                    elif header_clean in ("#youtubetitle", "youtubetitle", "youtube_title"):
                        if not self.youtube_title:
                            self.youtube_title = cell
                    elif header_clean in ("#title", "title", "track", "song", "name"):
                        if not self.title:
                            self.title = cell

        # Fallbacks for titles
        if self.title:
            if not self.spotify_title:
                self.spotify_title = self.title
            if not self.youtube_title:
                self.youtube_title = self.title
        else:
            self.title = self.spotify_title or self.youtube_title

        # Primary ID: must have spotify_id or youtube_id, else None
        self.id = self.spotify_id or self.youtube_id


def is_playlist_header_cell(cell):
    if not cell:
        return False
    val = cell.strip()
    playlist_tags = ("#playlist", "#spotifyplaylist", "#youtubeplaylist", "#ytplaylist")
    return any(tag in val for tag in playlist_tags)


def parse_csv_sheet(fileobj, force_strict=False):
    reader = csv.reader(fileobj)
    try:
        rows = list(reader)
    except Exception as e:
        raise PlaylisterError(f"Failed to read CSV: {e}")
        
    if not rows or not any(any(c.strip() for c in r) for r in rows):
        if not rows or (len(rows) == 1 and not any(rows[0])):
            raise PlaylisterError("CSV is empty.")
        return [], [], {}
    
    header = rows[0]
    
    # Identify descriptor columns (non-playlist) vs playlist columns
    descriptor_col_indices = []
    raw_playlist_cols = []
    
    for idx, col in enumerate(header):
        if is_playlist_header_cell(col):
            raw_playlist_cols.append((idx, col))
        else:
            descriptor_col_indices.append(idx)
            
    if not raw_playlist_cols:
        return [], [], {}
    
    descriptor_headers = [header[idx] for idx in descriptor_col_indices]

    # Parse playlist headers
    playlists = []
    playlist_col_map = []  # list of (col_idx, PlaylistData)

    for col_idx, col_str in raw_playlist_cols:
        col_str_clean = col_str.strip()
        has_spotify = "#spotifyplaylist" in col_str_clean or ("#playlist" in col_str_clean and "youtube.com" not in col_str_clean and "youtu.be" not in col_str_clean)
        has_youtube = "#youtubeplaylist" in col_str_clean or "#ytplaylist" in col_str_clean or ("#playlist" in col_str_clean and ("youtube.com" in col_str_clean or "youtu.be" in col_str_clean))

        if has_spotify and has_youtube:
            p_sp = PlaylistData(col_str_clean, service="spotify")
            p_sp.col_idx = col_idx
            if force_strict:
                p_sp.strict = True
            if not p_sp.ignore:
                if not p_sp.id:
                    raise PlaylisterError(f"Playlist cell at column {col_idx} misses a valid Spotify playlist ID: '{col_str_clean}'")
                playlists.append(p_sp)
                playlist_col_map.append((col_idx, p_sp))

            p_yt = PlaylistData(col_str_clean, service="youtube")
            p_yt.col_idx = col_idx
            if force_strict:
                p_yt.strict = True
            if not p_yt.ignore:
                if not p_yt.id:
                    raise PlaylisterError(f"Playlist cell at column {col_idx} misses a valid YouTube playlist ID: '{col_str_clean}'")
                playlists.append(p_yt)
                playlist_col_map.append((col_idx, p_yt))
        else:
            p = PlaylistData(col_str_clean)
            p.col_idx = col_idx
            if force_strict:
                p.strict = True
            if not p.ignore:
                if not p.id:
                    raise PlaylisterError(f"Playlist cell at column {col_idx} misses a valid playlist ID: '{col_str_clean}'")
                playlists.append(p)
                playlist_col_map.append((col_idx, p))

    # Parse track rows
    tracks = []
    track_rows = []

    for r_idx, row in enumerate(rows[1:], start=1):
        if not row or not any(c.strip() for c in row):
            continue

        desc_cells = []
        for c_idx in descriptor_col_indices:
            val = row[c_idx] if c_idx < len(row) else ""
            desc_cells.append(val)

        t = TrackData(raw_cells=desc_cells, r_idx=r_idx, col_headers=descriptor_headers)
        if t.ignore:
            continue

        if not t.id:
            raw_cell = row[0] if row else ""
            raise PlaylisterError(f"Track cell at row {r_idx} misses a valid track ID: '{raw_cell}'")

        tracks.append(t)
        track_rows.append((row, t))

    # Build matrix: keyed by playlist.id and track.id
    matrix = {p.id: {} for p in playlists}

    for row, t in track_rows:
        for col_idx, p in playlist_col_map:
            cell_val = row[col_idx].strip() if col_idx < len(row) else ""
            if cell_val == "#no":
                matrix[p.id][t.id] = "#no"
            elif cell_val == "":
                if p.strict:
                    raise PlaylisterError(f"Strict violation at row {t.r_idx} (track '{t.id}') and column {p.col_idx} (playlist {p.display_name}): empty cell.")
                matrix[p.id][t.id] = "#no"
            else:
                try:
                    num = int(cell_val)
                    if num <= 0:
                        raise ValueError()
                    matrix[p.id][t.id] = num
                except ValueError:
                    if p.strict:
                        raise PlaylisterError(f"Invalid input '{cell_val}' at row {t.r_idx} (track '{t.id}') and column {p.col_idx} (playlist {p.display_name}).")
                    else:
                        matrix[p.id][t.id] = "#no"

    # Validation and track sequence ordering (with randomization when duplicate ranks exist)
    for p in playlists:
        p_tracks = []
        for t in tracks:
            val = matrix[p.id][t.id]
            if isinstance(val, int):
                p_tracks.append((val, t.id))

        groups = collections.defaultdict(list)
        for val, t_id in p_tracks:
            groups[val].append(t_id)

        if p.strict:
            for val, t_ids in groups.items():
                if len(t_ids) > 1:
                    raise PlaylisterError(f"Duplicate track order positions in playlist {p.display_name} at column {p.col_idx}")

            sorted_keys = sorted(groups.keys())
            if sorted_keys:
                if sorted_keys[0] != 1:
                    raise PlaylisterError(f"Sequence violation in playlist {p.display_name} at column {p.col_idx}: missing index 1 (found index {sorted_keys[0]})")
                for i in range(len(sorted_keys) - 1):
                    if sorted_keys[i+1] != sorted_keys[i] + 1:
                        raise PlaylisterError(f"Sequence violation in playlist {p.display_name} at column {p.col_idx}: missing index {sorted_keys[i]+1} (found index {sorted_keys[i+1]})")

        sorted_keys = sorted(groups.keys())
        resolved_tracks = []
        rng = random.Random(p.id)
        for val in sorted_keys:
            t_ids = groups[val]
            if len(t_ids) > 1:
                t_ids.sort()
                rng.shuffle(t_ids)
            resolved_tracks.extend(t_ids)

        for t in tracks:
            if t.id in resolved_tracks:
                matrix[p.id][t.id] = resolved_tracks.index(t.id) + 1
            else:
                matrix[p.id][t.id] = "#no"

    return playlists, tracks, matrix
