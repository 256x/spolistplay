import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import logging
import time
import sys

logging.basicConfig(level=logging.WARN, format='%(asctime)s - %(levelname)s - %(message)s')

CLIENT_ID = os.environ.get("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("SPOTIPY_REDIRECT_URI", "https://127.0.0.1/")

user_home = os.path.expanduser("~")
cache_dir = os.path.join(user_home, ".cache", "spotify")
os.makedirs(cache_dir, exist_ok=True)
CACHE_PATH = os.path.join(cache_dir, ".spotify_cache")

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    logging.error("Client ID, client secret, or redirect URI not set.")
    print("Error: Spotify Client ID, Client Secret, or Redirect URI not set.")
    sys.exit(1)

scope = "user-read-playback-state,user-modify-playback-state,user-read-currently-playing,playlist-read-private"  # playlist-read-private を追加
auth_manager = SpotifyOAuth(client_id=CLIENT_ID,
                            client_secret=CLIENT_SECRET,
                            redirect_uri=REDIRECT_URI,
                            scope=scope,
                            cache_path=CACHE_PATH,
                            open_browser=True)

try:
    sp = spotipy.Spotify(auth_manager=auth_manager)
    sp.me()
    logging.info("Spotify authentication successful.")

except Exception as e:
    logging.error(f"Authentication failed: {e}")
    print(f"Error: Spotify authentication failed: {e}")
    print("Please check your environment variables or authentication process.")
    sys.exit(1)

current_device_id = None
current_track_chunks = []
current_chunk_index = 0
last_played_track_id = None

POLLING_INTERVAL = 2

def clear_screen():
    sys.stdout.write('\033c')
    sys.stdout.flush()
    print(f"\n- spotify playlist player\n")

def search_playlists(query, limit=30):
    try:
        if query == '0':
            # 自分のプレイリストを取得
            playlists = sp.current_user_playlists(limit=limit)['items']
            logging.info(f"Retrieved user's playlists. Results: {len(playlists)}")
            return playlists
        else:
            # 通常の検索
            result = sp.search(q=query, type='playlist', limit=limit)
            playlists = result['playlists']['items'] if 'playlists' in result else []
            playlists = [playlist for playlist in playlists if playlist is not None]
            logging.info(f"Searched for playlists with query '{query}'. Results: {len(playlists)}")
            return playlists
    except Exception as e:
        logging.error(f"Error while searching for playlists: {e}", exc_info=True)
        print(f"Error searching playlists: {e}")
        return []

def get_search_query():
    clear_screen()
    query = input("search: ")
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
        logging.error(f"Error while retrieving playlist tracks: {e}", exc_info=True)
        print(f"Error fetching tracks: {e}")
        return []

def process_playlist(playlist):
    clear_screen()
    print(f"Selected playlist: {playlist['name']} by {playlist['owner']['display_name']}")
    print("Fetching tracks...")

    try:
        tracks = get_all_playlist_tracks(playlist['id'])

        if not tracks:
            print("No tracks found in this playlist.")
            input("Press Enter to return to search menu...")
            return

        print(f"Found {len(tracks)} tracks in the playlist.")
        start_playback_loop(tracks, playlist_info=playlist)

    except Exception as e:
        logging.error(f"Error processing playlist: {e}", exc_info=True)
        print(f"Error processing playlist: {e}")
        input("Press Enter to return to search menu...")

def select_device():
    global current_device_id
    clear_screen()
    try:
        devices = sp.devices()['devices']
        if not devices:
            print("No active Spotify devices found.")
            input("Press Enter to return to search menu...")
            return None

        print("Active Spotify Devices:")
        for idx, device in enumerate(devices):
            print(f"{idx + 1}. {device['name']} ({device['type']}) {'[Active]' if device['is_active'] else ''}")

        selected_input = input("\ndevice: ")
        try:
            selected = int(selected_input) - 1
        except ValueError:
            print("Invalid input. Please enter a number.")
            input("Press Enter to return to search menu...")
            return None

        if selected < 0 or selected >= len(devices):
            print("Invalid selection.")
            input("Press Enter to return to search menu...")
            return None

        current_device_id = devices[selected]['id']
        print(f"\nSelected device: {devices[selected]['name']}")
        return current_device_id
    except Exception as e:
        logging.error(f"Error getting devices: {e}", exc_info=True)
        print(f"Error getting devices: {e}")
        input("Press Enter to return to search menu...")
        return None

def chunk_tracks(tracks, chunk_size=100):
    return [tracks[i:i + chunk_size] for i in range(0, len(tracks), chunk_size)]

def play_track_chunk(chunk, device_id):
    track_uris = [f'spotify:track:{track["id"]}' for track in chunk if track.get('id')]

    if not track_uris:
        print("No valid track URIs found in chunk.")
        return False

    try:
        sp.start_playback(device_id=device_id, uris=track_uris)
        first_track_name = chunk[0]['name'] if chunk else 'N/A'
        logging.info(f"Started playback for chunk {current_chunk_index+1} on device {device_id}. First track: {first_track_name}")
        return True
    except Exception as e:
        logging.error(f"Error calling start_playback: {e}", exc_info=True)
        print(f"Error starting playback: {e}")
        return False

def display_current_track(playback_state):
    global last_played_track_id

    current_track_id = playback_state.get('item', {}).get('id') if playback_state else None

    if current_track_id != last_played_track_id:
        pass
    elif last_played_track_id is None and current_track_id is not None:
        pass
    else:
        return

    if playback_state and playback_state.get('item'):
        item = playback_state['item']
        name = item.get('name', 'Unknown')
        artists = ', '.join([a['name'] for a in item.get('artists', [])])
        album = item.get('album', {}).get('name', 'Unknown Album')
        release_date = item.get('album', {}).get('release_date', '')
        year = release_date[:4] if release_date else 'Unknown Year'

        print(f"♪  {name} / {artists}", flush=True)
        print(f"󰀥  {album} ({year})\n", flush=True)

        last_played_track_id = current_track_id

def start_playback_loop(tracks, playlist_info=None):
    global current_device_id, current_track_chunks, current_chunk_index, last_played_track_id

    device_id = select_device()
    if not device_id:
        print("No device selected. Exiting playback process.", flush=True)
        return

    current_track_chunks = chunk_tracks(tracks, chunk_size=100)
    current_chunk_index = 0
    last_played_track_id = None

    if not current_track_chunks:
        print("No valid tracks found after chunking.", flush=True)
        return

    clear_screen()

    if playlist_info:
        print(f"- [ {playlist_info['name']} | {playlist_info['owner']['display_name']} ]\n")

    try:
        shuffle_state = True
        try:
            sp.shuffle(state=shuffle_state, device_id=device_id)
            logging.info("Shuffle enabled.")
        except Exception as e:
            logging.warning(f"Could not set initial shuffle state: {e}")
            print(f"Warning: Could not enable shuffle: {e}", flush=True)

        if not play_track_chunk(current_track_chunks[current_chunk_index], device_id):
            print("Failed to start playback for the first chunk.", flush=True)
            return

        time.sleep(3)

        last_polling_time = time.time()

        while True:
            try:
                current_time = time.time()

                if current_time - last_polling_time >= POLLING_INTERVAL:
                    playback_state = sp.current_playback()

                    display_current_track(playback_state)

                    if playback_state is None and last_played_track_id is not None:
                        print("\nPlayback ended.", flush=True)
                        break

                    last_polling_time = current_time

                sleep_duration = POLLING_INTERVAL - (time.time() - last_polling_time)
                if sleep_duration > 0:
                    time.sleep(sleep_duration)

            except Exception as e:
                logging.error(f"Error in playback loop polling/processing: {e}", exc_info=True)
                print(f"\n[Error] An error occurred: {e}", flush=True)
                if "token" in str(e).lower() or "device" in str(e).lower():
                    print("Stopping playback loop due to critical error.", flush=True)
                    break
                else:
                    print("Stopping playback loop due to unexpected error.", flush=True)
                    break

    except KeyboardInterrupt:
        print("\nCtrl+C detected. Stopping playback.", flush=True)

    finally:
        try:
            if current_device_id:
                sp.pause_playback(device_id=current_device_id)
        except Exception as e:
            logging.warning(f"Could not pause playback on exit: {e}")

        current_track_chunks = []
        current_chunk_index = 0
        last_played_track_id = None
        current_device_id = None

def select_playlist(playlists):
    clear_screen()
    if not playlists:
        print("No playlists found.")
        input("Press Enter to return to search menu...")
        return None

    sorted_playlists = sorted(playlists, key=lambda p: p['tracks']['total'], reverse=True)

    print("Playlists:")
    for idx, pl in enumerate(sorted_playlists):
        print(f"{idx + 1}. {pl['name']} ({pl['tracks']['total']} tracks) - {pl['owner']['display_name']}")

    selected_input = input("\nNo.: ")
    try:
        selected = int(selected_input) - 1
    except ValueError:
        print("Invalid input. Please enter a number.")
        input("Press Enter to return to search menu...")
        return None

    if 0 <= selected < len(sorted_playlists):
        return sorted_playlists[selected]
    else:
        print("Invalid selection.")
        input("Press Enter to return to search menu...")
        return None

def main():
    while True:
        try:
            query = get_search_query()
            if not query:
                print("Search query cannot be empty.")
                input("Press Enter to continue...")
                continue

            playlists = search_playlists(query)
            if not playlists:
                print(f"No playlists found for '{query}'.")
                input("Press Enter to continue...")
                continue

            selected = select_playlist(playlists)
            if selected:
                process_playlist(selected)
            else:
                print("No playlist selected.")

        except KeyboardInterrupt:
            print("\nCtrl+C detected. Exiting program.")
            break
        except SystemExit:
            print("Program exiting.")
            break
        except Exception as e:
            logging.error(f"Unhandled error in main loop: {e}", exc_info=True)
            print(f"\nAn unexpected error occurred: {e}")
            input("Press Enter to return to search loop...")

if __name__ == "__main__":
    main()

