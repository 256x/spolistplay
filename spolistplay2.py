import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import logging
import time

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Get client ID, client secret, and redirect URI from environment variables
CLIENT_ID = os.environ.get("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("SPOTIPY_REDIRECT_URI", "https://127.0.0.1/")  # Set default value

# Cache path configuration
user_home = os.path.expanduser("~")
cache_dir = os.path.join(user_home, ".cache", "spotify")
os.makedirs(cache_dir, exist_ok=True)
CACHE_PATH = os.path.join(cache_dir, ".spotify_cache")

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    logging.error("Client ID, client secret, or redirect URI not set.")
    exit()

# OAuth authentication setup
scope = "user-read-playback-state,user-modify-playback-state,user-read-currently-playing"
auth_manager = SpotifyOAuth(client_id=CLIENT_ID,
                            client_secret=CLIENT_SECRET,
                            redirect_uri=REDIRECT_URI,
                            scope=scope,
                            cache_path=CACHE_PATH,
                            open_browser=True)
sp = spotipy.Spotify(auth_manager=auth_manager)

# Global variables
current_playback_loop_active = False
current_device_id = None
current_track_chunks = []
current_chunk_index = 0

def search_playlists(query, limit=30):
    try:
        result = sp.search(q=query, type='playlist', limit=limit)
        playlists = result['playlists']['items'] if 'playlists' in result else []
        playlists = [playlist for playlist in playlists if playlist is not None]
        logging.info(f"Searched for playlists with query '{query}'. Results: {len(playlists)}")
        return playlists
    except Exception as e:
        logging.error(f"Error while searching for playlists: {e}")
        return []

def get_search_query():
    query = input("Enter search query: ")
    logging.info(f"User entered search query: {query}")
    return query

def get_all_playlist_tracks(playlist_id):
    tracks = []
    offset = 0
    limit = 100

    try:
        while True:
            results = sp.playlist_items(
                playlist_id,
                offset=offset,
                limit=limit,
                fields='items(track(id,name,artists,album(id,name,release_date)))'
            )

            items = results.get('items', [])
            if not items:
                break

            for item in items:
                track = item.get('track')
                if track:
                    tracks.append(track)

            if len(items) < limit:
                break

            offset += limit

        logging.info(f"Retrieved {len(tracks)} tracks from playlist '{playlist_id}'.")
        return tracks
    except Exception as e:
        logging.error(f"Error while retrieving playlist tracks: {e}")
        return []

def process_playlist(playlist):
    print(f"\nSelected playlist: {playlist['name']} by {playlist['owner']['display_name']}")
    print("Fetching tracks...")

    try:
        tracks = get_all_playlist_tracks(playlist['id'])

        if not tracks:
            print("No tracks found in this playlist.")
            return

        print(f"Found {len(tracks)} tracks in the playlist.\n")
        start_playback_loop(tracks)

    except Exception as e:
        print(f"Error processing playlist: {e}")
        logging.error(f"Error while processing playlist: {e}")

def select_device():
    global current_device_id
    try:
        devices = sp.devices()['devices']
        if not devices:
            print("No active Spotify devices found.")
            return None

        for idx, device in enumerate(devices):
            print(f"{idx + 1}. {device['name']} ({device['type']})")

        selected = int(input("\nEnter the number of the device you want to use: ")) - 1
        if selected < 0 or selected >= len(devices):
            print("Invalid selection.")
            return None

        current_device_id = devices[selected]['id']
        return current_device_id
    except Exception as e:
        print(f"Error getting devices: {e}")
        return None

def chunk_tracks(tracks, chunk_size=100):
    return [tracks[i:i + chunk_size] for i in range(0, len(tracks), chunk_size)]

def play_track_chunk(chunk, device_id):
    track_ids = [track['id'] for track in chunk if track.get('id')]
    
    if not track_ids:
        print("No valid track IDs found.")
        return False
    
    try:
        sp.start_playback(device_id=device_id, uris=['spotify:track:' + tid for tid in track_ids])
        print(f"Playing chunk with {len(track_ids)} tracks...")
        return True
    except Exception as e:
        print(f"Error playing tracks: {e}")
        return False

def display_current_track():
    try:
        current_track = sp.current_playback()
        if current_track and current_track['item']:
            item = current_track['item']
            name = item.get('name', 'Unknown')
            artists = ', '.join([a['name'] for a in item.get('artists', [])])
            album = item.get('album', {}).get('name', 'Unknown Album')
            release_date = item.get('album', {}).get('release_date', '')
            year = release_date[:4] if release_date else 'Unknown Year'

            # Show the album name and release year
            print(f"\n♪  {name} / {artists}\n󰀥  {album} ({year})\n")
        else:
            print("Nothing is currently playing.")
    except Exception as e:
        print(f"Error getting current track: {e}")

def start_playback_loop(tracks):
    global current_playback_loop_active, current_device_id, current_track_chunks, current_chunk_index

    if current_playback_loop_active:
        print("Another playlist is already playing.")
        return

    device_id = select_device()
    if not device_id:
        return

    current_track_chunks = chunk_tracks(tracks, chunk_size=100)
    current_chunk_index = 0

    if not current_track_chunks:
        print("No valid tracks found.")
        return

    print(f"\nPlaylist divided into {len(current_track_chunks)} chunks.")

    try:
        shuffle_state = False
        sp.shuffle(state=shuffle_state, device_id=device_id)
        current_playback_loop_active = True

        if not play_track_chunk(current_track_chunks[current_chunk_index], device_id):
            current_playback_loop_active = False
            return

        time.sleep(2)

        while current_playback_loop_active:
            display_current_track()

            current_playback = sp.current_playback()
            if current_playback and current_playback.get('progress_ms') is not None:
                if current_playback.get('progress_ms', 0) > 0 and not current_playback.get('is_playing', False):
                    if current_chunk_index < len(current_track_chunks) - 1:
                        current_chunk_index += 1
                        print(f"\nLoading next chunk ({current_chunk_index + 1}/{len(current_track_chunks)})...")
                        if not play_track_chunk(current_track_chunks[current_chunk_index], device_id):
                            current_playback_loop_active = False
                            break
                        time.sleep(2)
                    else:
                        print("End of playlist reached.")

            # Commands in a single line
            print(f"- P,<,>,N,R,X [{'Z' if shuffle_state else '-'}] : ", end="")
            choice = input()

            if choice == 'p':
                state = sp.current_playback()
                if state and state['is_playing']:
                    sp.pause_playback(device_id=device_id)
                    print("Paused.")
                else:
                    sp.start_playback(device_id=device_id)
                    print("Resumed.")
            elif choice == '<':
                sp.previous_track(device_id=device_id)
            elif choice == '>':
                sp.next_track(device_id=device_id)
            elif choice == 'n':
                if current_chunk_index < len(current_track_chunks) - 1:
                    current_chunk_index += 1
                    if not play_track_chunk(current_track_chunks[current_chunk_index], device_id):
                        print("Failed to load next chunk.")
                else:
                    print("Already at the last chunk.")
            elif choice == 'z':
                shuffle_state = not shuffle_state
                sp.shuffle(state=shuffle_state, device_id=device_id)
                print(f"Shuffle is now {'On' if shuffle_state else 'Off'}")
            elif choice == 'r':
                sp.pause_playback(device_id=device_id)
                current_playback_loop_active = False
                raise KeyboardInterrupt
            elif choice == 'x':
                sp.pause_playback(device_id=device_id)
                current_playback_loop_active = False
                print("\nExiting.")
                exit()
            else:
                print("Invalid choice.")

            time.sleep(2)

    except KeyboardInterrupt:
        print("\nExiting playback loop.")
    except Exception as e:
        print(f"Error in playback loop: {e}")
    finally:
        current_playback_loop_active = False
        current_track_chunks = []
        current_chunk_index = 0

def display_track_info(track, index, total):
    if not track:
        return

    name = track.get('name', 'Unknown')
    artists = [artist['name'] for artist in track.get('artists', [])]
    album = track.get('album', {}).get('name', 'Unknown Album')
    release_date = track.get('album', {}).get('release_date', '')
    year = release_date[:4] if release_date else 'Unknown Year'

    artist_name = ', '.join(artists) if artists else 'Unknown Artist'
    print(f"[{index}/{total}] {name} - {artist_name} | {album} ({year})")

def select_playlist(playlists):
    if not playlists:
        print("No playlists found.")
        return None

    sorted_playlists = sorted(playlists, key=lambda p: p['tracks']['total'], reverse=True)

    print("\nPlaylists:")
    for idx, pl in enumerate(sorted_playlists):
        print(f"{idx + 1}. {pl['name']} ({pl['tracks']['total']} tracks) - {pl['owner']['display_name']}")

    selected = int(input("\nSelect a playlist by number: ")) - 1
    if 0 <= selected < len(sorted_playlists):
        return sorted_playlists[selected]
    else:
        print("Invalid selection.")
        return None

def main():
    while True:
        try:
            query = get_search_query()
            playlists = search_playlists(query)
            selected = select_playlist(playlists)
            if selected:
                process_playlist(selected)
        except KeyboardInterrupt:
            print("\nGoodbye.")
            break

if __name__ == "__main__":
    main()

