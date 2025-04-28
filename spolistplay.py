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
    print("Please set the SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, and SPOTIPY_REDIRECT_URI environment variables.")
    sys.exit(1)

user_home = os.path.expanduser("~")
cache_dir = os.path.join(user_home, ".cache", "spotify")
os.makedirs(cache_dir, exist_ok=True)
CACHE_PATH = os.path.join(cache_dir, ".spotify_cache")

scope = "user-read-private user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-read-private"

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
    logging.error(f"Authentication failed: {e}", exc_info=True)
    print(f"Error: Spotify authentication failed. Please check your credentials, environment variables, and network connection.")
    print(f"Details: {e}")
    sys.exit(1)

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")
    print("\033[2J\033[H", end="", flush=True)
    print("- Spotify Playlist Player\n")

def getch():
    try:
        import termios, tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch
    except ImportError:
        import msvcrt
        try:
            return msvcrt.getch().decode("utf-8")
        except UnicodeDecodeError:
            return ''
    except Exception as e:
         logging.error(f"Error in getch(): {e}")
         return ''

def get_search_query():
    clear_screen()
    prompt = "search: "
    print(prompt, end="", flush=True)
    query = ""
    while True:
        try:
            ch = getch()
            if not ch: continue

            if ord(ch) == 27:
                print("\nESC pressed. Exiting.")
                sys.exit(0)
            elif ch in ("\r", "\n"):
                break
            elif ord(ch) in (8, 127):
                 if query:
                      query = query[:-1]
                      print("\b \b", end="", flush=True)
            elif ord(ch) == 3:
                 raise KeyboardInterrupt
            elif len(ch) == 1 and (32 <= ord(ch) < 127 or ord(ch) >= 128):
                 query += ch
                 print(ch, end="", flush=True)

        except KeyboardInterrupt:
             print("\nCtrl+C pressed. Exiting.")
             raise

        except Exception as e:
             logging.error(f"Error during search query input: {e}", exc_info=True)
             print(f"\nAn error occurred during input: {e}.")
             return query

    print()
    return query

def search_playlists(query, limit=30):
    try:
        if query == "0":
            print("Fetching your playlists...")
            playlists = []
            offset = 0
            while True:
                results = sp.current_user_playlists(limit=limit, offset=offset)
                items = results.get("items", [])
                if not items:
                    break
                playlists.extend(items)
                if len(items) < limit:
                    break
                offset += limit

            logging.info(f"Retrieved user's playlists. Count: {len(playlists)}")

        else:
            print(f"Searching for playlists matching '{query}'...")
            result = sp.search(q=query, type="playlist", limit=limit)
            playlists = result["playlists"]["items"] if "playlists" in result else []
            logging.info(f"Searched for playlists with query '{query}'. Count: {len(playlists)}")

        valid_playlists = [pl for pl in playlists if pl and pl.get("tracks") is not None and pl.get("tracks", {}).get("total") is not None]
        return valid_playlists

    except Exception as e:
        logging.error(f"Error searching playlists: {e}", exc_info=True)
        print(f"Error searching playlists: {e}")
        return []

def select_playlist(playlists):
    clear_screen()
    if not playlists:
        print("No playlists found.")
        return None

    valid_playlists = [pl for pl in playlists if pl.get("tracks") and pl.get("tracks", {}).get("total") is not None]

    if not valid_playlists:
        print("No valid playlists with track counts found.")
        return None

    sorted_playlists = sorted(valid_playlists, key=lambda p: p.get("tracks", {}).get("total", 0), reverse=True)

    print("Playlists:")
    display_limit = 30
    for idx, pl in enumerate(sorted_playlists[:display_limit]):
        track_count = pl.get("tracks", {}).get("total", "N/A")
        print(f"{idx+1}. {pl['name']} ({track_count} tracks) - {pl['owner']['display_name']}")

    if len(sorted_playlists) > display_limit:
         print(f"... {len(sorted_playlists) - display_limit} more playlists not shown.")


    selected_input = input("\nEnter playlist number to select: ")
    try:
        selected = int(selected_input) - 1
        if 0 <= selected < len(sorted_playlists):
            return sorted_playlists[selected]
        else:
            print("Invalid selection number.")
            return None
    except ValueError:
        print("Invalid input. Please enter a number.")
        return None

def get_all_playlist_tracks(playlist_id):
    tracks = []
    offset = 0
    limit = 100
    retry_limit = 3
    print("Fetching playlist tracks...")
    while True:
        attempt = 0
        results = None
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
                if attempt < retry_limit:
                    time.sleep(2)
                else:
                    logging.error("Max retry attempts reached for retrieving tracks. Stopping fetch.")
                    print(f"Failed to fetch tracks after multiple retries. Error: {e}")
                    return tracks

        if results is None:
             break

        items = results.get("items", [])
        if not items:
            break

        for item in items:
            track = item.get("track")
            if track and track.get("id"):
                tracks.append(track)
            else:
                logging.debug(f"Skipping invalid track item: {item}")

        if len(items) < limit:
            break

        offset += limit
        sys.stdout.flush()

    print(f"Retrieved {len(tracks)} valid tracks.")
    logging.info(f"Retrieved {len(tracks)} valid tracks from playlist {playlist_id}.")
    return tracks

def select_device():
    clear_screen()
    try:
        devices = sp.devices()["devices"]
        if not devices:
            print("No spotify devices found.")
            print("Please make sure the Spotify application is running and logged in.")
            return None

        print("Available Devices:")
        for idx, device in enumerate(devices):
            active_str = "[Active]" if device["is_active"] else ""
            print(f"{idx+1}. {device['name']} ({device['type']}) {active_str}")

        selected_input = input("\nEnter device number to play on: ")
        try:
            selected = int(selected_input) - 1
        except ValueError:
            print("Invalid input. Please enter a number.")
            return None

        if 0 <= selected < len(devices):
            return devices[selected]["id"]
        else:
            print("Invalid selection.")
            return None
    except Exception as e:
        logging.error(f"Error selecting device: {e}", exc_info=True)
        print(f"Error getting devices: {e}")
        print("Please check your Spotify Premium account status and network.")
        return None

def chunk_tracks(tracks, chunk_size=100):
    track_uris = [f"spotify:track:{track['id']}" for track in tracks if track and track.get("id")]
    return [track_uris[i: i + chunk_size] for i in range(0, len(track_uris), chunk_size)]

def play_track_chunk(chunk_uris, device_id):
    if not chunk_uris:
        return False
    try:
        sp.start_playback(device_id=device_id, uris=chunk_uris)
        logging.info(f"Started playback for a chunk of {len(chunk_uris)} tracks using uris.")
        return True
    except spotipy.exceptions.SpotifyException as e:
        logging.error(f"SpotifyException starting playback: {e}", exc_info=True)
        return False
    except Exception as e:
        logging.error(f"Error starting playback: {e}", exc_info=True)
        return False

def truncate_text(text, max_length):
    if not isinstance(text, str):
        text = str(text)
    if max_length is None or max_length < 0:
         return text
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
    min_y, min_x = 10, 40
    if max_y < min_y or max_x < min_x:
        curses.endwin()
        print(f"Error: Terminal too small. Needs at least {min_y}x{min_x}. Current size: {max_y}x{max_x}")
        return

    padding = 1
    header_h = 1
    command_h = 1

    min_body_h_required = 6

    usable_y = max_y - (padding * 2)
    usable_x = max_x - (padding * 2)
    body_h = usable_y - header_h - command_h - 1

    if body_h < min_body_h_required:
         curses.endwin()
         print(f"Error: Terminal height too small for initial layout. Needs at least {min_body_h_required + header_h + command_h + padding*2 + 1} lines total. Current size: {max_y}x{max_x}")
         sys.exit(1)

    header_win = curses.newwin(header_h, usable_x, padding, padding)
    body_win = curses.newwin(body_h, usable_x, padding + header_h + 1, padding)
    command_win = curses.newwin(command_h, usable_x, max_y - padding - command_h, padding)

    stdscr.bkgd(' ', curses.color_pair(1))

    track_uri_chunks = chunk_tracks(tracks, chunk_size=100)

    if not track_uri_chunks:
        body_win.addstr(0, 0, "No valid tracks to play.", curses.color_pair(6))
        body_win.noutrefresh()
        stdscr.addstr(max_y - padding -1, padding, "Press any key to return.", curses.color_pair(3))
        stdscr.noutrefresh()
        curses.doupdate()
        stdscr.getch()
        return

    playlist_uri = playlist_info.get('uri')

    try:
        if track_uri_chunks and track_uri_chunks[0]:
             first_track_uri = track_uri_chunks[0][0]
             if playlist_uri and first_track_uri:
                  sp.start_playback(
                     device_id=device_id,
                     context_uri=playlist_uri,
                     offset={'uri': first_track_uri},
                  )
                  logging.info(f"Started playback for playlist {playlist_uri} from track {first_track_uri}.")
             else:
                  sp.start_playback(device_id=device_id, uris=track_uri_chunks[0])
                  logging.info(f"Started playback for a chunk of {len(track_uri_chunks[0])} tracks using uris.")
        else:
            raise ValueError("No valid track URIs available to start playback.")

    except spotipy.exceptions.SpotifyException as e:
        logging.error(f"SpotifyException starting playback: {e}", exc_info=True)
        body_win.addstr(0, 0, "Failed to start playback (Spotify API Error).", curses.color_pair(6))
        body_win.addstr(1, 0, truncate_text(str(e), usable_x -1), curses.color_pair(6))
        body_win.addstr(2, 0, "Check device status or Premium account.", curses.color_pair(3))
        body_win.noutrefresh()
        stdscr.addstr(max_y - padding -1, padding, "Press any key to return.", curses.color_pair(3))
        stdscr.noutrefresh()
        curses.doupdate()
        stdscr.getch()
        return
    except Exception as e:
        logging.error(f"Error starting playback: {e}", exc_info=True)
        body_win.addstr(0, 0, "Failed to start playback (Unexpected Error).", curses.color_pair(6))
        body_win.addstr(1, 0, truncate_text(str(e), usable_x -1), curses.color_pair(6))
        body_win.addstr(2, 0, "Note: Playback control requires a Spotify Premium account.", curses.color_pair(3))
        body_win.noutrefresh()
        stdscr.addstr(max_y - padding -1, padding, "Press any key to return.", curses.color_pair(3))
        stdscr.noutrefresh()
        curses.doupdate()
        stdscr.getch()
        return


    shuffle_state = False
    try:
        current_playback_state_init = sp.current_playback(market='from_token')
        if current_playback_state_init is not None and "shuffle_state" in current_playback_state_init:
            shuffle_state = current_playback_state_init["shuffle_state"]
            logging.info(f"Initial shuffle state from API: {shuffle_state}")

    except Exception as e:
        logging.warning(f"Could not get initial shuffle state: {e}")
        shuffle_state = False

    cached_track_info = None
    cached_shuffle_state = shuffle_state
    cached_is_playing = False
    cached_max_x = max_x
    cached_max_y = max_y
    last_api_error = None

    needs_redraw = True
    last_poll_time = time.time()
    POLLING_INTERVAL = 2.0

    running = True
    while running:
        current_max_y, current_max_x = stdscr.getmaxyx()
        size_changed = (current_max_y != cached_max_y or current_max_x != cached_max_x)

        if size_changed:
            cached_max_y, cached_max_x = current_max_y, current_max_x
            if cached_max_y < min_y or cached_max_x < min_x:
                curses.endwin()
                print(f"Error: Terminal resized too small. Needs at least {min_y}x{min_x}. Current size: {cached_max_y}x{cached_max_x}")
                sys.exit(1)

            try:
                del header_win
                del body_win
                del command_win
            except NameError:
                pass

            usable_y = cached_max_y - (padding * 2)
            usable_x = cached_max_x - (padding * 2)
            body_h = usable_y - header_h - command_h - 1

            if body_h < min_body_h_required:
                 curses.endwin()
                 print(f"Error: Terminal height too small after resize. Needs at least {min_body_h_required + header_h + command_h + padding*2 + 1} lines total. Current size: {cached_max_y}x{cached_max_x}")
                 sys.exit(1)

            header_win = curses.newwin(header_h, usable_x, padding, padding)
            body_win = curses.newwin(body_h, usable_x, padding + header_h + 1, padding)
            command_win = curses.newwin(command_h, usable_x, cached_max_y - padding - command_h, padding)

            stdscr.clear()
            stdscr.bkgd(' ', curses.color_pair(1))
            stdscr.touchwin()

            needs_redraw = True

        current_time = time.time()
        poll_needed = (current_time - last_poll_time >= POLLING_INTERVAL) or needs_redraw

        current_playback_state = None
        if poll_needed:
            try:
                current_playback_state = sp.current_playback(market='from_token')
                last_poll_time = current_time
                if current_playback_state is not None:
                     last_api_error = None

                new_track_info = current_playback_state.get("item") if current_playback_state else None
                new_shuffle_state = current_playback_state.get("shuffle_state", False) if current_playback_state else cached_shuffle_state
                new_is_playing = current_playback_state.get("is_playing", False) if current_playback_state else cached_is_playing

                if new_track_info != cached_track_info or new_shuffle_state != cached_shuffle_state or new_is_playing != cached_is_playing or (last_api_error is not None):
                    needs_redraw = True
                    cached_track_info = new_track_info
                    cached_shuffle_state = new_shuffle_state
                    cached_is_playing = new_is_playing


            except Exception as e:
                logging.error(f"Error fetching playback state: {e}", exc_info=True)
                last_api_error = f"API Error: {truncate_text(str(e), usable_x - 15)}"
                needs_redraw = True

        key = stdscr.getch()

        if key != -1:
            key_handled = True

            if key in (ord("q"), ord("Q"), 27):
                running = False

            elif key in (ord("p"), ord("P")):
                try:
                    current_status_check = sp.current_playback(market='from_token')
                    if current_status_check is not None and current_status_check.get("is_playing"):
                        sp.pause_playback(device_id=device_id)
                        logging.info("Playback paused.")
                    else:
                        sp.start_playback(device_id=device_id)
                        logging.info("Started/resumed playback.")

                    last_poll_time = 0
                    needs_redraw = True
                    last_api_error = None

                except Exception as e:
                    logging.error(f"Error toggling playback: {e}", exc_info=True)
                    last_api_error = f"Cmd Error: {truncate_text(str(e), usable_x - 15)}"
                    needs_redraw = True

            elif key in (ord(">"), ord(".")):
                try:
                    sp.next_track(device_id=device_id)
                    logging.info("Skipped to next track.")
                    cached_track_info = None
                    last_poll_time = 0
                    needs_redraw = True
                    last_api_error = None
                except Exception as e:
                    logging.error(f"Error skipping to next track: {e}", exc_info=True)
                    last_api_error = f"Cmd Error: {truncate_text(str(e), usable_x - 15)}"
                    needs_redraw = True

            elif key in (ord("<"), ord(",")):
                try:
                    sp.previous_track(device_id=device_id)
                    logging.info("Skipped to previous track.")
                    cached_track_info = None
                    last_poll_time = 0
                    needs_redraw = True
                    last_api_error = None
                except Exception as e:
                    logging.error(f"Error returning to previous track: {e}", exc_info=True)
                    last_api_error = f"Cmd Error: {truncate_text(str(e), usable_x - 15)}"
                    needs_redraw = True

            elif key in (ord("s"), ord("S")):
                try:
                    current_playback_state_check = sp.current_playback(market='from_token')
                    current_shuffle = cached_shuffle_state
                    if current_playback_state_check is not None and "shuffle_state" in current_playback_state_check:
                         current_shuffle = current_playback_state_check["shuffle_state"]

                    new_shuffle_state = not current_shuffle if current_shuffle is not None else True

                    sp.shuffle(state=new_shuffle_state, device_id=device_id)
                    logging.info(f"Shuffle set to {new_shuffle_state}.")
                    time.sleep(0.1)
                    cached_shuffle_state = new_shuffle_state

                    last_poll_time = 0
                    needs_redraw = True
                    last_api_error = None

                except Exception as e:
                    logging.error(f"Error toggling shuffle: {e}", exc_info=True)
                    last_api_error = f"Cmd Error: {truncate_text(str(e), usable_x - 15)}"
                    needs_redraw = True

            elif key in (ord("x"), ord("X")):
                 try:
                    current_playback_state_exit = sp.current_playback(market='from_token')
                    if current_playback_state_exit and current_playback_state_exit.get("device"):
                         sp.pause_playback(device_id=current_playback_state_exit["device"]["id"])
                         logging.info("Playback paused due to X key exit")
                    elif device_id:
                         try:
                              sp.pause_playback(device_id=device_id)
                              logging.info(f"Attempted pause on selected device {device_id} due to X key exit.")
                         except Exception as e:
                              logging.warning(f"Could not pause playback on selected device {device_id} on X key exit: {e}")

                 except Exception as e:
                     logging.warning(f"Could not pause playback on X key exit: {e}")

                 running = False

            if key_handled:
                pass

        if needs_redraw:
            if size_changed:
                stdscr.clear()
                stdscr.bkgd(' ', curses.color_pair(1))
                stdscr.touchwin()

            header_win.clear()
            body_win.clear()
            command_win.clear()

            header = "- Spotify Playlist Player"
            header_win.addstr(0, 0, truncate_text(header, usable_x), curses.color_pair(5) | curses.A_BOLD)
            header_win.noutrefresh()

            if playlist_info:
                plist_line = f"{playlist_info['name']} by {playlist_info['owner']['display_name']}"
                body_win.addstr(0, 0, "Playlist: ", curses.color_pair(3))
                body_win.addstr(truncate_text(plist_line, usable_x - len("Playlist: ")), curses.color_pair(2))

            display_track_info = current_playback_state.get("item") if current_playback_state else cached_track_info
            display_is_playing = current_playback_state.get("is_playing", False) if current_playback_state else cached_is_playing
            display_shuffle_state = current_playback_state.get("shuffle_state", False) if current_playback_state else cached_shuffle_state

            if display_track_info:
                item = display_track_info
                track_name = item.get("name", "Unknown Track")
                artists = ", ".join([a["name"] for a in item.get("artists", [])]) if item.get("artists") else "Unknown Artist"
                album = item.get("album", {}).get("name", "Unknown Album")
                release_date = item.get("album", {}).get("release_date", "----")
                album_year = release_date[:4] if release_date and (release_date.startswith('2') or release_date.startswith('1')) else "----"
                album_line = f"{album} ({album_year})"

                info_start_row = 2

                display_lines = [
                    ("Track: ", track_name, info_start_row, 2),
                    ("Artist: ", artists, info_start_row + 1, 4),
                    ("Album: ", album_line, info_start_row + 2, 1),
                ]

                labels = [line[0] for line in display_lines]
                max_label_len = max(len(label) for label in labels) if labels else 0

                for label, content, row, color in display_lines:
                    content_start_col = max_label_len + 1
                    content_max_width = usable_x - content_start_col - 1
                    if content_max_width < 0: content_max_width = 0

                    body_win.addstr(row, 0, label, curses.color_pair(3))
                    body_win.addstr(row, content_start_col, truncate_text(content, content_max_width), curses.color_pair(color))

                status_row = info_start_row + 4
                if status_row < body_h:
                    play_status = "▶ Playing" if display_is_playing else "⏸ Paused"
                    status_color = 7 if display_is_playing else 6
                    body_win.addstr(status_row, 0, play_status, curses.color_pair(status_color))

                    shuffle_text = "☯ Shuffle:On" if display_shuffle_state else "➡ Shuffle:Off"
                    shuffle_color = 7 if display_shuffle_state else 3
                    shuffle_col = len(play_status) + 3
                    if shuffle_col < usable_x:
                         body_win.addstr(status_row, shuffle_col, shuffle_text, curses.color_pair(shuffle_color))

            else:
                body_win.addstr(3, 0, "Waiting for playback info...", curses.color_pair(3))
                body_win.addstr(4, 0, "Make sure a device is active and playing.", curses.color_pair(3))

            if last_api_error:
                 error_row = body_h - 1
                 if error_row >= 0:
                      body_win.clrtoeol()
                      body_win.addstr(error_row, 0, truncate_text(last_api_error, usable_x - 1), curses.color_pair(6))

            body_win.noutrefresh()
            command_win.clear()

            commands = [
                ("P", "Play/Pause"),
                ("<", "Prev"),
                (">", "Next"),
                ("ESC", "Back"),
                ("S", "Shaffle"),
                ("X", "Exit"),
            ]

            cmd_str_parts = [f"{key}:{action}" for key, action in commands]
            cmd_str = "  ".join(cmd_str_parts)
            command_win.addstr(0, 0, truncate_text(cmd_str, usable_x - 1), curses.color_pair(3))
            command_win.noutrefresh()

            curses.doupdate()

            needs_redraw = False

        time.sleep(POLLING_INTERVAL)

    try:
        current_playback_state_exit = sp.current_playback(market='from_token')
        if current_playback_state_exit and current_playback_state_exit.get("device"):
             sp.pause_playback(device_id=current_playback_state_exit["device"]["id"])
             logging.info("Playback paused on exit")
        elif device_id:
             try:
                  sp.pause_playback(device_id=device_id)
                  logging.info(f"Attempted pause on selected device {device_id} on exit.")
             except Exception as e:
                  logging.warning(f"Could not pause playback on selected device {device_id} on exit: {e}")

    except Exception as e:
        logging.warning(f"Could not pause playback on exit: {e}")


def process_playlist(playlist):
    clear_screen()
    print(f"Selected Playlist: {playlist['name']} by {playlist['owner']['display_name']}")

    total_tracks = playlist.get("tracks", {}).get("total", "N/A")
    print(f"Fetching {total_tracks} tracks...")

    tracks = get_all_playlist_tracks(playlist["id"])
    if not tracks:
        print("No playable tracks found in the selected playlist.")
        return

    print(f"Successfully fetched {len(tracks)} playable tracks.")
    print("Selecting a device...")

    device_id = select_device()
    if not device_id:
        print("No device selected. Returning to search menu.")
        return

    print("\nStarting playback. Entering playback control mode (Curses UI)...")

    try:
        curses.wrapper(playback_curses, sp, playlist, tracks, device_id)
        print("\nPlayback session ended.")

    except Exception as e:
        try:
             curses.endwin()
        except:
             pass

        logging.error(f"Error during playback (curses mode): {e}", exc_info=True)
        print(f"\nAn error occurred during playback: {e}")
        print("Exiting playback mode.")


def main():
    try:
        clear_screen()
        while True:
            query = get_search_query()

            if query is None:
                 print("Input error, please try again.")
                 continue
            if not query.strip():
                print("Search query cannot be empty.")
                continue

            playlists = search_playlists(query)

            if not playlists:
                print(f"No playlists found for '{query}'.")
                continue

            selected_playlist = select_playlist(playlists)

            if selected_playlist:
                process_playlist(selected_playlist)

    except KeyboardInterrupt:
        print("\nCtrl+C detected. Exiting program.")
        try:
            current_playback_state = sp.current_playback(market='from_token')
            if current_playback_state and current_playback_state.get("device"):
                sp.pause_playback(device_id=current_playback_state["device"]["id"])
                logging.info("Playback paused on Ctrl+C exit")
        except Exception as e:
            logging.warning(f"Could not pause playback on Ctrl+C exit: {e}")
        sys.exit(0)

    except Exception as e:
        logging.error(f"Unhandled error in main loop: {e}", exc_info=True)
        print(f"\nAn unexpected error occurred: {e}")
        print("Exiting.")
        sys.exit(1)


if __name__ == "__main__":
    main()

