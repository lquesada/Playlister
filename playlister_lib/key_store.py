import os
import sys
import json
import urllib.request
import urllib.parse
import base64
import time

def resolve_key_path(custom_path=None):
    if custom_path:
        return os.path.abspath(custom_path)
    return os.path.abspath(os.path.expanduser("~/.playlister"))

def _request_token(client_id, client_secret, payload):
    url = "https://accounts.spotify.com/api/token"
    data = urllib.parse.urlencode(payload).encode("utf-8")
    
    auth_str = f"{client_id}:{client_secret}"
    auth_b64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req) as response:
        res = json.loads(response.read().decode("utf-8"))
        
    return res["access_token"], res.get("refresh_token"), res["expires_in"]

def refresh_spotify_token(client_id, client_secret, refresh_token):
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    return _request_token(client_id, client_secret, payload)

def exchange_code_for_token(client_id, client_secret, code, redirect_uri):
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri
    }
    return _request_token(client_id, client_secret, payload)

def migrate_if_needed(dir_path):
    if os.path.exists(dir_path) and os.path.isfile(dir_path):
        try:
            with open(dir_path, "r") as f:
                migrated_data = json.load(f)
            os.remove(dir_path)
            os.makedirs(dir_path, exist_ok=True)
            keys_path = os.path.join(dir_path, "keys")
            fd = os.open(keys_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                json.dump(migrated_data, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to migrate credentials file to directory: {e}", file=sys.stderr)

def save_key_file(dir_path, data, silent=False):
    try:
        os.makedirs(dir_path, exist_ok=True)
        keys_path = os.path.join(dir_path, "keys")
        fd = os.open(keys_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        if not silent:
            print(f"Credentials successfully saved to: {keys_path}")
    except Exception as e:
        print(f"Warning: Failed to save credentials to file: {e}", file=sys.stderr)

def load_cache(key_dir):
    dir_path = resolve_key_path(key_dir)
    cache_path = os.path.join(dir_path, "cache")
    if os.path.exists(cache_path):
        try:
            fd = os.open(cache_path, os.O_RDONLY)
            with os.fdopen(fd, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_cache(key_dir, cache_data):
    dir_path = resolve_key_path(key_dir)
    cache_path = os.path.join(dir_path, "cache")
    try:
        os.makedirs(dir_path, exist_ok=True)
        fd = os.open(cache_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(cache_data, f, indent=2)
    except Exception:
        pass

def clear_cache_file(key_dir):
    dir_path = resolve_key_path(key_dir)
    cache_path = os.path.join(dir_path, "cache")
    if os.path.exists(cache_path):
        try:
            os.remove(cache_path)
            print("Cache cleared successfully.")
        except Exception as e:
            print(f"Error clearing cache: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("No cache found to clear.")

def get_api_key(key_dir=None, no_store_key=False):
    path = resolve_key_path(key_dir)
    migrate_if_needed(path)
    os.makedirs(path, exist_ok=True)
    print(f"Using API key directory: {path}\n")
    
    keys_path = os.path.join(path, "keys")
    data = {}
    if os.path.exists(keys_path):
        try:
            fd = os.open(keys_path, os.O_RDONLY)
            with os.fdopen(fd, "r") as f:
                data = json.load(f)
        except Exception:
            pass

    newly_prompted = False
    client_id = os.environ.get("SPOTIPY_CLIENT_ID") or data.get("client_id")
    client_secret = os.environ.get("SPOTIPY_CLIENT_SECRET") or data.get("client_secret")
    redirect_uri = os.environ.get("SPOTIPY_REDIRECT_URI") or data.get("redirect_uri")

    if not client_id or not client_secret or not redirect_uri:
        newly_prompted = True
        print("\n" + "=" * 80)
        print("                   SPOTIFY API CREDENTIALS REQUIRED")
        print("=" * 80)
        print("Spotify API Credentials (Client ID, Client Secret, and Redirect URI) are missing.\n")
        print("To obtain them:")
        print("  1. Go to the Spotify Developer Dashboard: https://developer.spotify.com/dashboard")
        print("  2. Create an application to get your Client ID and Client Secret.")
        print("  3. Configure a Redirect URI in your Spotify Application Settings on the dashboard.")
        print("     IMPORTANT: You must add a redirect URI (such as 'http://127.0.0.1:8000/callback')")
        print("     to the Redirect URIs in your Spotify App Settings and input the EXACT")
        print("     SAME redirect URI below when prompted.\n")
        print("Note: Running with --no_store_key will ask for the credentials and never save them.")
        print("=" * 80 + "\n")
        try:
            if not client_id:
                client_id = input("Enter Spotify Client ID: ").strip()
            if not client_secret:
                client_secret = input("Enter Spotify Client Secret: ").strip()
            if not redirect_uri:
                redirect_uri = input("Enter Spotify Redirect URI [default: http://127.0.0.1:8000/callback]: ").strip()
                if not redirect_uri:
                    redirect_uri = "http://127.0.0.1:8000/callback"
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            sys.exit(1)
            
        if not client_id or not client_secret or not redirect_uri:
            print("Error: Spotify Client ID, Client Secret, and Redirect URI are required.", file=sys.stderr)
            sys.exit(1)

    data["client_id"] = client_id
    data["client_secret"] = client_secret
    data["redirect_uri"] = redirect_uri

    scopes = "playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative user-read-private"

    saved_scopes = data.get("scopes", "")
    requested_set = set(scopes.split())
    saved_set = set(saved_scopes.split())
    has_all_scopes = requested_set.issubset(saved_set)

    access_token = data.get("access_token")
    expires_at = data.get("expires_at", 0)
    refresh_token = data.get("refresh_token")

    if has_all_scopes and access_token and time.time() < expires_at - 60:
        if newly_prompted and not no_store_key:
            data["scopes"] = scopes
            save_key_file(path, data, silent=False)
        return access_token

    if has_all_scopes and refresh_token:
        try:
            new_access, new_refresh, new_expires_in = refresh_spotify_token(client_id, client_secret, refresh_token)
            data["access_token"] = new_access
            data["expires_at"] = time.time() + new_expires_in
            if new_refresh:
                data["refresh_token"] = new_refresh
            if not no_store_key:
                save_key_file(path, data, silent=True)
            return new_access
        except Exception as e:
            print(f"Warning: Failed to refresh token: {e}. Re-authenticating...", file=sys.stderr)

    auth_url = (
        "https://accounts.spotify.com/authorize?"
        + urllib.parse.urlencode({
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": scopes
        })
    )
    
    try:
        import webbrowser
        webbrowser.open(auth_url)
    except Exception:
        pass
        
    print("\nAuthorization Required:")
    print(f"Please add '{redirect_uri}' to the Redirect URIs in your Spotify App Settings.")
    print("Navigate to the following URL in your browser to authorize the application:")
    print(auth_url)
    print()
    print("Note: After you click 'Agree' on the Spotify page, your browser will redirect to a URL")
    print("starting with your redirect URI (which may fail to load / show a 'Site Can't Be Reached' page).")
    print("This is normal and expected! Simply COPY the entire URL from your browser's address bar")
    print("(it should contain '?code=...') and paste it below.")
    print()
    try:
        redirected_url = input("Enter the URL you were redirected to: ").strip()
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        sys.exit(1)

    parsed_url = urllib.parse.urlparse(redirected_url)
    params = urllib.parse.parse_qs(parsed_url.query)
    code = params.get("code")
    if not code:
        if redirected_url.startswith("http") or redirected_url.startswith("/"):
            print("Error: Could not find 'code' parameter in the redirected URL.", file=sys.stderr)
            sys.exit(1)
        code = [redirected_url]

    try:
        new_access, new_refresh, new_expires_in = exchange_code_for_token(client_id, client_secret, code[0], redirect_uri)
        data["access_token"] = new_access
        data["refresh_token"] = new_refresh
        data["expires_at"] = time.time() + new_expires_in
        data["scopes"] = scopes
        if not no_store_key:
            save_key_file(path, data, silent=False)
        return new_access
    except Exception as e:
        print(f"Error: Failed to obtain access token: {e}", file=sys.stderr)
        sys.exit(1)
