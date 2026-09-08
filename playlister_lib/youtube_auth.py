import os
import sys
import json
import urllib.request
import urllib.parse
import time

def resolve_youtube_key_path(custom_path=None):
    if custom_path:
        return os.path.abspath(custom_path)
    return os.path.abspath(os.path.expanduser("~/.playlister"))

def load_client_secrets_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Desktop app client secrets are nested under "installed" or "web"
    cfg = data.get("installed") or data.get("web") or data
    client_id = cfg.get("client_id")
    client_secret = cfg.get("client_secret")
    redirect_uris = cfg.get("redirect_uris", [])
    redirect_uri = redirect_uris[0] if redirect_uris else "http://127.0.0.1:8080"
    return client_id, client_secret, redirect_uri

def _request_token(payload):
    url = "https://oauth2.googleapis.com/token"
    data = urllib.parse.urlencode(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req) as response:
        res = json.loads(response.read().decode("utf-8"))
    return res["access_token"], res.get("refresh_token"), res.get("expires_in", 3600)

def refresh_youtube_token(client_id, client_secret, refresh_token):
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    return _request_token(payload)

def exchange_code_for_token(client_id, client_secret, code, redirect_uri):
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    return _request_token(payload)

def save_youtube_key_file(dir_path, data, silent=False):
    try:
        os.makedirs(dir_path, exist_ok=True)
        keys_path = os.path.join(dir_path, "youtube_keys")
        fd = os.open(keys_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        if not silent:
            print(f"YouTube credentials successfully saved to: {keys_path}")
    except Exception as e:
        print(f"Warning: Failed to save YouTube credentials to file: {e}", file=sys.stderr)

def load_youtube_cache(key_dir):
    dir_path = resolve_youtube_key_path(key_dir)
    cache_path = os.path.join(dir_path, "youtube_cache")
    if os.path.exists(cache_path):
        try:
            fd = os.open(cache_path, os.O_RDONLY)
            with os.fdopen(fd, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_youtube_cache(key_dir, cache_data):
    dir_path = resolve_youtube_key_path(key_dir)
    cache_path = os.path.join(dir_path, "youtube_cache")
    try:
        os.makedirs(dir_path, exist_ok=True)
        fd = os.open(cache_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(cache_data, f, indent=2)
    except Exception:
        pass

def clear_youtube_cache_file(key_dir):
    dir_path = resolve_youtube_key_path(key_dir)
    cache_path = os.path.join(dir_path, "youtube_cache")
    if os.path.exists(cache_path):
        try:
            os.remove(cache_path)
            print("YouTube cache cleared successfully.")
        except Exception as e:
            print(f"Error clearing YouTube cache: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("No YouTube cache found to clear.")

def clear_youtube_keys_file(key_dir):
    dir_path = resolve_youtube_key_path(key_dir)
    keys_path = os.path.join(dir_path, "youtube_keys")
    if os.path.exists(keys_path):
        try:
            os.remove(keys_path)
            print(f"YouTube credentials file successfully deleted: {keys_path}")
        except Exception as e:
            print(f"Error: Failed to delete YouTube credentials file '{keys_path}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"No YouTube credentials found to delete at: {keys_path}")

def get_youtube_api_key(key_dir=None, no_store_key=False, client_secrets_path=None):
    path = resolve_youtube_key_path(key_dir)
    os.makedirs(path, exist_ok=True)
    
    keys_path = os.path.join(path, "youtube_keys")
    data = {}
    if os.path.exists(keys_path):
        try:
            fd = os.open(keys_path, os.O_RDONLY)
            with os.fdopen(fd, "r") as f:
                data = json.load(f)
        except Exception:
            pass

    client_id = os.environ.get("YOUTUBE_CLIENT_ID") or data.get("client_id")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET") or data.get("client_secret")
    redirect_uri = os.environ.get("YOUTUBE_REDIRECT_URI") or data.get("redirect_uri") or "http://127.0.0.1:8080"

    if client_secrets_path and os.path.exists(client_secrets_path):
        try:
            cs_id, cs_secret, cs_redir = load_client_secrets_json(client_secrets_path)
            if cs_id:
                client_id = cs_id
            if cs_secret:
                client_secret = cs_secret
            if cs_redir:
                redirect_uri = cs_redir
        except Exception as e:
            print(f"Warning: Failed to parse client secrets file: {e}", file=sys.stderr)

    newly_prompted = False
    if not client_id or not client_secret:
        newly_prompted = True
        print("\n" + "=" * 80)
        print("                   YOUTUBE API CREDENTIALS REQUIRED")
        print("=" * 80)
        print("YouTube Data API Credentials (Client ID and Client Secret) are missing.\n")
        print("To obtain them (100% free, no credit card required):")
        print("  1. Go to Google Cloud Console: https://console.cloud.google.com/")
        print("  2. Create a new project (e.g. 'Playlister').")
        print("  3. Go to 'APIs & Services' > 'Enabled APIs & Services', click '+ ENABLE APIS AND SERVICES'")
        print("     and enable 'YouTube Data API v3'.")
        print("  4. Go to 'APIs & Services' > 'OAuth consent screen':")
        print("     - Choose 'External', enter an App name, and save.")
        print("     - Under 'Test users', click '+ ADD USERS' and add your Google account email.")
        print("  5. Go to 'APIs & Services' > 'Credentials':")
        print("     - Click '+ CREATE CREDENTIALS' > 'OAuth client ID'.")
        print("     - Select Application type: 'Desktop app' (or 'Web application' with redirect URI")
        print("       'http://127.0.0.1:8080').")
        print("     - Copy your Client ID and Client Secret, or download client_secrets.json.\n")
        print("Note: Running with --no_store_key will prompt for credentials without saving them.")
        print("=" * 80 + "\n")
        try:
            secrets_file_input = input("Enter path to downloaded client_secrets.json (or press Enter to type manually): ").strip()
            if secrets_file_input and os.path.exists(os.path.expanduser(secrets_file_input)):
                cs_id, cs_secret, cs_redir = load_client_secrets_json(os.path.expanduser(secrets_file_input))
                client_id = cs_id
                client_secret = cs_secret
                if cs_redir:
                    redirect_uri = cs_redir
            else:
                if not client_id:
                    client_id = input("Enter YouTube Client ID: ").strip()
                if not client_secret:
                    client_secret = input("Enter YouTube Client Secret: ").strip()
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            sys.exit(1)

        if not client_id or not client_secret:
            print("Error: YouTube Client ID and Client Secret are required.", file=sys.stderr)
            sys.exit(1)

    data["client_id"] = client_id
    data["client_secret"] = client_secret
    data["redirect_uri"] = redirect_uri

    scopes = "https://www.googleapis.com/auth/youtube"

    access_token = data.get("access_token")
    expires_at = data.get("expires_at", 0)
    refresh_token = data.get("refresh_token")

    if access_token and time.time() < expires_at - 60:
        if newly_prompted and not no_store_key:
            save_youtube_key_file(path, data, silent=False)
        return access_token

    if refresh_token:
        try:
            new_access, new_refresh, new_expires_in = refresh_youtube_token(client_id, client_secret, refresh_token)
            data["access_token"] = new_access
            data["expires_at"] = time.time() + new_expires_in
            if new_refresh:
                data["refresh_token"] = new_refresh
            if not no_store_key:
                save_youtube_key_file(path, data, silent=True)
            return new_access
        except Exception as e:
            print(f"Warning: Failed to refresh YouTube token: {e}. Re-authenticating...", file=sys.stderr)

    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        + urllib.parse.urlencode({
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": scopes,
            "access_type": "offline",
            "prompt": "consent"
        })
    )

    try:
        import webbrowser
        webbrowser.open(auth_url)
    except Exception:
        pass

    print("\nYouTube Authorization Required:")
    print("Navigate to the following URL in your browser to authorize access to YouTube playlists:")
    print(auth_url)
    print()
    print("Note: If Google shows an 'unverified app' warning, click 'Advanced' -> 'Go to <app> (unsafe)'.")
    print(f"After approving, your browser will redirect to a URL starting with '{redirect_uri}'.")
    print("Simply COPY the entire redirected URL from your browser's address bar (containing '?code=...')")
    print("or the code parameter, and paste it below.")
    print()
    try:
        redirected_url = input("Enter the URL or authorization code: ").strip()
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
        if new_refresh:
            data["refresh_token"] = new_refresh
        data["expires_at"] = time.time() + new_expires_in
        if not no_store_key:
            save_youtube_key_file(path, data, silent=False)
        return new_access
    except Exception as e:
        print(f"Error: Failed to obtain YouTube access token: {e}", file=sys.stderr)
        sys.exit(1)
