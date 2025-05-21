import os
import sys
import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import curses
import time
import logging
import platform
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", stream=sys.stderr)

# Spotify API credentials
CLIENT_ID = os.environ.get("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("SPOTIPY_REDIRECT_URI", "https://127.0.0.0/")

# Validate credentials
if not (CLIENT_ID and CLIENT_SECRET and REDIRECT_URI):
    print("Error: Spotify Client ID, Client Secret, or Redirect URI is not set.")
    print("Please set SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, and SPOTIPY_REDIRECT_URI environment variables.")
    sys.exit(1)

# Cache directory setup
user_home = os.path.expanduser("~")
cache_dir = os.path.join(user_home, ".cache", "spotify")
os.makedirs(cache_dir, exist_ok=True)
CACHE_PATH = os.path.join(cache_dir, ".spotify_cache")

# Spotify API scope
scope = "user-read-private user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-read-private"

# Initialize Spotify client
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
    logging.info(f"Spotify authentication successful for user: {user_profile.get('display_name', 'N/A')}")
    print("Spotify authentication successful.")
except Exception as e:
    logging.error(f"Authentication failed: {e}", exc_info=True)
    print("Error: Spotify authentication failed. Please check credentials, environment variables, and network connection.")
    print(f"Details: {e}")
    sys.exit(1)

def truncate_text(text, max_length):
    """Truncate text to max_length, adding '...' if needed."""
    if not isinstance(text, str):
        text = str(text)
    if max_length is None or max_length < 0:
        return text
    if max_length < 4:
        return text[:max_length]
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."

def clear_screen(stdscr=None):
    """Clear the terminal screen. Use curses if stdscr provided, else OS command."""
    if stdscr:
        try:
            stdscr.clear()
            stdscr.refresh()
        except curses.error as e:
            logging.warning(f"Curses clear failed, attempting OS clear: {e}", exc_info=True)
            os_clear()
    else:
        os_clear()
        print(" - Spotify Playlist Player\n")

def os_clear():
    """Clear terminal using OS-specific commands and ANSI codes."""
    os.system("cls" if os.name == "nt" else "clear")
    print("\033[2J\033[H", end="", flush=True)

def getch():
    """Read a single character from terminal (assumes raw mode set externally)."""
    try:
        if platform.system() == "Windows":
            import msvcrt
            return msvcrt.getch().decode("utf-8", errors='ignore')
        else:
            return sys.stdin.read(1)
    except ImportError:
        logging.error("Required modules for getch (msvcrt/termios) not found.", exc_info=True)
        return ''
    except EOFError:
        logging.error("EOFError in getch. Input stream might be closed.", exc_info=True)
        return ''
    except Exception as e:
        logging.error(f"Error reading character in getch: {e}", exc_info=True)
        return ''

def get_search_query():
    """Get search query character by character, managing raw mode."""
    fd = sys.stdin.fileno()
    original_termios_settings = None
    prompt = " Search: "
    query = ""

    clear_screen()
    sys.stdout.write(prompt)
    sys.stdout.flush()

    if platform.system() != "Windows":
        try:
            import termios, tty
            original_termios_settings = termios.tcgetattr(fd)
            logging.debug("Setting terminal to raw mode for get_search_query")
            tty.setraw(fd)
        except Exception as e:
            logging.error(f"Failed to set terminal to raw mode: {e}. Input will be buffered.", exc_info=True)
            logging.error("Falling back to standard input (no character editing). Press Enter after typing.")
            sys.stdout.write(prompt)
            sys.stdout.flush()
            try:
                query = input()
                return query.strip()
            except KeyboardInterrupt:
                print("\nCtrl+C pressed. Exiting.")
                raise
            except Exception as e:
                logging.error(f"Error during standard input fallback: {e}", exc_info=True)
                print(f"\nAn error occurred: {e}.")
                return ""

    try:
        while True:
            ch = getch()
            logging.debug(f"Read char in raw mode: {ord(ch) if ch else 'N/A'} ({ch!r})")

            if not ch:
                logging.debug("getch returned empty string, breaking input loop.")
                break

            if ord(ch) == 3:
                logging.debug("Ctrl+C detected in raw mode input")
                raise KeyboardInterrupt

            if ch in ('\r', '\n'):
                sys.stdout.write('\n')
                sys.stdout.flush()
                break

            if ord(ch) in (8, 127):
                if query:
                    query = query[:-1]
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
                else:
                    pass
            elif ord(ch) == 27:
                logging.debug("ESC key detected")
                print("\nESC pressed. Returning.")
                return None
            elif ' ' <= ch <= '~' or ord(ch) >= 128:
                query += ch
                sys.stdout.write(ch)
                sys.stdout.flush()
            else:
                logging.debug(f"Ignoring control character: {ord(ch)}")

    except KeyboardInterrupt:
        print("\nCtrl+C pressed. Exiting.")
        raise
    except Exception as e:
        logging.error(f"Error during search query raw input loop: {e}", exc_info=True)
        print(f"\nAn unexpected error occurred during input: {e}.")
        pass

    finally:
        if original_termios_settings and platform.system() != "Windows":
            try:
                import termios
                logging.debug("Restoring terminal settings after get_search_query")
                termios.tcsetattr(fd, termios.TCSADRAIN, original_termios_settings)
                sys.stdout.write('\r\n')
                sys.stdout.flush()
            except Exception as restore_e:
                logging.error(f"Failed to restore terminal settings: {restore_e}", exc_info=True)

    return query.strip()

def search_playlists(query, limit=50):
    """Search Spotify for playlists based on query."""
    try:
        if query == "0":
            print("Fetching your playlists...")
            playlists = []
            offset = 0
            playlist_fetch_limit = 50
            while True:
                results = sp.current_user_playlists(limit=playlist_fetch_limit, offset=offset)
                items = results.get("items", [])
                if not items:
                    break
                playlists.extend(items)
                if len(items) < playlist_fetch_limit:
                    break
                offset += playlist_fetch_limit
            logging.info(f"Retrieved user's playlists. Count: {len(playlists)}")
        else:
            print(f"Searching for playlists matching '{query}'...")
            search_api_limit = 50
            result = sp.search(q=query, type="playlist", limit=search_api_limit)
            playlists = result["playlists"]["items"] if "playlists" in result else []
            logging.info(f"Searched for playlists with query '{query}'. Count: {len(playlists)}")

        valid_playlists = [
            pl for pl in playlists
            if pl and pl.get("tracks") is not None and pl.get("tracks", {}).get("total") is not None
        ]
        return valid_playlists
    except Exception as e:
        logging.error(f"Error searching playlists: {e}", exc_info=True)
        print(f"Error searching playlists: {e}")
        return []

def display_commands_popup(stdscr, commands, title="Commands"):
    """Display commands in a temporary popup window."""
    max_key_width = max(len(k) for k, _ in commands) if commands else 0
    max_action_width = max(len(a) for _, a in commands) if commands else 0
    command_line_width = max_key_width + len(": ") + max_action_width
    popup_width = max(command_line_width, len(title)) + 4
    popup_height = len(commands) + 3
    max_y, max_x = stdscr.getmaxyx()

    if popup_height > max_y or popup_width > max_x:
        logging.warning(f"Terminal too small to display command popup ({popup_width}x{popup_height}). Terminal size: {max_x}x{max_y}")
        return

    popup_y = (max_y - popup_height) // 2
    popup_x = (max_x - popup_width) // 2
    popup_win = curses.newwin(popup_height, popup_width, popup_y, popup_x)
    popup_win.bkgd(' ', curses.A_NORMAL)  # Set transparent background
    popup_win.box()
    title_start_col = (popup_width - len(title)) // 2
    popup_win.addstr(1, title_start_col, title, curses.A_BOLD)
    key_end_col_in_popup = 2 + max_key_width
    action_start_col_in_popup = key_end_col_in_popup + len(": ")

    for i, (key_str, action_str) in enumerate(commands):
        row = 2 + i
        key_start_col_in_popup = key_end_col_in_popup - len(key_str)
        popup_win.addstr(row, key_start_col_in_popup, key_str, curses.A_NORMAL)
        popup_win.addstr(row, key_end_col_in_popup, ": ", curses.A_NORMAL)
        popup_win.addstr(row, action_start_col_in_popup, action_str, curses.A_NORMAL)

    stdscr.noutrefresh()
    popup_win.noutrefresh()
    curses.doupdate()
    getch()
    stdscr.clear()
    stdscr.noutrefresh()
    curses.doupdate()
    del popup_win

def select_playlist_curses(stdscr, playlists):
    """Display a paginated list of playlists using curses and allow user selection."""
    curses.curs_set(0)
    curses.use_default_colors()  # Ensure terminal's default background
    stdscr.bkgd(' ', curses.A_NORMAL)  # Set transparent background
    stdscr.nodelay(True)
    stdscr.timeout(100)

    sorted_playlists = sorted(
        [pl for pl in playlists if pl.get("tracks", {}).get("total") is not None],
        key=lambda p: p["tracks"]["total"],
        reverse=True
    )

    selected = 0
    per_page = 15
    total = len(sorted_playlists)
    total_pages = (total + per_page - 1) // per_page

    while True:
        stdscr.erase()
        max_y, max_x = stdscr.getmaxyx()
        page = selected // per_page
        start = page * per_page
        end = min(start + per_page, total)

        # Header
        header = f"- Playlist Page {page + 1}/{total_pages}"
        stdscr.addstr(0, 0, header[:max_x], curses.A_BOLD)

        # Display playlists
        for idx in range(start, end):
            pl = sorted_playlists[idx]
            name = pl["name"]
            tracks = pl.get("tracks", {}).get("total", "?")
            line = f"{idx + 1:3d}. {name} ({tracks} tracks)"
            row = idx - start + 2
            if row < max_y - 1:
                if idx == selected:
                    stdscr.addstr(row, 0, line[:max_x], curses.A_REVERSE)
                else:
                    stdscr.addstr(row, 0, line[:max_x], curses.A_NORMAL)

        # Command help at bottom
        help_text = "[ move: hjkl/arrows | select: Enter | cancel: ESC/Q ]"
        stdscr.addstr(max_y - 1, 0, help_text[:max_x], curses.A_BOLD)

        stdscr.refresh()
        key = stdscr.getch()

        if key in (ord('q'), ord('Q'), 27):  # ESC or Q
            return None
        elif key in (curses.KEY_UP, ord('k')):
            if selected > 0:
                selected -= 1
        elif key in (curses.KEY_DOWN, ord('j')):
            if selected < total - 1:
                selected += 1
        elif key in (curses.KEY_LEFT, ord('h')):
            selected = max(0, selected - per_page)
        elif key in (curses.KEY_RIGHT, ord('l')):
            selected = min(total - 1, selected + per_page)
        elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            return sorted_playlists[selected]

def get_all_playlist_tracks(playlist_id):
    """Fetch all tracks from a playlist ID with caching."""
    cache_file = os.path.join(cache_dir, f"playlist_{playlist_id}.json")
    try:
        with open(cache_file, 'r') as f:
            tracks = json.load(f)
            logging.info(f"Loaded {len(tracks)} tracks from cache for playlist {playlist_id}")
            return tracks
    except FileNotFoundError:
        logging.debug(f"No cache found for playlist {playlist_id}")
    except Exception as e:
        logging.warning(f"Failed to load playlist cache: {e}", exc_info=True)

    tracks = []
    offset = 0
    limit = 100
    retry_limit = 3
    print("Fetching playlist tracks...")
    try:
        while True:
            attempt = 0
            results = None
            while attempt < retry_limit:
                try:
                    results = sp.playlist_items(
                        playlist_id,
                        offset=offset,
                        limit=limit,
                        fields="items(track(id,name,artists(name),album(id,name,release_date)))",
                        market='from_token'
                    )
                    break
                except spotipy.exceptions.SpotifyException as se:
                    attempt += 1
                    retry_after = int(se.headers.get('Retry-After', 2)) if se.http_status == 429 else 2
                    logging.warning(f"Attempt {attempt}/{retry_limit}: Spotify API error retrieving tracks: {se}. Retrying after {retry_after}s")
                    if attempt < retry_limit:
                        print(f"Retrying track fetch ({attempt}/{retry_limit})...")
                        time.sleep(retry_after)
                    else:
                        logging.error("Max retry attempts reached for retrieving tracks.")
                        print(f"Failed to fetch tracks after multiple retries: {se}")
                        return tracks
                except Exception as e:
                    attempt += 1
                    logging.warning(f"Attempt {attempt}/{retry_limit}: Unexpected error retrieving tracks: {e}")
                    if attempt < retry_limit:
                        print(f"Retrying track fetch ({attempt}/{retry_limit})...")
                        time.sleep(2)
                    else:
                        logging.error("Max retry attempts reached for retrieving tracks.")
                        print(f"Failed to fetch tracks after multiple retries: {e}")
                        return tracks

            if results is None or not results.get("items"):
                break

            valid_items_count = 0
            for item in results.get("items", []):
                track = item.get("track")
                if track and track.get("id") and track.get("name") and track.get("artists"):
                    tracks.append(track)
                    valid_items_count += 1
                else:
                    logging.debug(f"Skipping invalid track item: {item}")

            if len(results.get("items", [])) < limit and valid_items_count > 0:
                break
            if len(results.get("items", [])) == 0:
                break

            offset += limit
            sys.stdout.flush()

        try:
            with open(cache_file, 'w') as f:
                json.dump(tracks, f)
            logging.info(f"Saved {len(tracks)} tracks to cache for playlist {playlist_id}")
        except Exception as e:
            logging.warning(f"Failed to save playlist cache: {e}", exc_info=True)

        print(f"\nFinished fetching tracks. Retrieved {len(tracks)} valid tracks.")
        logging.info(f"Finished fetching tracks. Retrieved {len(tracks)} valid tracks from playlist {playlist_id}.")
        return tracks
    except Exception as e:
        logging.error(f"Critical error during track fetching loop: {e}", exc_info=True)
        print(f"Critical error during track fetching: {e}")
        return tracks

def select_device_curses(stdscr):
    """Display a list of Spotify devices using curses and allow user selection."""
    curses.curs_set(0)
    curses.use_default_colors()  # Ensure terminal's default background
    stdscr.bkgd(' ', curses.A_NORMAL)  # Set transparent background
    stdscr.nodelay(True)
    stdscr.timeout(100)

    try:
        devices = sp.devices()["devices"]
    except Exception as e:
        stdscr.erase()
        stdscr.addstr(1, 0, "Failed to fetch devices.", curses.A_BOLD)
        stdscr.addstr(3, 0, str(e), curses.A_NORMAL)
        stdscr.addstr(5, 0, "Press any key to return.")
        stdscr.refresh()
        stdscr.getch()
        return None

    if not devices:
        stdscr.erase()
        stdscr.addstr(1, 0, "No active Spotify devices found.", curses.A_BOLD)
        stdscr.addstr(3, 0, "Ensure Spotify is running and active on some device.")
        stdscr.addstr(5, 0, "Press any key to return.")
        stdscr.refresh()
        stdscr.getch()
        return None

    selected = 0
    total = len(devices)

    while True:
        stdscr.erase()
        max_y, max_x = stdscr.getmaxyx()

        # Header
        stdscr.addstr(0, 0, "- Device", curses.A_BOLD)

        # Display devices
        for idx, d in enumerate(devices):
            name = d.get("name", "Unknown")
            dtype = d.get("type", "Unknown")
            active = "[Active]" if d.get("is_active") else ""
            line = f"{idx + 1:3d}. {name} ({dtype}) {active}"
            row = idx + 2
            if row < max_y - 1:
                if idx == selected:
                    stdscr.addstr(row, 0, line[:max_x], curses.A_REVERSE)
                else:
                    stdscr.addstr(row, 0, line[:max_x], curses.A_NORMAL)

        # Footer
        help_text = "[ move: hjkl/arrows | select: Enter | cancel: ESC/Q ]"
        stdscr.addstr(max_y - 1, 0, help_text[:max_x], curses.A_BOLD)

        stdscr.refresh()
        key = stdscr.getch()

        if key in (ord('q'), ord('Q'), 27):  # ESC or Q
            return None
        elif key in (curses.KEY_UP, ord('k')):
            if selected > 0:
                selected -= 1
        elif key in (curses.KEY_DOWN, ord('j')):
            if selected < total - 1:
                selected += 1
        elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            return devices[selected]

def playback_curses(stdscr, sp_client, playlist_info, tracks, selected_device):
    """Run curses UI for playback control with progress bar and caching."""
    device_id = selected_device['id']
    device_name = selected_device.get('name', 'Unknown Device')
    device_supports_volume = selected_device.get('supports_volume', False)
    MIN_PLAYBACK_TERM_Y = 10
    MIN_PLAYBACK_TERM_X = 40
    max_y, max_x = stdscr.getmaxyx()
    if max_y < MIN_PLAYBACK_TERM_Y or max_x < MIN_PLAYBACK_TERM_X:
        raise ValueError(f"Terminal too small for playback UI. Needs at least {MIN_PLAYBACK_TERM_Y}x{MIN_PLAYBACK_TERM_X}. Current size: {max_y}x{max_x}")

    curses.curs_set(0)
    curses.use_default_colors()  # Ensure terminal's default background
    stdscr.bkgd(' ', curses.A_NORMAL)  # Set transparent background
    stdscr.nodelay(True)
    stdscr.timeout(500)  # Increased to 500ms to reduce flicker
    padding = 1
    header_h = 1
    min_body_h_required = 6
    usable_y = max_y - (padding * 2)
    usable_x = max_x - (padding * 2)
    body_h = usable_y - header_h - 1
    min_required_y = header_h + 1 + min_body_h_required + 1 + padding
    if max_y < min_required_y or body_h < min_body_h_required:
        raise ValueError(f"Terminal height too small for layout. Needs at least {min_required_y} lines. Current size: {max_y}x{max_x}")

    try:
        header_win = curses.newwin(header_h, usable_x, padding, padding)
        body_win = curses.newwin(body_h, usable_x, padding + header_h + 1, padding)
        header_win.bkgd(' ', curses.A_NORMAL)  # Set transparent background
        body_win.bkgd(' ', curses.A_NORMAL)  # Set transparent background
    except curses.error as e:
        logging.error(f"Failed to create curses windows: {e}", exc_info=True)
        raise ValueError(f"Failed to initialize UI windows: {e}") from e

    stdscr.clear()
    stdscr.refresh()
    playlist_uri = playlist_info.get('uri')
    first_track_uri = None
    if tracks and tracks[0] and tracks[0].get("id"):
        first_track_uri = f"spotify:track:{tracks[0]['id']}"

    if not playlist_uri or not first_track_uri:
        body_win.addstr(0, 0, "Error: Cannot start playback - missing playlist or track URI.", curses.A_BOLD)
        body_win.addstr(1, 0, "Ensure playlist has valid tracks.", curses.A_NORMAL)
        body_win.noutrefresh()
        stdscr.addstr(max_y - padding - 1, padding, "Press any key to return.", curses.A_BOLD)
        stdscr.noutrefresh()
        curses.doupdate()
        stdscr.getch()
        try:
            if 'header_win' in locals() and header_win:
                header_win.clear()
                del header_win
            if 'body_win' in locals() and body_win:
                body_win.clear()
                del body_win
        except NameError:
            logging.debug("NameError during window cleanup, likely undefined header_win/body_win")
            pass
        except Exception as e:
            logging.warning(f"Error cleaning up windows: {e}", exc_info=True)
        stdscr.clear()
        stdscr.refresh()
        return True

    try:
        sp_client.start_playback(
            device_id=device_id,
            context_uri=playlist_uri,
            offset={'uri': first_track_uri},
        )
        logging.info(f"Started playback for playlist {playlist_uri} from track {first_track_uri}.")
        time.sleep(1)
    except spotipy.exceptions.SpotifyException as e:
        logging.error(f"SpotifyException starting playback: {e}", exc_info=True)
        body_win.addstr(0, 0, "Failed to start playback (Spotify API Error).", curses.A_BOLD)
        body_win.addstr(1, 0, truncate_text(str(e), usable_x - 1), curses.A_NORMAL)
        body_win.addstr(2, 0, "Check device status, Premium account, or playlist validity.", curses.A_NORMAL)
        body_win.noutrefresh()
        stdscr.addstr(max_y - padding - 1, padding, "Press any key to return.", curses.A_BOLD)
        stdscr.noutrefresh()
        curses.doupdate()
        stdscr.getch()
        try:
            if 'header_win' in locals() and header_win:
                header_win.clear()
                del header_win
            if 'body_win' in locals() and body_win:
                body_win.clear()
                del body_win
        except NameError:
            logging.debug("NameError during window cleanup, likely undefined header_win/body_win")
            pass
        except Exception as e:
            logging.warning(f"Error cleaning up windows: {e}", exc_info=True)
        stdscr.clear()
        stdscr.refresh()
        return True
    except Exception as e:
        logging.error(f"Unexpected error starting playback: {e}", exc_info=True)
        body_win.addstr(0, 0, "Failed to start playback (Unexpected Error).", curses.A_BOLD)
        body_win.addstr(1, 0, truncate_text(str(e), usable_x - 1), curses.A_NORMAL)
        body_win.addstr(2, 0, "Note: Playback control requires a Spotify Premium account.", curses.A_NORMAL)
        body_win.noutrefresh()
        stdscr.addstr(max_y - padding - 1, padding, "Press any key to return.", curses.A_BOLD)
        stdscr.noutrefresh()
        curses.doupdate()
        stdscr.getch()
        try:
            if 'header_win' in locals() and header_win:
                header_win.clear()
                del header_win
            if 'body_win' in locals() and body_win:
                body_win.clear()
                del body_win
        except NameError:
            logging.debug("NameError during window cleanup, likely undefined header_win/body_win")
            pass
        except Exception as e:
            logging.warning(f"Error cleaning up windows: {e}", exc_info=True)
        stdscr.clear()
        stdscr.refresh()
        return True

    cached_playback_state = None
    last_playback_state_hash = None
    last_api_error = None
    needs_redraw = True
    last_poll_time = 0
    POLLING_INTERVAL = 2.0
    current_volume_percent = None
    cache_file = os.path.join(cache_dir, f"playback_cache_{device_id}.json")

    def save_playback_cache(state):
        """Save playback state to cache."""
        try:
            with open(cache_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            logging.warning(f"Failed to save playback cache: {e}", exc_info=True)

    def load_playback_cache():
        """Load playback state from cache."""
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except Exception as e:
            logging.warning(f"Failed to load playback cache: {e}", exc_info=True)
            return None

    def format_time(ms):
        """Convert milliseconds to MM:SS format."""
        if ms is None:
            return "--:--"
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def draw_progress_bar(progress_ms, duration_ms, bar_width):
        """Draw progress bar using '*' for filled and '-' for empty."""
        if progress_ms is None or duration_ms is None or duration_ms == 0:
            return "-" * bar_width
        progress = min(progress_ms / duration_ms, 1.0)
        filled = int(bar_width * progress)
        empty = bar_width - filled
        return f"{'=' * filled}{'-' * empty}"

    try:
        initial_state = sp_client.current_playback(market='from_token')
        if initial_state and initial_state.get("device", {}).get("id") == device_id and initial_state.get("device", {}).get("supports_volume"):
            current_volume_percent = initial_state["device"].get("volume_percent")
            logging.debug(f"Got initial volume: {current_volume_percent}%")
        elif selected_device.get("supports_volume"):
            try:
                devices = sp_client.devices().get("devices", [])
                selected_device_info = next((d for d in devices if d.get("id") == device_id), None)
                if selected_device_info and selected_device_info.get("supports_volume"):
                    current_volume_percent = selected_device_info.get("volume_percent")
                    logging.debug(f"Got initial volume from devices list: {current_volume_percent}%")
            except Exception as e:
                logging.debug(f"Could not get initial volume from devices list: {e}", exc_info=True)
    except Exception as e:
        logging.debug(f"Could not get initial playback state or volume: {e}", exc_info=True)

    running = True
    exit_program = False
    prev_state = None

    try:
        while running:
            current_max_y, current_max_x = stdscr.getmaxyx()
            size_changed = (current_max_y != max_y or current_max_x != max_x)
            if size_changed:
                max_y, max_x = current_max_y, current_max_x
                usable_y = max_y - (padding * 2)
                usable_x = max_x - (padding * 2)
                body_h = usable_y - header_h - 1
                min_required_y = header_h + 1 + min_body_h_required + 1 + padding
                if max_y < min_required_y or body_h < min_body_h_required:
                    raise ValueError(f"Terminal resized too small. Needs at least {min_required_y} lines. Current size: {max_y}x{max_x}")

                try:
                    if 'header_win' in locals() and header_win:
                        header_win.clear()
                        del header_win
                    if 'body_win' in locals() and body_win:
                        body_win.clear()
                        del body_win
                except NameError:
                    logging.debug("NameError during window cleanup, likely undefined header_win/body_win")
                    pass
                except Exception as e:
                    logging.warning(f"Error deleting old windows during resize: {e}", exc_info=True)

                try:
                    header_win = curses.newwin(header_h, usable_x, padding, padding)
                    body_win = curses.newwin(body_h, usable_x, padding + header_h + 1, padding)
                    header_win.bkgd(' ', curses.A_NORMAL)  # Set transparent background
                    body_win.bkgd(' ', curses.A_NORMAL)  # Set transparent background
                except curses.error as e:
                    logging.error(f"Failed to create curses windows: {e}", exc_info=True)
                    raise ValueError(f"Failed to resize UI windows: {e}") from e

                stdscr.clear()
                stdscr.touchwin()
                needs_redraw = True

            current_time = time.time()
            poll_needed = (current_time - last_poll_time >= POLLING_INTERVAL) or needs_redraw
            if poll_needed:
                try:
                    new_playback_state = sp_client.current_playback(market='from_token')
                    state_hash = hashlib.md5(json.dumps(new_playback_state, sort_keys=True).encode()).hexdigest()
                    if state_hash != last_playback_state_hash:
                        cached_playback_state = new_playback_state
                        last_playback_state_hash = state_hash
                        save_playback_cache(cached_playback_state)
                        last_api_error = None
                        needs_redraw = True
                        if cached_playback_state and cached_playback_state.get("device", {}).get("id") == device_id and cached_playback_state.get("device", {}).get("supports_volume"):
                            new_volume = cached_playback_state["device"].get("volume_percent")
                            if new_volume is not None and new_volume != current_volume_percent:
                                logging.debug(f"Volume updated via API state: {new_volume}%")
                                current_volume_percent = new_volume
                    last_poll_time = current_time
                except spotipy.exceptions.SpotifyException as se:
                    if se.http_status == 429:
                        retry_after = int(se.headers.get('Retry-After', 2))
                        logging.warning(f"Rate limit hit, retrying after {retry_after} seconds")
                        time.sleep(retry_after)
                    else:
                        logging.error(f"Spotify API error: {se}", exc_info=True)
                        last_api_error = f"API Error: {truncate_text(str(se), usable_x - 15)}"
                        cached_playback_state = load_playback_cache()
                        needs_redraw = True
                except Exception as e:
                    logging.error(f"Error fetching playback state: {e}", exc_info=True)
                    last_api_error = f"API Error: {truncate_text(str(e), usable_x - 15)}"
                    cached_playback_state = load_playback_cache()
                    needs_redraw = True

            key = stdscr.getch()
            current_state = (cached_playback_state, current_volume_percent, max_y, max_x)
            if key != -1 or current_state != prev_state:
                needs_redraw = True

            if key != -1:
                if key == ord('?'):
                    commands_list = [
                        ("Enter/P", "Play/Pause"),
                        ("h/Left", "Previous Track"),
                        ("l/Right", "Next Track"),
                        ("j/Down", "Volume Down"),
                        ("k/Up", "Volume Up"),
                        ("S", "Toggle Shuffle"),
                        ("ESC/q", "Back to Search"),
                        ("X", "Exit Program"),
                    ]
                    display_commands_popup(stdscr, commands_list, "Playback Commands")
                    needs_redraw = True
                elif key in (ord("q"), ord("Q"), 27):
                    logging.info("Exiting playback UI via q, Q, or ESC. Attempting to pause playback.")
                    try:
                        pause_device_id = cached_playback_state.get("device", {}).get("id") if cached_playback_state and cached_playback_state.get("device") else selected_device['id']
                        if pause_device_id:
                            if cached_playback_state is None or cached_playback_state.get("is_playing", True):
                                sp_client.pause_playback(device_id=pause_device_id)
                                logging.info(f"Playback paused on device {pause_device_id} on UI exit.")
                            else:
                                logging.debug("Playback already paused, no need to pause on UI exit.")
                        else:
                            logging.warning("Could not determine device to pause on UI exit.")
                    except Exception as e:
                        logging.warning(f"Could not pause playback on UI exit: {e}", exc_info=True)
                    running = False
                elif key in (ord('\n'), ord('\r'), curses.KEY_ENTER, ord("p"), ord("P")):
                    try:
                        is_currently_playing = cached_playback_state.get("is_playing") if cached_playback_state else False
                        target_device_id = cached_playback_state.get("device", {}).get("id") if cached_playback_state and cached_playback_state.get("device") else selected_device['id']
                        if is_currently_playing:
                            sp_client.pause_playback(device_id=target_device_id)
                            logging.info("Playback paused.")
                        else:
                            sp_client.start_playback(device_id=target_device_id)
                            logging.info("Started/resumed playback.")
                        last_poll_time = 0
                        cached_playback_state = None
                        needs_redraw = True
                        last_api_error = None
                    except Exception as e:
                        logging.error(f"Error toggling playback: {e}", exc_info=True)
                        last_api_error = f"Cmd Error: {truncate_text(str(e), usable_x - 15)}"
                        needs_redraw = True
                elif key in (curses.KEY_RIGHT, ord('l'), ord('L')):
                    try:
                        target_device_id = cached_playback_state.get("device", {}).get("id") if cached_playback_state and cached_playback_state.get("device") else selected_device['id']
                        sp_client.next_track(device_id=target_device_id)
                        logging.info("Skipped to next track.")
                        last_poll_time = 0
                        cached_playback_state = None
                        needs_redraw = True
                        last_api_error = None
                    except Exception as e:
                        logging.error(f"Error skipping to next track: {e}", exc_info=True)
                        last_api_error = f"Cmd Error: {truncate_text(str(e), usable_x - 15)}"
                        needs_redraw = True
                elif key in (curses.KEY_LEFT, ord('h'), ord('H')):
                    try:
                        target_device_id = cached_playback_state.get("device", {}).get("id") if cached_playback_state and cached_playback_state.get("device") else selected_device['id']
                        sp_client.previous_track(device_id=target_device_id)
                        logging.info("Skipped to previous track.")
                        last_poll_time = 0
                        cached_playback_state = None
                        needs_redraw = True
                        last_api_error = None
                    except Exception as e:
                        logging.error(f"Error returning to previous track: {e}", exc_info=True)
                        last_api_error = f"Cmd Error: {truncate_text(str(e), usable_x - 15)}"
                        needs_redraw = True
                elif key in (curses.KEY_UP, ord('k'), ord('K')):
                    if device_supports_volume:
                        if current_volume_percent is None:
                            logging.debug("Volume up received but current_volume_percent is None, forcing poll.")
                            last_poll_time = 0
                            needs_redraw = True
                        else:
                            try:
                                new_volume = min(100, current_volume_percent + 5)
                                sp_client.volume(new_volume, device_id=device_id)
                                logging.info(f"Increased volume to {new_volume}%.")
                                current_volume_percent = new_volume
                                last_poll_time = 0
                                needs_redraw = True
                                last_api_error = None
                            except Exception as e:
                                logging.error(f"Error increasing volume: {e}", exc_info=True)
                                last_api_error = f"Vol Up Error: {truncate_text(str(e), usable_x - 20)}"
                                needs_redraw = True
                    else:
                        logging.debug("Volume up ignored: device does not support volume control.")
                        last_api_error = f"Device does not support volume control."
                        needs_redraw = True
                elif key in (curses.KEY_DOWN, ord('j'), ord('J')):
                    if device_supports_volume:
                        if current_volume_percent is None:
                            logging.debug("Volume down received but current_volume_percent is None, forcing poll.")
                            last_poll_time = 0
                            needs_redraw = True
                        else:
                            try:
                                new_volume = max(0, current_volume_percent - 5)
                                sp_client.volume(new_volume, device_id=device_id)
                                logging.info(f"Decreased volume to {new_volume}%.")
                                current_volume_percent = new_volume
                                last_poll_time = 0
                                needs_redraw = True
                                last_api_error = None
                            except Exception as e:
                                logging.error(f"Error decreasing volume: {e}", exc_info=True)
                                last_api_error = f"Vol Down Error: {truncate_text(str(e), usable_x - 20)}"
                                needs_redraw = True
                    else:
                        logging.debug("Volume down ignored: device does not support volume control.")
                        last_api_error = f"Device does not support volume control."
                        needs_redraw = True
                elif key in (ord("s"), ord("S")):
                    try:
                        target_device_id = cached_playback_state.get("device", {}).get("id") if cached_playback_state and cached_playback_state.get("device") else selected_device['id']
                        current_shuffle = cached_playback_state.get("shuffle_state", False) if cached_playback_state else False
                        new_shuffle_state = not current_shuffle
                        sp_client.shuffle(state=new_shuffle_state, device_id=target_device_id)
                        logging.info(f"Shuffle set to {new_shuffle_state}.")
                        time.sleep(0.1)
                        last_poll_time = 0
                        cached_playback_state = None
                        needs_redraw = True
                        last_api_error = None
                    except Exception as e:
                        logging.error(f"Error toggling shuffle: {e}", exc_info=True)
                        last_api_error = f"Cmd Error: {truncate_text(str(e), usable_x - 15)}"
                        needs_redraw = True
                elif key in (ord("x"), ord("X")):
                    logging.info("Exiting program via X. Attempting to pause playback.")
                    try:
                        pause_device_id = cached_playback_state.get("device", {}).get("id") if cached_playback_state and cached_playback_state.get("device") else selected_device['id']
                        if pause_device_id:
                            sp_client.pause_playback(device_id=pause_device_id)
                            logging.info(f"Playback paused on device {pause_device_id} due to X key exit.")
                        else:
                            logging.warning("Could not determine device to pause on X key exit.")
                    except Exception as e:
                        logging.warning(f"Could not pause playback on X key exit: {e}", exc_info=True)
                    running = False
                    exit_program = True

            if needs_redraw:
                header_win.clear()
                body_win.clear()
                header = "- Spotify Playlist Player"
                header_win.addstr(0, 0, truncate_text(header, usable_x), curses.A_BOLD)
                header_win.noutrefresh()
                item_display_data = []
                if playlist_info:
                    item_display_data.append((
                        "Playlist:",
                        f"{playlist_info['name']} by {playlist_info['owner']['display_name']}",
                        0,
                    ))
                display_playback_state = cached_playback_state if cached_playback_state else {}
                display_track_info = display_playback_state.get("item")
                progress_ms = display_playback_state.get("progress_ms")
                duration_ms = display_track_info.get("duration_ms") if display_track_info else None
                item_display_data.append((
                    "Device:",
                    f"{device_name}",
                    1,
                ))
                if display_track_info:
                    item = display_track_info
                    track_name = item.get("name", "Unknown Track")
                    artists = ", ".join([a.get("name", "Unknown Artist") for a in item.get("artists", [])]) if item.get("artists") else "Unknown Artist"
                    album = item.get("album", {}).get("name", "Unknown Album")
                    release_date = item.get("album", {}).get("release_date", "----")
                    album_year = release_date[:4] if release_date and release_date[:4].isdigit() else "----"
                    progress_time = f"{format_time(progress_ms)} / {format_time(duration_ms)}"
                    album_line = f"{album} ({album_year})"
                    item_display_data.extend([
                        ("Track:", track_name, 3),
                        ("Artist:", artists, 4),
                        ("Album:", album_line, 5),
                        ("Progress:", progress_time, 6),
                    ])
                    status_row_in_body = 8
                else:
                    waiting_message_start_col_in_body = 0
                    body_win.addstr(2, waiting_message_start_col_in_body, truncate_text("Waiting for playback info...", usable_x - waiting_message_start_col_in_body), curses.A_NORMAL)
                    if cached_playback_state is None:
                        body_win.addstr(3, waiting_message_start_col_in_body, truncate_text("Attempting to fetch playback state...", usable_x - waiting_message_start_col_in_body), curses.A_NORMAL)
                        body_win.addstr(4, waiting_message_start_col_in_body, truncate_text("Ensure a device is active and playing.", usable_x - waiting_message_start_col_in_body), curses.A_NORMAL)
                    else:
                        body_win.addstr(3, waiting_message_start_col_in_body, truncate_text("Playback stopped or no track loaded.", usable_x - waiting_message_start_col_in_body), curses.A_NORMAL)
                        current_active_device_name = display_playback_state.get("device", {}).get("name")
                        if current_active_device_name:
                            body_win.addstr(4, waiting_message_start_col_in_body, truncate_text(f"Active Device: {current_active_device_name}", usable_x - waiting_message_start_col_in_body), curses.A_NORMAL)
                    status_row_in_body = 6

                labels = [label for label, _, _ in item_display_data]
                max_label_len = max(len(label) for label in labels) if labels else 0
                content_start_col_in_body = min(max_label_len + 2, usable_x // 3)
                if content_start_col_in_body < 1:
                    content_start_col_in_body = 1
                for label, content, row_in_body in item_display_data:
                    if row_in_body < body_h:
                        label_col_end = content_start_col_in_body - 1
                        label_start_col_in_body = label_col_end - len(label)
                        label_start_col_in_body = max(0, label_start_col_in_body)
                        body_win.addstr(row_in_body, label_start_col_in_body, label, curses.A_BOLD)
                        content_max_width = usable_x - content_start_col_in_body - 1
                        if content_max_width < 0:
                            content_max_width = 0
                        body_win.addstr(row_in_body, content_start_col_in_body, truncate_text(content, content_max_width), curses.A_NORMAL)

                separator_row_in_body = 2
                if separator_row_in_body < body_h:
                    progress_bar = draw_progress_bar(progress_ms, duration_ms, usable_x)
                    body_win.addstr(separator_row_in_body, 0, progress_bar, curses.A_NORMAL)

                display_is_playing = display_playback_state.get("is_playing", False)
                display_shuffle_state = display_playback_state.get("shuffle_state", False)
                display_volume_percent = cached_playback_state.get("device", {}).get("volume_percent") if cached_playback_state and cached_playback_state.get("device", {}).get("supports_volume") else None
                if status_row_in_body < body_h:
                    play_status = "Playing" if display_is_playing else "Paused"
                    status_attr = curses.A_BOLD if display_is_playing else curses.A_NORMAL
                    body_win.addstr(status_row_in_body, 0, play_status, status_attr)
                    shuffle_text = "Shuffle: On" if display_shuffle_state else "Shuffle: Off"
                    shuffle_attr = curses.A_BOLD if display_shuffle_state else curses.A_NORMAL
                    shuffle_col_in_body = len(play_status) + 3
                    if shuffle_col_in_body < usable_x:
                        body_win.addstr(status_row_in_body, shuffle_col_in_body, truncate_text(shuffle_text, usable_x - shuffle_col_in_body - 1), shuffle_attr)
                    if device_supports_volume:
                        volume_text = f"Volume: {display_volume_percent}%" if display_volume_percent is not None else "Volume: N/A"
                        volume_col_in_body = shuffle_col_in_body + len(truncate_text(shuffle_text, usable_x - shuffle_col_in_body - 1)) + 3
                        if volume_col_in_body < usable_x:
                            body_win.addstr(status_row_in_body, volume_col_in_body, truncate_text(volume_text, usable_x - volume_col_in_body - 1), curses.A_NORMAL)
                else:
                    waiting_message_start_col_in_body = 0
                    body_win.addstr(2, waiting_message_start_col_in_body, truncate_text("Waiting for playback info...", usable_x - waiting_message_start_col_in_body), curses.A_NORMAL)
                    if cached_playback_state is None:
                        body_win.addstr(3, waiting_message_start_col_in_body, truncate_text("Attempting to fetch playback state...", usable_x - waiting_message_start_col_in_body), curses.A_NORMAL)
                        body_win.addstr(4, waiting_message_start_col_in_body, truncate_text("Ensure a device is active and playing.", usable_x - waiting_message_start_col_in_body), curses.A_NORMAL)
                    else:
                        body_win.addstr(3, waiting_message_start_col_in_body, truncate_text("Playback stopped or no track loaded.", usable_x - waiting_message_start_col_in_body), curses.A_NORMAL)
                        current_active_device_name = display_playback_state.get("device", {}).get("name")
                        if current_active_device_name:
                            body_win.addstr(4, waiting_message_start_col_in_body, truncate_text(f"Active Device: {current_active_device_name}", usable_x - waiting_message_start_col_in_body), curses.A_NORMAL)

                error_row_in_body = body_h - 1
                min_error_row_needed_in_body = status_row_in_body + 1
                if error_row_in_body >= max(0, min_error_row_needed_in_body) and error_row_in_body >= 0:
                    if last_api_error:
                        body_win.clrtoeol()
                        body_win.addstr(error_row_in_body, 0, truncate_text(last_api_error, usable_x - 1), curses.A_BOLD)
                    else:
                        body_win.move(error_row_in_body, 0)
                        body_win.clrtoeol()

                body_win.noutrefresh()
                commands_hint_line = "Press '?' for commands."
                stdscr.addstr(max_y - 1, padding, truncate_text(commands_hint_line, max_x - 2*padding), curses.A_BOLD)
                stdscr.clrtoeol()
                curses.doupdate()
                needs_redraw = False
                prev_state = current_state

    except Exception as e:
        logging.error(f"Unhandled error in playback_curses: {e}", exc_info=True)
        raise
    finally:
        logging.debug("Cleaning up windows in playback_curses finally block")
        try:
            if 'header_win' in locals() and header_win:
                header_win.clear()
                del header_win
            if 'body_win' in locals() and body_win:
                body_win.clear()
                del body_win
        except NameError:
            logging.debug("NameError during window cleanup, likely undefined header_win/body_win")
            pass
        except Exception as e:
            logging.warning(f"Error cleaning up windows in playback_curses finally: {e}", exc_info=True)
        try:
            stdscr.clear()
            stdscr.refresh()
            logging.debug("stdscr cleared and refreshed in playback_curses finally")
        except Exception as e:
            logging.warning(f"Failed to clear/refresh stdscr in playback_curses finally: {e}", exc_info=True)

    return not exit_program

def cleanup_playback(sp_client):
    """Attempt to pause current playback."""
    logging.info("Attempting to pause playback during cleanup.")
    try:
        current_playback_state = sp_client.current_playback(market='from_token')
        if current_playback_state and current_playback_state.get("device") and current_playback_state.get("is_playing"):
            device_id = current_playback_state["device"]["id"]
            sp_client.pause_playback(device_id=device_id)
            logging.info(f"Playback paused on device {device_id}.")
        else:
            logging.info("No active playback state found to pause.")
    except Exception as e:
        logging.warning(f"Could not pause playback during cleanup: {e}", exc_info=True)

def main():
    """Main function to run the Spotify playlist player."""
    clear_screen()
    print("Starting Spotify Playlist Player...")
    time.sleep(1)
    try:
        while True:
            query = get_search_query()
            if query is None:
                clear_screen()
                print("See you later! :)")
                break
            if not query:
                print("Search query cannot be empty.")
                input("Press Enter to continue...")
                continue
            playlists = search_playlists(query)
            if not playlists:
                print(f"No playlists found for '{query}'.")
                input("Press Enter to continue...")
                continue
            try:
                selected_playlist = curses.wrapper(select_playlist_curses, playlists)
                if selected_playlist is None:
                    print("Returning to search.")
                    continue
                print(f"Selected Playlist: {selected_playlist['name']} by {selected_playlist['owner']['display_name']}")
                tracks = get_all_playlist_tracks(selected_playlist['id'])
                if not tracks:
                    print("No valid tracks found in the playlist.")
                    input("Press Enter to continue...")
                    continue
                selected_device = curses.wrapper(select_device_curses)
                if selected_device is None:
                    print("No device selected. Returning to search.")
                    continue
                print(f"Selected Device: {selected_device['name']} ({selected_device['type']})")
                continue_playback = curses.wrapper(playback_curses, sp, selected_playlist, tracks, selected_device)
                if not continue_playback:
                    print("Exiting program.")
                    cleanup_playback(sp)
                    break
                print("Returning to search.")
            except ValueError as ve:
                clear_screen()
                print(f"\nError: {ve}")
                print("Playlist or device selection aborted due to terminal issue.")
                print("Returning to search.")
                input("Press Enter to continue...")
                continue
            except Exception as e:
                clear_screen()
                logging.error(f"Unhandled error during selection or playback: {e}", exc_info=True)
                print(f"\nError: Failed to select playlist or start playback: {e}")
                print("Returning to search.")
                input("Press Enter to continue...")
                continue
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Exiting.")
        cleanup_playback(sp)
        sys.exit(0)

if __name__ == "__main__":
    main()
