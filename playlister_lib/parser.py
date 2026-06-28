import csv
import re

class PlaylisterError(Exception):
    pass

class PlaylistData:
    def __init__(self, raw_str):
        self.raw = raw_str.strip()
        self.id = None
        self.title = None
        self.strict = False
        self.ignore = False
        self._parse()

    @property
    def display_name(self):
        if self.title:
            return f"'{self.title}' ('{self.id}')"
        return f"'{self.id}'"

    def _parse(self):
        # Check flags
        if re.search(r'(?:^|\s)#ignore\b', self.raw):
            self.ignore = True
        if re.search(r'(?:^|\s)#strict\b', self.raw):
            self.strict = True

        # Extract playlist ID / URL
        id_match = re.search(r'#playlist:([^\s]+)', self.raw)
        if id_match:
            self.id = self._extract_id(id_match.group(1))

        # Extract title
        title_match = re.search(r'#title:(?:<([^>]*)>|@([^@]*)@|!([^!]*)!)', self.raw)
        if title_match:
            self.title = next(g for g in title_match.groups() if g is not None)

    def _extract_id(self, val):
        # Extract the last path segment before any query parameters
        clean_val = val.split('?')[0].strip('/')
        return clean_val.split('/')[-1]

class TrackData:
    def __init__(self, raw_str):
        self.raw = raw_str.strip()
        self.id = None
        self.title = None
        self.ignore = False
        self._parse()

    def _parse(self):
        if re.search(r'(?:^|\s)#ignore\b', self.raw):
            self.ignore = True

        # Extract track ID / URL
        id_match = re.search(r'#track:([^\s]+)', self.raw)
        if id_match:
            self.id = self._extract_id(id_match.group(1))

        # Extract title
        title_match = re.search(r'#title:(?:<([^>]*)>|@([^@]*)@|!([^!]*)!)', self.raw)
        if title_match:
            self.title = next(g for g in title_match.groups() if g is not None)

    def _extract_id(self, val):
        # Extract the last path segment before any query parameters
        clean_val = val.split('?')[0].strip('/')
        return clean_val.split('/')[-1]


def parse_csv_sheet(fileobj, force_strict=False):
    reader = csv.reader(fileobj)
    try:
        rows = list(reader)
    except Exception as e:
        raise PlaylisterError(f"Failed to read CSV: {e}")
        
    if not rows:
        raise PlaylisterError("CSV is empty.")
    
    header = rows[0]
    playlists = []
    playlist_indices = []
    
    # Parse playlist headers
    for idx, col in enumerate(header):
        if idx == 0:
            continue
        if not col.strip():
            continue
        if '#playlist' not in col:
            continue
        p = PlaylistData(col)
        p.col_idx = idx
        if p.ignore:
            continue
        if not p.id:
            raise PlaylisterError(f"Playlist cell at column {idx} misses a valid playlist ID: '{col}'")
        if force_strict:
            p.strict = True
        playlists.append(p)
        playlist_indices.append((idx, p))
        
    tracks = []
    track_rows = []
    # Parse track rows
    for r_idx, row in enumerate(rows[1:], start=1):
        if not row or not row[0].strip():
            continue
        t = TrackData(row[0])
        t.r_idx = r_idx
        if t.ignore:
            continue
        if not t.id:
            raise PlaylisterError(f"Track cell at row {r_idx} misses a valid track ID: '{row[0]}'")
        tracks.append(t)
        track_rows.append((row, t))

    matrix = {p.id: {} for p in playlists}
    
    # Fill and validate matrix
    for row, t in track_rows:
        for col_idx, p in playlist_indices:
            cell_val = row[col_idx].strip() if col_idx < len(row) else ""
            if cell_val == "#no":
                matrix[p.id][t.id] = "#no"
            elif cell_val == "":
                if p.strict:
                    raise PlaylisterError(f"Strict violation at row {t.r_idx} (track '{t.id}') and column {p.col_idx} (playlist {p.display_name}): empty cell.")
                matrix[p.id][t.id] = "#no"
            else:
                # Check if number
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

    # Final Playlist Validation (Ordering, Completeness & Randomization)
    import collections
    import random

    for p in playlists:
        p_tracks = []
        for t in tracks:
            val = matrix[p.id][t.id]
            if isinstance(val, int):
                p_tracks.append((val, t.id))
                
        # Group by order value
        groups = collections.defaultdict(list)
        for val, t_id in p_tracks:
            groups[val].append(t_id)
            
        if p.strict:
            # Check for duplicate positions
            for val, t_ids in groups.items():
                if len(t_ids) > 1:
                    raise PlaylisterError(f"Duplicate track order positions in playlist {p.display_name} at column {p.col_idx}")
            
            # Check sequence completeness starting at 1 with no gaps
            sorted_keys = sorted(groups.keys())
            if sorted_keys:
                if sorted_keys[0] != 1:
                    raise PlaylisterError(f"Sequence violation in playlist {p.display_name} at column {p.col_idx}: missing index 1 (found index {sorted_keys[0]})")
                for i in range(len(sorted_keys) - 1):
                    if sorted_keys[i+1] != sorted_keys[i] + 1:
                        raise PlaylisterError(f"Sequence violation in playlist {p.display_name} at column {p.col_idx}: missing index {sorted_keys[i]+1} (found index {sorted_keys[i+1]})")
                        
        # Now resolve the track order (with randomization if not strict and duplicates exist)
        sorted_keys = sorted(groups.keys())
        resolved_tracks = []
        rng = random.Random(p.id)
        for val in sorted_keys:
            t_ids = groups[val]
            if len(t_ids) > 1:
                # Shuffle the group to randomize their order.
                # First sort them by ID to ensure stable initial state before shuffle
                t_ids.sort()
                rng.shuffle(t_ids)
            resolved_tracks.extend(t_ids)
            
        # Re-populate the matrix for this playlist with 1-based sequential indices
        for t in tracks:
            if t.id in resolved_tracks:
                matrix[p.id][t.id] = resolved_tracks.index(t.id) + 1
            else:
                matrix[p.id][t.id] = "#no"
                      
    return playlists, tracks, matrix
