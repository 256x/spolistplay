import os
import sys
import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import curses
import time
import logging

logging.basicConfig(level=logging.WARN, format="%(asctime)s - %(levelname)s - %(message)s")

CLIENT_ID = os.environ.get("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("SPOTIPY_REDIRECT_URI", "https://127.0.0.1/")

if not (CLIENT_ID and CLIENT_SECRET and REDIRECT_URI):
    print("Error: Spotify Client ID, Client Secret, or Redirect URI is not set.")
    sys.exit(1)

user_home = os.path.expanduser("~")
cache_dir = os.path.join(user_home, ".cache", "spotify")
os.makedirs(cache_dir, exist_ok=True)
CACHE_PATH = os.path.join(cache_dir, ".spotify_cache")

scope = "user-read-private user-read-playback-state,user-modify-playback-state,user-read-currently-playing,playlist-read-private"

try:
    auth_manager = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=scope,
        cache_path=CACHE_PATH,
        open_browser=True
    )
    sp = spotipy.Spotify(auth_manager=auth_manager, requests_timeout=20)
    user_profile = sp.me()
    logging.info("User profile loaded: " + json.dumps(user_profile))
    print("Spotify authentication successful.")
except Exception as e:
    logging.error(f"Authentication failed: {e}")
    print(f"Error: Spotify authentication failed: {e}")
    sys.exit(1)

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")
    print("\033[2J\033[H", end="", flush=True)
    print("- Spotify Playlist Player\n")

def getch():
    try:
        import termios, tty
    except ImportError:
        import msvcrt
        return msvcrt.getch().decode("utf-8")
    else:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

def get_search_query():
    clear_screen()
    prompt = "search: "
    print(prompt, end="", flush=True)
    query = ""
    while True:
        ch = getch()
        if ord(ch) == 27:
            print("\nESC pressed. Exiting.")
            sys.exit(0)
        elif ch in ("\r", "\n"):
            break
        else:
            query += ch
            print(ch, end="", flush=True)
    print()
    return query

def search_playlists(query, limit=30):
    try:
        if query == "0":
            playlists = sp.current_user_playlists(limit=limit)["items"]
            logging.info(f"Retrieved user's playlists. Count: {len(playlists)}")
            return playlists
        else:
            result = sp.search(q=query, type="playlist", limit=limit)
            playlists = result["playlists"]["items"] if "playlists" in result else []
            logging.info(f"Searched for playlists with query '{query}'. Count: {len(playlists)}")
            return playlists
    except Exception as e:
        logging.error(f"Error searching playlists: {e}", exc_info=True)
        print(f"Error searching playlists: {e}")
        return []

def select_playlist(playlists):
    clear_screen()
    if not playlists:
        print("No playlists found.")
        input("Press Enter to return to search.")
        return None
    valid_playlists = [pl for pl in playlists if pl is not None and pl.get("tracks")]
    if not valid_playlists:
        print("No valid playlists found.")
        input("Press Enter to return to search.")
        return None
    sorted_playlists = sorted(valid_playlists, key=lambda p: p["tracks"]["total"], reverse=True)
    print("Playlists:")
    for idx, pl in enumerate(sorted_playlists):
        print(f"{idx+1}. {pl['name']} ({pl['tracks']['total']} tracks) - {pl['owner']['display_name']}")
    selected_input = input("\nNo.: ")
    try:
        selected = int(selected_input) - 1
        if 0 <= selected < len(sorted_playlists):
            return sorted_playlists[selected]
        else:
            print("Invalid selection.")
            input("Press Enter to return to search.")
            return None
    except ValueError:
        print("Invalid input. Please enter a number.")
        input("Press Enter to return to search.")
        return None

def get_all_playlist_tracks(playlist_id):
    tracks = []
    offset = 0
    limit = 100
    retry_limit = 3
    while True:
        attempt = 0
        while attempt < retry_limit:
            try:
                results = sp.playlist_items(
                    playlist_id,
                    offset=offset,
                    limit=limit,
                    fields="items(track(id,name,artists,album(id,name,release_date)))",
                )
                break
            except Exception as e:
                attempt += 1
                logging.warning(f"Attempt {attempt} of {retry_limit}: Error retrieving tracks: {e}")
                if attempt == retry_limit:
                    logging.error("Max retry attempts reached for retrieving tracks.")
                    return tracks
                time.sleep(2)
        items = results.get("items", [])
        if not items:
            break
        for item in items:
            track = item.get("track")
            if track:
                tracks.append(track)
        if len(items) < limit:
            break
        offset += limit
    logging.info(f"Retrieved {len(tracks)} tracks from playlist {playlist_id}.")
    return tracks

def select_device():
    clear_screen()
    try:
        devices = sp.devices()["devices"]
        if not devices:
            print("No spotify devices found.")
            input("Press Enter to return to search.")
            return None
        print("Devices:")
        for idx, device in enumerate(devices):
            active_str = "[Active]" if device["is_active"] else ""
            print(f"{idx+1}. {device['name']} ({device['type']}) {active_str}")
        selected_input = input("\nNo.: ")
        try:
            selected = int(selected_input) - 1
        except ValueError:
            print("Invalid input. Please enter a number.")
            input("Press Enter to return to search.")
            return None
        if 0 <= selected < len(devices):
            return devices[selected]["id"]
        else:
            print("Invalid selection.")
            input("Press Enter to return to search.")
            return None
    except Exception as e:
        logging.error(f"Error selecting device: {e}", exc_info=True)
        print(f"Error getting devices: {e}")
        input("Press Enter to return to search.")
        return None

def chunk_tracks(tracks, chunk_size=100):
    return [tracks[i: i + chunk_size] for i in range(0, len(tracks), chunk_size)]

def play_track_chunk(chunk, device_id):
    track_uris = [f"spotify:track:{track['id']}" for track in chunk if track.get("id")]
    if not track_uris:
        print("No valid track URIs found in chunk.")
        return False
    try:
        sp.start_playback(device_id=device_id, uris=track_uris)
        logging.info("Started playback for a chunk.")
        return True
    except Exception as e:
        logging.error(f"Error starting playback: {e}", exc_info=True)
        print(f"Error starting playback: {e}")
        print("Note: Playback control requires a Spotify Premium account.")
        return False

def truncate_text(text, max_length):
    if max_length < 3:
         return text[:max_length]
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."

def init_iceberg_colors():
    if curses.COLORS >= 16:
        curses.init_pair(1, 223, -1)
        curses.init_pair(2, 110, -1)
        curses.init_pair(3, 109, -1)
        curses.init_pair(4, 146, -1)
        curses.init_pair(5, 216, -1)
        curses.init_pair(6, 167, -1)
        curses.init_pair(7, 150, -1)
    else:
        curses.init_pair(1, curses.COLOR_WHITE, -1)
        curses.init_pair(2, curses.COLOR_CYAN, -1)
        curses.init_pair(3, curses.COLOR_BLUE, -1)
        curses.init_pair(4, curses.COLOR_MAGENTA, -1)
        curses.init_pair(5, curses.COLOR_YELLOW, -1)
        curses.init_pair(6, curses.COLOR_RED, -1)
        curses.init_pair(7, curses.COLOR_GREEN, -1)

def playback_curses(stdscr, sp, playlist_info, tracks, device_id):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(100)

    curses.start_color()
    curses.use_default_colors()
    init_iceberg_colors()

    max_y, max_x = stdscr.getmaxyx()
    if max_y < 10 or max_x < 40:
        curses.endwin()
        print(f"Error: Terminal too small. Needs at least 10x40. Current size: {max_y}x{max_x}")
        return

    padding = 1
    usable_y = max_y - (padding * 2)
    usable_x = max_x - (padding * 2)

    header_win = curses.newwin(1, usable_x, padding, padding)
    body_win = curses.newwin(usable_y - 3, usable_x, padding + 2, padding)
    command_win = curses.newwin(1, usable_x, max_y - padding - 1, padding)
    
    stdscr.bkgd(' ', curses.color_pair(1))

    track_chunks = chunk_tracks(tracks, chunk_size=100)
    current_chunk_index = 0
    if not track_chunks:
        stdscr.addstr(padding, padding, "No tracks to play. Press any key to return.", curses.color_pair(6))
        stdscr.refresh()
        stdscr.getch()
        return

    if not play_track_chunk(track_chunks[current_chunk_index], device_id):
        stdscr.addstr(max_y - padding - 1, padding, "Playback failed. Press any key to return.", curses.color_pair(6))
        stdscr.refresh()
        stdscr.getch()
        return

    shuffle_state = False

    try:
        current_playback_state = sp.current_playback()
        if current_playback_state is not None and "shuffle_state" in current_playback_state:
            shuffle_state = current_playback_state["shuffle_state"]
            logging.info(f"Initial shuffle state from API: {shuffle_state}")
        else:
            sp.shuffle(state=True, device_id=device_id)
            shuffle_state = True
            logging.info("Attempted to set initial shuffle state ON.")

    except Exception as e:
        logging.warning(f"Could not get or set initial shuffle state: {e}")
        shuffle_state = False

    last_poll_time = time.time()
    POLLING_INTERVAL = 2.0
    running = True

    cached_track_info = None
    cached_shuffle_state = shuffle_state
    cached_max_x = max_x
    cached_max_y = max_y

    needs_redraw = True

    while running:
        current_max_y, current_max_x = stdscr.getmaxyx()

        if current_max_y < 10 or current_max_x < 40:
            curses.endwin()
            print(f"Error: Terminal too small after resize. Needs at least 10x40. Current size: {current_max_y}x{current_max_x}")
            sys.exit(1)

        if current_max_y != cached_max_y or current_max_x != cached_max_x:
            cached_max_y, cached_max_x = current_max_y, current_max_x
            try:
                del header_win
                del body_win
                del command_win
            except NameError:
                pass

            usable_y = cached_max_y - (padding * 2)
            usable_x = cached_max_x - (padding * 2)

            header_win = curses.newwin(1, usable_x, padding, padding)
            body_win = curses.newwin(usable_y - 3, usable_x, padding + 2, padding)
            command_win = curses.newwin(1, usable_x, cached_max_y - padding - 1, padding)

            stdscr.touchwin()
            needs_redraw = True

        current_time = time.time()
        poll_needed = (current_time - last_poll_time >= POLLING_INTERVAL)

        current_playback_state = None
        if poll_needed:
            try:
                current_playback_state = sp.current_playback()
                last_poll_time = current_time

                new_shuffle_state = cached_shuffle_state
                if current_playback_state is not None and "shuffle_state" in current_playback_state:
                    new_shuffle_state = current_playback_state["shuffle_state"]

                new_track_info = current_playback_state.get("item") if current_playback_state else None

                if new_track_info != cached_track_info or new_shuffle_state != cached_shuffle_state or current_playback_state is None:
                    needs_redraw = True
                    cached_track_info = new_track_info
                    cached_shuffle_state = new_shuffle_state

            except Exception as e:
                logging.error(f"Error fetching playback state: {e}", exc_info=True)
                pass

        try:
            key = stdscr.getch()
        except Exception:
            key = -1

        key_handled = False

        if key != -1:
            if key in (ord("x"), ord("X")):
                try:
                    sp.pause_playback(device_id=device_id)
                    logging.info("Playback paused due to X key exit")
                except Exception as e:
                    logging.warning(f"Could not pause playback on X key exit: {e}")
                curses.endwin()
                sys.exit(0)
            elif key == 27:
                running = False

            elif key in (ord("p"), ord("P")):
                try:
                    current_status = sp.current_playback()
                    if current_status is not None and current_status.get("is_playing"):
                        sp.pause_playback(device_id=device_id)
                        logging.info("Paused playback.")
                    else:
                        sp.start_playback(device_id=device_id)
                        logging.info("Started/resumed playback.")

                    key_handled = True
                    last_poll_time = 0
                    needs_redraw = True
                    if current_status is not None:
                        current_playback_state = {
                            "is_playing": not current_status.get("is_playing", False)
                        }

                except Exception as e:
                    logging.error(f"Error toggling playback: {e}", exc_info=True)
                    pass

            elif key in (ord(">"), ord(".")):
                try:
                    sp.next_track(device_id=device_id)
                    logging.info("Skipped to next track.")
                    key_handled = True
                    cached_track_info = None
                    last_poll_time = 0
                except Exception as e:
                    logging.error(f"Error skipping to next track: {e}", exc_info=True)
                    pass

            elif key in (ord("<"), ord(",")):
                try:
                    sp.previous_track(device_id=device_id)
                    logging.info("Skipped to previous track.")
                    key_handled = True
                    cached_track_info = None
                    last_poll_time = 0
                except Exception as e:
                    logging.error(f"Error returning to previous track: {e}", exc_info=True)
                    pass
            elif key in (ord("s"), ord("S")):
                try:
                    current_spotify_state = sp.current_playback()
                    current_shuffle = cached_shuffle_state

                    new_shuffle_state = not current_shuffle if current_shuffle is not None else True

                    sp.shuffle(state=new_shuffle_state, device_id=device_id)
                    logging.info(f"Shuffle set to {new_shuffle_state}.")
                    key_handled = True
                    needs_redraw = True
                    last_poll_time = 0

                except Exception as e:
                    logging.error(f"Error toggling shuffle: {e}", exc_info=True)
                    pass

        if key_handled:
            needs_redraw = True

        if needs_redraw:
            header_win.clear()
            body_win.clear()
            command_win.clear()

            header = "- Spotify Playlist Player"
            header_win.addstr(0, 0, header, curses.color_pair(5) | curses.A_BOLD)
            header_win.noutrefresh()

            if playlist_info:
                plist_line = f"{playlist_info['name']} by {playlist_info['owner']['display_name']}"
                body_win.addstr(0, 0, "Playlist: ", curses.color_pair(3))
                body_win.addstr(truncate_text(plist_line, usable_x - 10), curses.color_pair(2))

            if cached_track_info:
                item = cached_track_info
                track_name = item.get("name", "Unknown")
                artists = ", ".join([a["name"] for a in item.get("artists", [])])
                album = item.get("album", {}).get("name", "Unknown Album")
                release_date = item.get("album", {}).get("release_date", "----")
                album_line = f"{album} ({release_date[:4] if release_date else '----'})"

                labels = ["Track: ", "Artist: ", "Album: "]
                max_label_len = max(len(label) for label in labels)

                display_lines = [
                    (labels[0], track_name, 2, 4),
                    (labels[1], artists, 3, 4),
                    (labels[2], album_line, 4, 1),
                ]

                play_status = "▶ Playing" if current_playback_state and current_playback_state.get("is_playing") else "⏸ Paused"
                status_color = 7 if current_playback_state and current_playback_state.get("is_playing") else 6

                body_win.addstr(7, 0, play_status, curses.color_pair(status_color))

                shuffle_text = "☯ Shuffle:On" if cached_shuffle_state else "➡ Shuffle:Off"
                shuffle_color = 7 if cached_shuffle_state else 3
                body_win.addstr(7, 12, shuffle_text, curses.color_pair(shuffle_color))


                for label, content, row, color in display_lines:
                    padding = " " * (max_label_len - len(label))
                    content_max_width = usable_x - (max_label_len + 1)
                    body_win.addstr(row, 0, label, curses.color_pair(3))
                    body_win.addstr(row, max_label_len, truncate_text(content, content_max_width), curses.color_pair(color))

            else:
                body_win.addstr(3, 0, "No playback information available.", curses.color_pair(6))
                body_win.addstr(4, 0, "Check if Spotify is running and a device is selected.", curses.color_pair(3))

            body_win.noutrefresh()

            commands = [
                ("P", "⏯"),
                ("<", "⏮"),
                (">", "⏯"),
                ("S", "☯"),
                ("ESC", "↩"),
                ("X", "❌")
            ]
            
            cmd_str = "  ".join([f"{key}:{action}" for key, action in commands])
            try:
                command_win.addstr(0, 0, truncate_text(cmd_str, usable_x - 1), curses.color_pair(3))
            except curses.error:
                command_win.addstr(0, 0, truncate_text(cmd_str, usable_x - 2), curses.color_pair(3))
            command_win.noutrefresh()

            curses.doupdate()

            needs_redraw = False

    try:
        sp.pause_playback(device_id=device_id)
        logging.info("Playback paused on exit")
    except Exception as e:
        logging.warning(f"Could not pause playback on exit: {e}")


def process_playlist(playlist):
    clear_screen()
    print(f"Selected Playlist: {playlist['name']} by {playlist['owner']['display_name']}")
    print("Fetching tracks...")
    tracks = get_all_playlist_tracks(playlist["id"])
    if not tracks:
        print("No tracks found in the selected playlist.")
        input("Press Enter to return to search...")
        return
    print(f"Found {len(tracks)} tracks in the playlist.")
    device_id = select_device()
    if not device_id:
        print("No device selected. Returning to search menu.")
        input("Press Enter to continue...")
        return
    try:
        curses.wrapper(playback_curses, sp, playlist, tracks, device_id)
    except Exception as e:
        logging.error(f"Error during playback (curses mode): {e}", exc_info=True)
        print(f"An error occurred during playback: {e}")
        input("Press Enter to return to search...")

def main():
    try:
        clear_screen()
        print("\033[1;36m╔════════════════════════════════════════╗")
        print("║  Welcome to Spotify Playlist Player   ║")
        print("╚════════════════════════════════════════╝\033[0m")
        print("\nEnter a search term to find playlists, or '0' to see your playlists.\n")
        
        while True:
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
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Exiting program.")
        try:
            sp.pause_playback()
            logging.info("Playback paused on Ctrl+C exit")
        except Exception as e:
            logging.warning(f"Could not pause playback on Ctrl+C exit: {e}")
    except Exception as e:
        logging.error(f"Unhandled error in main loop: {e}", exc_info=True)
        print(f"\nAn unexpected error occurred: {e}")
        input("Press Enter to return to search...")


if __name__ == "__main__":
    main()

