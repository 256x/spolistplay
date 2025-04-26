import os
import sys
import time
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

# Iceberg color scheme
ICEBERG = {
    "fg": "\033[38;2;143;161;179m",
    "title": "\033[38;2;94;129;172m",
    "artist": "\033[38;2;131;148;150m",
    "album": "\033[38;2;198;208;245m",
    "query": "\033[38;2;136;192;208m",
    "num": "\033[38;2;163;190;140m",
    "info": "\033[38;2;208;135;112m",
    "reset": "\033[0m"
}

POLLING_INTERVAL = 2

def clear_screen():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')

def iceberg_print(msg, color="fg", end="\n"):
    print(f"{ICEBERG[color]}{msg}{ICEBERG['reset']}", end=end, flush=True)

def print_header():
    iceberg_print("- Spotify playlist player\n", "fg")

def print_track_info(track):
    artists = ', '.join(artist['name'] for artist in track['artists'])
    title = track['name']
    album_name = track['album']['name']
    release_date = track['album'].get('release_date', '')
    year = release_date.split('-')[0] if release_date else ''
    iceberg_print(f"♪    {title:<28} - {artists}", "title")
    iceberg_print(f"󰀥    {album_name} ({year})", "album")

def select_from_list(items, key="name", prompt="Select:", show_type=False):
    valid_items = [item for item in items if item is not None and key in item]
    max_index_len = len(str(len(valid_items)-1))
    if show_type:
        # For device list: show name (type)
        name_width = max(len(f"{item[key]} ({item.get('type','')})") for item in valid_items)
        for i, item in enumerate(valid_items):
            type_str = item.get('type', '')
            name_with_type = f"{item[key]} ({type_str})"
            iceberg_print(f"  [{str(i).rjust(max_index_len)}] {name_with_type.ljust(name_width)}", "num")
    else:
        # For playlist list: show name (tracks)
        name_width = max(len(f"{item[key]} ({item.get('tracks',{}).get('total','?')})") for item in valid_items)
        for i, item in enumerate(valid_items):
            track_count = item.get('tracks', {}).get('total', '?')
            name_with_count = f"{item[key]} ({track_count})"
            iceberg_print(f"  [{str(i).rjust(max_index_len)}] {name_with_count.ljust(name_width)}", "num")
    while True:
        try:
            iceberg_print(prompt, "query", end=" ")
            idx = input()
        except KeyboardInterrupt:
            iceberg_print("\nExiting...", "info")
            sys.exit(0)
        if idx.isdigit() and 0 <= int(idx) < len(valid_items):
            return valid_items[int(idx)]
        iceberg_print("Please enter a valid number.", "info")

def get_playlist_tracks(sp, playlist_id):
    tracks = []
    results = sp.playlist_tracks(playlist_id)
    tracks.extend(results["items"])
    while results["next"]:
        results = sp.next(results)
        tracks.extend(results["items"])
    return [item["track"]["uri"] for item in tracks if item["track"]]

def playback_loop(sp, device_id, track_uris):
    clear_screen()
    print_header()
    sp.start_playback(device_id=device_id, uris=track_uris)
    sp.shuffle(True, device_id=device_id)
    # Wait for playback state to update (API delay workaround)
    for _ in range(6):
        playback = sp.current_playback()
        if playback and playback.get("is_playing"):
            break
        time.sleep(0.5)
    last_track_id = None
    try:
        while True:
            playback = sp.current_playback()
            if not playback or not playback.get("is_playing"):
                iceberg_print("Playback has stopped.", "info")
                break
            track = playback["item"]
            if track and track["id"] != last_track_id:
                iceberg_print("-" * 48, "fg")
                print_track_info(track)
                last_track_id = track["id"]
            time.sleep(POLLING_INTERVAL)
    except KeyboardInterrupt:
        iceberg_print("\nStopping playback...", "info")
        try:
            sp.pause_playback(device_id=device_id)
        except Exception:
            pass
        return  # Return to search

def main():
    client_id = os.environ.get("SPOTIPY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIPY_CLIENT_SECRET")
    redirect_uri = os.environ.get("SPOTIPY_REDIRECT_URI")
    if not all([client_id, client_secret, redirect_uri]):
        iceberg_print("Spotify authentication info is not set.", "info")
        sys.exit(1)
    scope = "user-read-playback-state user-modify-playback-state playlist-read-private playlist-read-collaborative"
    sp = Spotify(auth_manager=SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
        cache_path=os.path.expanduser("~/.cache/iceberg_spotify")
    ))

    while True:
        clear_screen()
        print_header()
        try:
            iceberg_print("Enter playlist name to search (or 0 for your playlists):", "query", end=" ")
            query = input().strip()
        except KeyboardInterrupt:
            iceberg_print("\nExiting...", "info")
            sys.exit(0)
        if not query:
            iceberg_print("Please enter a playlist name.", "info")
            continue

        if query == "0":
            # Get user's own playlists
            user_playlists = []
            results = sp.current_user_playlists(limit=50)
            user_playlists.extend(results['items'])
            while results['next']:
                results = sp.next(results)
                user_playlists.extend(results['items'])
            if not user_playlists:
                iceberg_print("You have no playlists.", "info")
                continue
            playlists = [p for p in user_playlists if 'tracks' in p and p['tracks'].get('total') is not None]
            playlists.sort(key=lambda p: p['tracks']['total'], reverse=True)
            iceberg_print("\nYour playlists:", "fg")
        else:
            results = sp.search(q=query, type="playlist", limit=30)
            playlists = results["playlists"]["items"]
            if not playlists:
                iceberg_print("No playlists found.", "info")
                continue
            playlists = [p for p in playlists if p is not None and 'tracks' in p and p['tracks'].get('total') is not None]
            playlists.sort(key=lambda p: p['tracks']['total'], reverse=True)
            iceberg_print("\nSearch results:", "fg")

        playlist = select_from_list(playlists, key="name", prompt="Select playlist number to play:")

        devices = sp.devices()["devices"]
        if not devices:
            iceberg_print("No Spotify devices found. Please open Spotify app.", "info")
            continue
        iceberg_print("\nPlayback devices:", "fg")
        device = select_from_list(devices, key="name", prompt="Select playback device number:", show_type=True)

        track_uris = get_playlist_tracks(sp, playlist["id"])
        iceberg_print(f"\nPlaying '{playlist['name']}' on {device['name']}...\n", "info")
        playback_loop(sp, device["id"], track_uris)

if __name__ == "__main__":
    main()

