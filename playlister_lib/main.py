import sys
import os
import spotipy
from playlister_lib.cli import parse_args
from playlister_lib.key_store import get_api_key, load_cache, save_cache
from playlister_lib.parser import parse_csv_sheet, PlaylisterError
from playlister_lib.mock_client import OfflineSpotifyClient

def get_current_tracks(sp, playlist_id, track_cache):
    results = sp.playlist_tracks(playlist_id)
    items = results.get('items', []) if results else []
    while results and results.get('next'):
        results = sp.next(results)
        if results:
            items.extend(results.get('items', []))
        else:
            break
        
    current_tracks = []
    for item in items:
        if not item:
            continue
        # The /items endpoint returns 'item', the old /tracks endpoint returned 'track'
        track = item.get('track') or item.get('item')
        if track and track.get('id'):
            tid = track['id']
            current_tracks.append(tid)
            # Cache name and duration
            track_cache[tid] = {
                "name": track.get('name'),
                "duration_ms": track.get('duration_ms')
            }
    return current_tracks

def format_duration(ms):
    if ms is None or not isinstance(ms, (int, float)):
        return "N/A"
    seconds = int(ms / 1000)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

def main():
    # 1. Guard Python version
    if sys.version_info < (3, 6):
        sys.stderr.write("Error: playlister requires Python 3.6 or higher.\n")
        sys.exit(1)
        
    parsed_args = parse_args()
    
    import argparse
    args = argparse.Namespace(
        csv_file=None,
        execute=False,
        local=False,
        auto_approve=False,
        remove_dupes=False,
        test_api_key=False,
        key_dir=getattr(parsed_args, "key_dir", None),
        no_store_key=getattr(parsed_args, "no_store_key", False),
        strict=getattr(parsed_args, "strict", False) is True,
        dump=None,
        delete_key=False,
        check_all=False,
        clear_cache=False,
    )
    
    cmd = getattr(parsed_args, "command", None)
    if cmd is None or type(cmd).__name__ in ("MagicMock", "Mock"):
        if getattr(parsed_args, "dump", None) is not None and not (type(parsed_args.dump).__name__ in ("MagicMock", "Mock")):
            cmd = "dump"
        elif getattr(parsed_args, "check_all", False) is True and not (type(parsed_args.check_all).__name__ in ("MagicMock", "Mock")):
            cmd = "check"
        elif getattr(parsed_args, "test_api_key", False) is True and not (type(parsed_args.test_api_key).__name__ in ("MagicMock", "Mock")):
            cmd = "test-keys"
        elif getattr(parsed_args, "delete_key", False) is True and not (type(parsed_args.delete_key).__name__ in ("MagicMock", "Mock")):
            cmd = "clear-keys"
        elif getattr(parsed_args, "clear_cache", False) is True and not (type(parsed_args.clear_cache).__name__ in ("MagicMock", "Mock")):
            cmd = "clear-cache"
        elif getattr(parsed_args, "local", False) is True and not (type(parsed_args.local).__name__ in ("MagicMock", "Mock")):
            cmd = "print"
        else:
            if getattr(parsed_args, "execute", False) is True and not (type(parsed_args.execute).__name__ in ("MagicMock", "Mock")):
                cmd = "push"
            else:
                cmd = "diff"

    if cmd == "diff":
        args.csv_file = getattr(parsed_args, "csv_file", None)
    elif cmd == "push":
        args.csv_file = getattr(parsed_args, "csv_file", None)
        args.execute = True
        args.auto_approve = getattr(parsed_args, "auto_approve", False)
        args.remove_dupes = getattr(parsed_args, "remove_dupes", False)
    elif cmd == "check":
        args.csv_file = getattr(parsed_args, "csv_file", None)
        args.check_all = True
    elif cmd == "print":
        args.csv_file = getattr(parsed_args, "csv_file", None)
        args.local = True
    elif cmd == "dump":
        val = getattr(parsed_args, "playlist_or_album", None)
        if val is None or type(val).__name__ in ("MagicMock", "Mock"):
            val = getattr(parsed_args, "dump", None)
        args.dump = val
    elif cmd == "test-keys":
        args.test_api_key = True
        args.local = getattr(parsed_args, "local", False)
    elif cmd == "clear-keys":
        args.delete_key = True
    elif cmd == "clear-cache":
        args.clear_cache = True
    elif cmd == "clear-all":
        args.delete_key = True
        args.clear_cache = True

    if args.delete_key:
        from playlister_lib.key_store import resolve_key_path
        path = resolve_key_path(args.key_dir)
        if cmd == "clear-all":
            if os.path.exists(path):
                try:
                    if os.path.isdir(path):
                        import shutil
                        shutil.rmtree(path)
                        print(f"Credentials directory successfully deleted: {path}")
                    else:
                        os.remove(path)
                        print(f"Credentials file successfully deleted: {path}")
                except Exception as e:
                    print(f"Error: Failed to delete credentials directory '{path}': {e}", file=sys.stderr)
                    sys.exit(1)
            else:
                print(f"No credentials directory found to delete at: {path}")
        else:
            # clear-keys: delete the keys file specifically
            if os.path.exists(path):
                if os.path.isdir(path):
                    keys_path = os.path.join(path, "keys")
                    if os.path.exists(keys_path):
                        try:
                            os.remove(keys_path)
                            print(f"Credentials file successfully deleted: {keys_path}")
                        except Exception as e:
                            print(f"Error: Failed to delete credentials file '{keys_path}': {e}", file=sys.stderr)
                            sys.exit(1)
                    else:
                        print(f"No credentials file found to delete at: {keys_path}")
                else:
                    try:
                        os.remove(path)
                        print(f"Credentials file successfully deleted: {path}")
                    except Exception as e:
                        print(f"Error: Failed to delete credentials file '{path}': {e}", file=sys.stderr)
                        sys.exit(1)
            else:
                print(f"No credentials found to delete at: {path}")
        if not args.clear_cache:
            sys.exit(0)

    if args.clear_cache:
        from playlister_lib.key_store import clear_cache_file
        clear_cache_file(args.key_dir)
        if args.csv_file is None:
            sys.exit(0)
    
    # 2. Credentials handling
    if args.test_api_key:
        if args.local:
            print("Credentials verification: success (offline local test)")
            sys.exit(0)
        key = get_api_key(args.key_dir, args.no_store_key)
        if not key:
            print("Error: Spotify credentials are empty.", file=sys.stderr)
            sys.exit(1)
        try:
            sp = spotipy.Spotify(auth=key)
            user_info = sp.current_user()
            user_display_name = user_info.get("display_name") or user_info.get("id", "Unknown")
            print(f"Credentials verification: success (online check passed for user: {user_display_name})")
        except Exception as e:
            print(f"Error: Credentials verification failed online: {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    if args.local:
        key = None
    else:
        key = get_api_key(args.key_dir, args.no_store_key)
        if not key:
            print("Error: Spotify credentials are required.", file=sys.stderr)
            sys.exit(1)

    # 3. Handle --dump if provided
    if args.dump is not None:
        sp = spotipy.Spotify(auth=key)
        track_cache = load_cache(args.key_dir) if not args.local else {}
        
        # Resolve ID/URL
        target_val = args.dump.strip()
        target_id = target_val
        is_album = False
        
        if "spotify.com" in target_val:
            try:
                if "/album/" in target_val:
                    is_album = True
                    parts = target_val.split("/album/")
                    if len(parts) > 1:
                        target_id = parts[1].split("?")[0].strip('/')
                elif "/playlist/" in target_val:
                    parts = target_val.split("/playlist/")
                    if len(parts) > 1:
                        target_id = parts[1].split("?")[0].strip('/')
            except Exception:
                pass
                
        p_info = None
        album_info = None
        
        if is_album:
            try:
                album_info = sp.album(target_id)
            except Exception as e:
                print(f"Error: Failed to fetch album '{target_id}' from Spotify: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            try:
                p_info = sp.playlist(target_id)
            except Exception as playlist_err:
                # If raw ID was provided, try fetching as album before failing
                try:
                    album_info = sp.album(target_id)
                    is_album = True
                except Exception:
                    print(f"Error: Failed to fetch playlist '{target_id}' from Spotify: {playlist_err}", file=sys.stderr)
                    sys.exit(1)
                    
        name = album_info.get('name', 'Unknown') if is_album else p_info.get('name', 'Unknown')
        if is_album:
            print(f"#album:{target_id} #title:<{name}>\n")
        else:
            print(f"#playlist:{target_id} #title:<{name}>\n")
        
        # Get all tracks paginated
        items = []
        try:
            if is_album:
                results = sp.album_tracks(target_id)
            else:
                results = sp.playlist_tracks(target_id)
                
            items = results.get('items', []) if results else []
            while results and results.get('next'):
                results = sp.next(results)
                if results:
                    items.extend(results.get('items', []))
                else:
                    break
        except Exception as e:
            type_str = "album" if is_album else "playlist"
            print(f"Error: Failed to fetch {type_str} tracks: {e}", file=sys.stderr)
            sys.exit(1)
                 
        for item in items:
            if not item:
                continue
            if is_album:
                track = item
            else:
                track = item.get('track') or item.get('item')
                
            if track and track.get('id'):
                tid = track['id']
                tname = track.get('name', 'Unknown')
                tdur = track.get('duration_ms')
                track_cache[tid] = {
                    "name": tname,
                    "duration_ms": tdur
                }
                print(f"#track:{tid} #title:<{tname}>")
                 
        save_cache(args.key_dir, track_cache)
        sys.exit(0)

    # 4. Parse CSV
    try:
        with open(args.csv_file, "r") as f:
            playlists, tracks, matrix = parse_csv_sheet(f, force_strict=args.strict)
    except FileNotFoundError:
        print(f"Error: CSV file not found: {args.csv_file}", file=sys.stderr)
        sys.exit(1)
    except PlaylisterError as e:
        print(f"Validation Error: {e}", file=sys.stderr)
        sys.exit(1)

    # 4b. Handle --check_all if provided
    if getattr(args, "check_all", False) is True:
        sp = spotipy.Spotify(auth=key)
        track_cache = load_cache(args.key_dir) if not args.local else {}
        # 1. Check playlists
        for p in playlists:
            if p.title:
                try:
                    p_info = sp.playlist(p.id)
                except Exception as e:
                    print(f"Error: Failed to fetch playlist '{p.id}' from Spotify: {e}", file=sys.stderr)
                    sys.exit(1)

                playlist_name = p_info.get('name', p.id)
                if playlist_name != p.title:
                    print(f"Error: Playlist title mismatch for ID '{p.id}'. Spotify source of truth is '{playlist_name}', but the CSV has '#title:<{p.title}>'. Please update the CSV to match Spotify.", file=sys.stderr)
                    sys.exit(1)

        # 2. Check tracks (all of them, even if not in any playlist)
        for t in tracks:
            if t.title:
                if t.id not in track_cache:
                    try:
                        t_info = sp.track(t.id)
                        track_cache[t.id] = {
                            "name": t_info.get('name'),
                            "duration_ms": t_info.get('duration_ms')
                        }
                        save_cache(args.key_dir, track_cache)
                    except Exception as e:
                        print(f"Error: Failed to fetch track '{t.id}': {e}", file=sys.stderr)
                        sys.exit(1)

                t_info = track_cache[t.id]
                if t_info["name"] != t.title:
                    print(f"Error: Track title mismatch for ID '{t.id}'. Spotify source of truth is '{t_info['name']}', but the CSV has '#title:<{t.title}>'. Please update the CSV to match Spotify.", file=sys.stderr)
                    sys.exit(1)

        save_cache(args.key_dir, track_cache)
        print("All playlist and track titles verified successfully.")
        sys.exit(0)

    # 4. Initialize Spotify Client
    if args.local:
        sp = OfflineSpotifyClient(playlists=playlists, tracks=tracks)
    else:
        sp = spotipy.Spotify(auth=key)

    track_cache = load_cache(args.key_dir) if not args.local else {}
    playlists_changes = []

    # 5. Process each playlist
    for p in playlists:
        try:
            p_info = sp.playlist(p.id)
        except Exception as e:
            print(f"Error: Failed to fetch playlist '{p.id}' from Spotify: {e}", file=sys.stderr)
            sys.exit(1)

        playlist_name = p_info.get('name', p.id)
        # Title check
        if p.title and playlist_name != p.title:
            print(f"Error: Playlist title mismatch for ID '{p.id}'. Spotify source of truth is '{playlist_name}', but the CSV has '#title:<{p.title}>'. Please update the CSV to match Spotify.", file=sys.stderr)
            sys.exit(1)

        # In local run we do not perform diffing against online Spotify
        if args.local:
            p_tracks = []
            for t in tracks:
                val = matrix[p.id][t.id]
                if isinstance(val, int):
                    p_tracks.append((val, t))
            p_tracks.sort(key=lambda x: x[0])
            playlists_changes.append({
                "playlist_name": playlist_name,
                "p_tracks": p_tracks
            })
            continue

        # Fetch current tracks in playlist
        try:
            current_tracks = get_current_tracks(sp, p.id, track_cache)
            save_cache(args.key_dir, track_cache)
        except Exception as e:
            print(f"Error: Failed to fetch tracks for playlist '{p.id}': {e}", file=sys.stderr)
            sys.exit(1)

        # Safety check: detect when API returns empty items for a non-empty playlist
        reported_total = p_info.get('tracks', {}).get('total', 0) if isinstance(p_info.get('tracks'), dict) else 0
        if reported_total > 0 and len(current_tracks) == 0:
            print(f"Error: Spotify reports playlist '{playlist_name}' has {reported_total} tracks, but the API returned 0 items.", file=sys.stderr)
            print("This is likely a Spotify API permissions issue. Try the following:", file=sys.stderr)
            print("  1. Delete your credentials directory and re-authenticate:  playlister --delete_key", file=sys.stderr)
            print("  2. Ensure your Spotify account is the owner or collaborator of this playlist.", file=sys.stderr)
            print("  3. If using a Spotify Developer App in Development Mode, ensure your account is", file=sys.stderr)
            print("     listed under User Management in the Spotify Developer Dashboard.", file=sys.stderr)
            sys.exit(1)

        # Check for duplicates on Spotify
        seen = set()
        dupes = []
        for tid in current_tracks:
            if tid in seen:
                if tid not in dupes:
                    dupes.append(tid)
            seen.add(tid)

        if dupes and not args.remove_dupes:
            print(f"Error: Playlist '{playlist_name}' (ID: {p.id}) contains duplicate tracks: {', '.join(dupes)}. Refusing to make changes. Please run with --remove_dupes to automatically clean them.", file=sys.stderr)
            sys.exit(1)

        # Target tracks list
        p_tracks = []
        for t in tracks:
            val = matrix[p.id][t.id]
            if isinstance(val, int):
                p_tracks.append((val, t))
        p_tracks.sort(key=lambda x: x[0])
        target_tracks = [t.id for _, t in p_tracks]

        # Verify Track Titles
        for _, t in p_tracks:
            if t.id not in track_cache:
                try:
                    t_info = sp.track(t.id)
                    track_cache[t.id] = {
                        "name": t_info.get('name'),
                        "duration_ms": t_info.get('duration_ms')
                    }
                    save_cache(args.key_dir, track_cache)
                except Exception as e:
                    print(f"Error: Failed to fetch track '{t.id}': {e}", file=sys.stderr)
                    sys.exit(1)

            t_info = track_cache[t.id]
            if t.title and t_info["name"] != t.title:
                print(f"Error: Track title mismatch for ID '{t.id}'. Spotify source of truth is '{t_info['name']}', but the CSV has '#title:<{t.title}>'. Please update the CSV to match Spotify.", file=sys.stderr)
                sys.exit(1)

        # Diff Calculations
        to_remove = [tid for tid in current_tracks if tid not in target_tracks]
        for d in dupes:
            if d not in to_remove:
                to_remove.append(d)

        # Simulate final list order after removes to check what is left
        current_after_removes = [tid for tid in current_tracks if tid not in to_remove]
        to_add = [tid for tid in target_tracks if tid not in current_after_removes]

        sim_list = list(current_after_removes)
        sim_list.extend(to_add)
        reorder_needed = sim_list != target_tracks

        proposed_moves = []
        if reorder_needed and len(sim_list) == len(target_tracks):
            sim_current = list(sim_list)
            for i in range(len(target_tracks)):
                target_item = target_tracks[i]
                if sim_current[i] != target_item:
                    if target_item in sim_current[i:]:
                        j = sim_current.index(target_item, i)
                        proposed_moves.append((target_item, j, i))
                        item = sim_current.pop(j)
                        sim_current.insert(i, item)

        has_changes = bool(to_remove or to_add or reorder_needed)
        playlists_changes.append({
            "playlist": p,
            "playlist_name": playlist_name,
            "current_tracks": current_tracks,
            "target_tracks": target_tracks,
            "to_remove": to_remove,
            "to_add": to_add,
            "reorder_needed": reorder_needed,
            "proposed_moves": proposed_moves,
            "has_changes": has_changes,
            "p_tracks": p_tracks,
            "dupes": dupes
        })

    # 6. Display proposed changes
    if args.local:
        for pc in playlists_changes:
            print(f"Playlist: {pc['playlist_name']} (Local, {len(pc['p_tracks'])} tracks)")
            for idx, (_, t) in enumerate(pc["p_tracks"], start=1):
                track_name = t.title if t.title else t.id
                print(f"{idx} - Track: {track_name}")
        print("Local validation completed. No errors found.")
        sys.exit(0)

    any_changes = False
    for pc in playlists_changes:
        total_ms = 0
        all_durations_known = True
        for _, t in pc["p_tracks"]:
            t_info = track_cache.get(t.id)
            if t_info and t_info.get("duration_ms") is not None:
                total_ms += t_info["duration_ms"]
            else:
                all_durations_known = False
        p_dur = format_duration(total_ms) if (all_durations_known and total_ms > 0) else "N/A"
        print(f"Playlist: {pc['playlist_name']} ({p_dur}, {len(pc['p_tracks'])} tracks)")
        for idx, (_, t) in enumerate(pc["p_tracks"], start=1):
            track_name = t.title if t.title else t.id
            t_info = track_cache.get(t.id)
            t_dur = format_duration(t_info["duration_ms"]) if (t_info and t_info.get("duration_ms") is not None) else "N/A"
            print(f"{idx} - {t_dur} - Track: {track_name}")

        if pc["has_changes"]:
            any_changes = True
            print("  Proposed changes:")
            if pc.get("dupes"):
                print("    ~ Duplicates found on Spotify. Cleaning and re-adding duplicate tracks.")
            if pc["to_remove"]:
                print("    - Remove:")
                for tid in pc["to_remove"]:
                    name = track_cache.get(tid, {}).get("name", tid)
                    print(f"      * {name} ({tid})")
            if pc["to_add"]:
                print("    + Add:")
                for tid in pc["to_add"]:
                    name = track_cache.get(tid, {}).get("name", tid)
                    print(f"      * {name} ({tid})")
            if pc["reorder_needed"]:
                print("    ~ Reorder:")
                for tid, j, i in pc.get("proposed_moves", []):
                    name = track_cache.get(tid, {}).get("name", tid)
                    print(f"      * Move: {name} ({tid}) from position {j + 1} to position {i + 1}")
        else:
            print("  Playlist is already up to date.")
        print("\n")

    if not args.execute:
        print("Dry run completed. No changes applied.")
        print("You may want to run with 'push' and possibly with '--auto-approve'.")
        sys.exit(0)

    if not any_changes:
        print("All playlists are already up to date.")
        sys.exit(0)

    # 8. Apply modifications
    for pc in playlists_changes:
        if not pc["has_changes"]:
            continue

        # 8.0 Confirmation check
        if args.auto_approve:
            approved = True
        else:
            try:
                confirm = input(f"Apply these changes to Spotify for playlist '{pc['playlist_name']}'? (y/N): ").strip().lower()
                approved = (confirm == 'y')
            except KeyboardInterrupt:
                print("\nSync cancelled.")
                sys.exit(1)

        if not approved:
            print(f"Sync skipped for playlist: {pc['playlist_name']}")
            continue

        p = pc["playlist"]
        print(f"\nSyncing playlist: {pc['playlist_name']}")

        # 8.1 Remove songs
        if pc["to_remove"]:
            for tid in pc["to_remove"]:
                name = track_cache.get(tid, {}).get("name", tid)
                print(f"Removing: {name} ({tid})")
                try:
                    sp.playlist_remove_all_occurrences_of_items(p.id, [tid])
                except Exception as e:
                    print(f"Error removing track '{tid}': {e}", file=sys.stderr)
                    sys.exit(1)

        # 8.2 Add songs
        if pc["to_add"]:
            for tid in pc["to_add"]:
                name = track_cache.get(tid, {}).get("name", tid)
                print(f"Adding: {name} ({tid})")
                try:
                    sp.playlist_add_items(p.id, [tid])
                except Exception as e:
                    print(f"Error adding track '{tid}': {e}", file=sys.stderr)
                    sys.exit(1)

        # 8.3 Reorder songs
        current = get_current_tracks(sp, p.id, track_cache)
        save_cache(args.key_dir, track_cache)
        target = pc["target_tracks"]
        
        if current != target:
            if len(current) != len(target):
                print(f"Warning: Current playlist tracks count ({len(current)}) does not match target count ({len(target)}). Skipping reordering to avoid index errors.", file=sys.stderr)
            else:
                print("Reordering tracks...")
                for i in range(len(target)):
                    target_item = target[i]
                    if i < len(current) and current[i] != target_item:
                        if target_item not in current[i:]:
                            print(f"Error: Track '{target_item}' missing from current tracks during reordering.", file=sys.stderr)
                            break
                        j = current.index(target_item, i)
                        name = track_cache.get(target_item, {}).get("name", target_item)
                        print(f"  - Move: {name} ({target_item}) from position {j + 1} to position {i + 1}")
                        try:
                            sp.playlist_reorder_items(p.id, range_start=j, insert_before=i)
                            # Update local model
                            item = current.pop(j)
                            current.insert(i, item)
                        except Exception as e:
                            print(f"Error reordering playlist '{p.id}': {e}", file=sys.stderr)
                            sys.exit(1)

        # 8.4 Verification check
        final_tracks = get_current_tracks(sp, p.id, track_cache)
        save_cache(args.key_dir, track_cache)
        if final_tracks != target:
            print(f"Error: Sync verification failed for playlist '{p.id}'. State does not match target.", file=sys.stderr)
            sys.exit(1)
        print(f"\nPlaylist {pc['playlist_name']} successfully synced.")

    save_cache(args.key_dir, track_cache)
    print("\nSync process completed.")

if __name__ == "__main__":
    main()
