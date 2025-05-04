# --- START OF FILE spolistplay.py ---

import os
import sys
import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import curses
import time
import logging
import platform

logging.basicConfig(level=logging.WARN, format="%(asctime)s - %(levelname)s - %(message)s", stream=sys.stderr)

CLIENT_ID = os.environ.get("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("SPOTIPY_REDIRECT_URI", "https://127.0.0.0/")

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
    logging.info("Spotify authentication successful for user: " + user_profile.get('display_name', 'N/A'))
    print("Spotify authentication successful.")

except Exception as e:
    logging.error(f"Authentication failed: {e}", exc_info=True)
    print(f"Error: Spotify authentication failed. Please check your credentials, environment variables, and network connection.")
    print(f"Details: {e}")
    sys.exit(1)

def truncate_text(text, max_length):
    """Truncates text and adds '...' if it exceeds max_length."""
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
    """Clears the terminal screen. Uses curses if stdscr is provided, otherwise OS command."""
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
    """Clears the terminal using OS-specific commands and ANSI codes."""
    os.system("cls" if os.name == "nt" else "clear")
    print("\033[2J\033[H", end="", flush=True)


def getch():
    """Reads a single character input from the terminal (assuming raw mode is set externally)."""
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
         logging.error("EOFError encountered in getch. Input stream might be closed.", exc_info=True)
         return ''
    except Exception as e:
         logging.error(f"Error reading character in getch: {e}", exc_info=True)
         return ''


def get_search_query():
    """Gets a search query character by character from the user, managing raw mode."""
    fd = sys.stdin.fileno()
    original_termios_settings = None
    prompt = " search: "
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
            logging.error("\nFalling back to standard input (no character editing). Please press Enter after typing.")
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
    """Searches Spotify for playlists based on the query."""
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

def init_iceberg_colors():
    """No-op function as colors are disabled."""
    pass

def init_standard_colors():
    """No-op function as colors are disabled."""
    pass


def display_commands_popup(stdscr, commands, title="Commands"):
    """Displays commands in a temporary popup window (monochrome)."""
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
    popup_win.box()
    # popup_win.bkgd(' ', curses.color_pair(1)) # Color removed

    title_start_col = (popup_width - len(title)) // 2
    popup_win.addstr(1, title_start_col, title, curses.A_BOLD) # Bold title

    key_end_col_in_popup = 2 + max_key_width
    action_start_col_in_popup = key_end_col_in_popup + len(": ")

    for i, (key_str, action_str) in enumerate(commands):
        row = 2 + i
        key_start_col_in_popup = key_end_col_in_popup - len(key_str)
        popup_win.addstr(row, key_start_col_in_popup, key_str, curses.A_NORMAL) # Normal text
        popup_win.addstr(row, key_end_col_in_popup, ": ", curses.A_NORMAL) # Normal text
        popup_win.addstr(row, action_start_col_in_popup, action_str, curses.A_NORMAL) # Normal text


    stdscr.noutrefresh()
    popup_win.noutrefresh()
    curses.doupdate()

    # Use getch directly on the popup window to capture input
    popup_win.nodelay(False) # Wait for input
    popup_win.getch()
    popup_win.nodelay(True) # Restore non-blocking mode if needed

    stdscr.clear()
    # stdscr.bkgd(' ', curses.color_pair(1)) # Color removed
    stdscr.noutrefresh()
    curses.doupdate()
    del popup_win


def select_playlist_curses(stdscr, playlists):
    """Displays a paginated list of playlists using curses and allows user to select one (monochrome)."""
    # init_iceberg_colors() # Color initialization removed

    if not playlists:
        stdscr.addstr(0, 0, "No valid playlists found.", curses.A_BOLD) # Bold error
        stdscr.addstr(1, 0, "Press any key to return.", curses.A_NORMAL)
        stdscr.refresh()
        stdscr.getch()
        return None

    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(100)

    valid_playlists = [pl for pl in playlists if pl.get("tracks", {}).get("total") is not None]

    if not valid_playlists:
         stdscr.addstr(0, 0, "No valid playlists with track counts found.", curses.A_BOLD) # Bold error
         stdscr.addstr(1, 0, "Press any key to return.", curses.A_NORMAL)
         stdscr.refresh()
         stdscr.getch()
         return None

    sorted_playlists = sorted(valid_playlists, key=lambda p: p.get("tracks", {}).get("total", 0), reverse=True)

    items_per_page = 10
    total_items = len(sorted_playlists)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    current_page = 1
    selected_idx_in_page = 0
    number_input = ""

    min_required_y = 1 + 1 + items_per_page + 3
    min_required_x = 40

    max_y, max_x = stdscr.getmaxyx()
    if max_y < min_required_y or max_x < min_required_x:
        raise ValueError(f"Terminal too small for playlist selection. Needs at least {min_required_y}x{min_required_x}. Current size: {max_y}x{max_x}")


    running = True
    while running:
        max_y, max_x = stdscr.getmaxyx()
        if max_y < min_required_y or max_x < min_required_x:
             raise ValueError(f"Terminal resized too small for playlist selection. Needs at least {min_required_y}x{min_required_x}. Current size: {max_y}x{max_x}")

        stdscr.clear()
        # stdscr.bkgd(' ', curses.color_pair(1)) # Color removed

        usable_x = max_x - 2

        stdscr.addstr(1, 1, "- Playlists", curses.A_BOLD) # Bold header

        start_idx_overall = (current_page - 1) * items_per_page
        end_idx_overall = min(start_idx_overall + items_per_page, total_items)

        if selected_idx_in_page >= (end_idx_overall - start_idx_overall) and (end_idx_overall - start_idx_overall) > 0:
            selected_idx_in_page = (end_idx_overall - start_idx_overall) - 1
        elif (end_idx_overall - start_idx_overall) == 0:
             selected_idx_in_page = 0


        for i in range(start_idx_overall, end_idx_overall):
            pl = sorted_playlists[i]
            track_count = pl.get("tracks", {}).get("total", "N/A")
            display_idx = i + 1
            name = truncate_text(pl['name'], usable_x - 25)
            owner = truncate_text(pl['owner']['display_name'], 15)

            display_line = f"{display_idx}. {name} ({track_count} tracks) - {owner}"
            display_line = truncate_text(display_line, usable_x)

            row = 3 + (i - start_idx_overall)

            if row < max_y - 3:
                 if (i - start_idx_overall) == selected_idx_in_page:
                     stdscr.addstr(row, 1, display_line, curses.A_REVERSE) # Reverse for selection
                 else:
                     stdscr.addstr(row, 1, display_line, curses.A_NORMAL) # Normal text

        status_line = f"Page {current_page}/{total_pages} - Total: {total_items} playlists"
        stdscr.addstr(max_y - 1, 1, truncate_text(status_line, usable_x), curses.A_NORMAL) # Normal text

        input_prompt = "Select #: "
        input_row = max_y - 3
        if input_row >= 0:
            stdscr.addstr(input_row, 1, input_prompt, curses.A_NORMAL) # Normal text
            stdscr.addstr(input_row, 1 + len(input_prompt), number_input)
            stdscr.clrtoeol()

        commands_hint_line = "Press '?' for commands."
        stdscr.addstr(max_y - 2, 1, truncate_text(commands_hint_line, usable_x), curses.A_NORMAL) # Normal text


        stdscr.noutrefresh()
        curses.doupdate()

        key = stdscr.getch()

        if key != -1:
            if ord('0') <= key <= ord('9'):
                number_input += chr(key)
            elif key in (ord('\n'), ord('\r'), curses.KEY_ENTER):
                if number_input:
                    try:
                        selected_num = int(number_input)
                        if 1 <= selected_num <= total_items:
                            running = False
                            return sorted_playlists[selected_num - 1]
                        else:
                            error_row = max_y - 3
                            if error_row >= 0:
                                stdscr.addstr(error_row, 1 + len(input_prompt) + len(number_input), " Invalid!", curses.A_BOLD) # Bold error
                                stdscr.noutrefresh()
                                curses.doupdate()
                                time.sleep(0.5)
                            number_input = ""
                    except ValueError:
                         number_input = ""

                else:
                     selected_overall_idx = start_idx_overall + selected_idx_in_page
                     if 0 <= selected_overall_idx < total_items:
                         running = False
                         return sorted_playlists[selected_overall_idx]


            elif key in (8, 127, curses.KEY_BACKSPACE):
                 if number_input:
                      number_input = number_input[:-1]
                 else:
                      pass

            elif number_input:
                 pass

            elif key == ord('?'):
                 commands_list = [
                     ("Arrows/jk/lh", "Navigate/Page"),
                     ("#", "Direct Select"),
                     ("Enter", "Select Item"),
                     ("ESC", "Back to Search"),
                 ]
                 display_commands_popup(stdscr, commands_list, "Playlist Commands")
                 # Force redraw after popup closes
                 stdscr.clear()
                 # stdscr.bkgd(' ') # Ensure background is cleared
                 stdscr.touchwin()


            elif key in (curses.KEY_UP, ord('k'), ord('K')):
                 if selected_idx_in_page > 0:
                      selected_idx_in_page -= 1
                 elif current_page > 1:
                      current_page -= 1
                      prev_page_items_count = min(items_per_page, total_items - ((current_page - 1) * items_per_page))
                      selected_idx_in_page = max(0, prev_page_items_count - 1)
                 number_input = ""
                 stdscr.clear()
                 # stdscr.bkgd(' ', curses.color_pair(1)) # Color removed
                 stdscr.touchwin()


            elif key in (curses.KEY_DOWN, ord('j'), ord('J')):
                 start_idx_overall_current_page = (current_page - 1) * items_per_page
                 current_page_items_count = min(items_per_page, total_items - start_idx_overall_current_page)
                 if selected_idx_in_page < current_page_items_count - 1:
                      selected_idx_in_page += 1
                 elif current_page < total_pages:
                      current_page += 1
                      selected_idx_in_page = 0
                 number_input = ""
                 stdscr.clear()
                 # stdscr.bkgd(' ', curses.color_pair(1)) # Color removed
                 stdscr.touchwin()

            elif key in (curses.KEY_LEFT, ord('h'), ord('H')):
                if current_page > 1:
                    current_page -= 1
                    selected_idx_in_page = 0
                number_input = ""
                stdscr.clear()
                # stdscr.bkgd(' ', curses.color_pair(1)) # Color removed
                stdscr.touchwin()


            elif key in (curses.KEY_RIGHT, ord('l'), ord('L')):
                if current_page < total_pages:
                    current_page += 1
                    selected_idx_in_page = 0
                number_input = ""
                stdscr.clear()
                # stdscr.bkgd(' ', curses.color_pair(1)) # Color removed
                stdscr.touchwin()


            elif key == 27:
                running = False
                return None


    return None


def get_all_playlist_tracks(playlist_id):
    """Fetches all tracks from a given playlist ID using pagination."""
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
                    logging.warning(f"Attempt {attempt} of {retry_limit}: Spotify API error retrieving tracks: {se}", exc_info=True)
                    if attempt < retry_limit:
                        print(f"Retrying track fetch ({attempt}/{retry_limit})...")
                        time.sleep(2)
                    else:
                        logging.error("Max retry attempts reached for retrieving tracks.")
                        print(f"Failed to fetch tracks after multiple retries: {se}")
                        return tracks
                except Exception as e:
                    attempt += 1
                    logging.warning(f"Attempt {attempt} of {retry_limit}: Unexpected error retrieving tracks: {e}", exc_info=True)
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
            # Print progress indicator without newline
            print(".", end="", flush=True)
            # sys.stdout.flush() # Already flushed by end=""

    except Exception as e:
        logging.error(f"Critical error during track fetching loop: {e}", exc_info=True)
        print(f"A critical error occurred during track fetching: {e}")
        return tracks

    print(f"\nFinished fetching tracks. Retrieved {len(tracks)} valid tracks.")
    logging.info(f"Finished fetching tracks. Retrieved {len(tracks)} valid tracks from playlist {playlist_id}.")
    return tracks


def select_device_curses(stdscr):
    """Displays available devices using curses and allows user to select one (monochrome)."""
    # init_iceberg_colors() # Color initialization removed

    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(100)

    min_required_y = 6
    min_required_x = 40

    running = True
    selected_idx = 0
    devices = []
    number_input = ""
    display_offset_device = 0

    try:
        devices = sp.devices()["devices"]
        if not devices:
            max_y, max_x = stdscr.getmaxyx()
            stdscr.clear()
            # stdscr.bkgd(' ', curses.color_pair(1)) # Color removed
            stdscr.addstr(1, 1, "- Device", curses.A_BOLD) # Bold header
            stdscr.addstr(3, 1, "No spotify devices found.", curses.A_BOLD) # Bold error
            stdscr.addstr(4, 1, "Make sure the Spotify application is running and logged in.", curses.A_NORMAL)
            stdscr.addstr(max_y - 1, 1, "Press any key to return.", curses.A_NORMAL)
            stdscr.noutrefresh()
            curses.doupdate()
            stdscr.nodelay(False) # Wait for key press
            stdscr.getch()
            stdscr.nodelay(True) # Restore non-blocking
            return None
    except Exception as e:
        logging.error(f"Error fetching devices for curses selection: {e}", exc_info=True)
        max_y, max_x = stdscr.getmaxyx()
        stdscr.clear()
        # stdscr.bkgd(' ', curses.color_pair(1)) # Color removed
        stdscr.addstr(1, 1, "- Device", curses.A_BOLD) # Bold header
        stdscr.addstr(3, 1, "Error fetching devices.", curses.A_BOLD) # Bold error
        stdscr.addstr(4, 1, truncate_text(str(e), max_x - 2), curses.A_BOLD) # Bold error detail
        stdscr.addstr(max_y - 1, 1, "Press any key to return.", curses.A_NORMAL)
        stdscr.noutrefresh()
        curses.doupdate()
        stdscr.nodelay(False) # Wait for key press
        stdscr.getch()
        stdscr.nodelay(True) # Restore non-blocking
        return None

    total_items = len(devices)
    if total_items == 0:
        return None

    if selected_idx >= total_items:
         selected_idx = total_items - 1


    while running:
        max_y, max_x = stdscr.getmaxyx()
        if max_y < min_required_y or max_x < min_required_x:
             raise ValueError(f"Terminal resized too small for device selection. Needs at least {min_required_y}x{min_required_x}. Current size: {max_y}x{max_x}")

        stdscr.clear()
        # stdscr.bkgd(' ', curses.color_pair(1)) # Color removed

        usable_x = max_x - 2

        stdscr.addstr(1, 1, "- Device", curses.A_BOLD) # Bold header

        display_start_row = 3
        max_display_items = max_y - display_start_row - 3

        if max_display_items > 0:
            if selected_idx < display_offset_device:
                 display_offset_device = selected_idx
            elif selected_idx >= display_offset_device + max_display_items:
                 display_offset_device = selected_idx - max_display_items + 1

            display_offset_device = max(0, display_offset_device)
            display_offset_device = min(display_offset_device, max(0, total_items - max_display_items))
        else:
             display_offset_device = 0

        for i in range(display_offset_device, min(display_offset_device + max_display_items, total_items)):
            device = devices[i]
            active_str = "[Active]" if device["is_active"] else ""
            display_idx = i + 1

            display_line = f"{display_idx}. {device['name']} ({device['type']}) {active_str}"
            display_line = truncate_text(display_line, usable_x)

            row = display_start_row + (i - display_offset_device)

            if row < max_y - 3: # Changed from max_y - 2 to max_y - 3 to avoid collision with input line
                 if i == selected_idx:
                     stdscr.addstr(row, 1, display_line, curses.A_REVERSE) # Reverse for selection
                 else:
                     stdscr.addstr(row, 1, display_line, curses.A_NORMAL) # Normal text


        commands_hint_line = "Press '?' for commands."
        stdscr.addstr(max_y - 1, 1, truncate_text(commands_hint_line, usable_x), curses.A_NORMAL) # Normal text

        input_prompt = "Select #: "
        input_row = max_y - 2 # Changed from max_y - 3 to max_y - 2
        if input_row >= 0:
            stdscr.addstr(input_row, 1, input_prompt, curses.A_NORMAL) # Normal text
            stdscr.addstr(input_row, 1 + len(input_prompt), number_input)
            stdscr.clrtoeol()


        stdscr.noutrefresh()
        curses.doupdate()

        key = stdscr.getch()

        if key != -1:
            if ord('0') <= key <= ord('9'):
                number_input += chr(key)
            elif key in (ord('\n'), ord('\r'), curses.KEY_ENTER):
                if number_input:
                    try:
                        selected_num = int(number_input)
                        if 1 <= selected_num <= total_items:
                            running = False
                            return devices[selected_num - 1]
                        else:
                            error_row = max_y - 2
                            if error_row >= 0:
                                stdscr.addstr(error_row, 1 + len(input_prompt) + len(number_input), " Invalid!", curses.A_BOLD) # Bold error
                                stdscr.noutrefresh()
                                curses.doupdate()
                                time.sleep(0.5)
                            number_input = ""
                    except ValueError:
                         number_input = ""

                else:
                     if 0 <= selected_idx < total_items:
                         running = False
                         return devices[selected_idx]


            elif key in (8, 127, curses.KEY_BACKSPACE):
                 if number_input:
                      number_input = number_input[:-1]
                 else:
                      pass

            elif number_input:
                 pass

            elif key == ord('?'):
                 commands_list = [
                     ("Arrows/jk", "Navigate List"),
                     ("lh", "Scroll List"),
                     ("#", "Direct Select"),
                     ("Enter", "Select Item"),
                     ("q/ESC", "Back to Search"),
                 ]
                 display_commands_popup(stdscr, commands_list, "Device Commands")
                 # Force redraw after popup closes
                 stdscr.clear()
                 # stdscr.bkgd(' ') # Ensure background is cleared
                 stdscr.touchwin()


            elif key in (curses.KEY_UP, ord('k'), ord('K')):
                 if selected_idx > 0:
                      selected_idx -= 1
                 number_input = ""
                 stdscr.clear()
                 # stdscr.bkgd(' ', curses.color_pair(1)) # Color removed
                 stdscr.touchwin()

            elif key in (curses.KEY_DOWN, ord('j'), ord('J')):
                 if selected_idx < total_items - 1:
                      selected_idx += 1
                 number_input = ""
                 stdscr.clear()
                 # stdscr.bkgd(' ', curses.color_pair(1)) # Color removed
                 stdscr.touchwin()

            elif key in (curses.KEY_LEFT, ord('h'), ord('H')):
                 if display_offset_device > 0:
                      scroll_amount = max_display_items if max_display_items > 0 else 1
                      display_offset_device = max(0, display_offset_device - scroll_amount)
                      selected_idx = display_offset_device
                      number_input = ""
                      stdscr.clear()
                      # stdscr.bkgd(' ', curses.color_pair(1)) # Color removed
                      stdscr.touchwin()


            elif key in (curses.KEY_RIGHT, ord('l'), ord('L')):
                 if max_display_items > 0 and display_offset_device + max_display_items < total_items:
                      scroll_amount = max_display_items if max_display_items > 0 else 1
                      display_offset_device = min(total_items - max_display_items, display_offset_device + scroll_amount)
                      selected_idx = display_offset_device
                      number_input = ""
                      stdscr.clear()
                      # stdscr.bkgd(' ', curses.color_pair(1)) # Color removed
                      stdscr.touchwin()

            elif key in (ord('q'), ord('Q'), 27):
                running = False
                return None


    return None


def playback_curses(stdscr, sp_client, playlist_info, tracks, selected_device):
    """Runs the curses UI for controlling playback (monochrome). Returns False on X key exit, True otherwise."""
    device_id = selected_device['id']
    device_name = selected_device.get('name', 'Unknown Device')
    device_supports_volume = selected_device.get('supports_volume', False)

    MIN_PLAYBACK_TERM_Y = 10
    MIN_PLAYBACK_TERM_X = 40

    max_y, max_x = stdscr.getmaxyx()
    if max_y < MIN_PLAYBACK_TERM_Y or max_x < MIN_PLAYBACK_TERM_X:
        raise ValueError(f"Terminal too small for playback UI. Needs at least {MIN_PLAYBACK_TERM_Y}x{MIN_PLAYBACK_TERM_X}. Current size: {max_y}x{max_x}")

    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(100)

    # curses.start_color() # Color removed
    # curses.use_default_colors() # Color removed
    # init_iceberg_colors() # Color removed

    padding = 1
    header_h = 1
    min_body_h_required = 6

    usable_y = max_y - (padding * 2)
    usable_x = max_x - (padding * 2)
    body_h = usable_y - header_h - 1

    min_required_y = header_h + 1 + min_body_h_required + 1 + padding
    if max_y < min_required_y or body_h < min_body_h_required:
         raise ValueError(f"Terminal height too small for layout. Needs at least {min_required_y} lines total. Current size: {max_y}x{max_x}")

    try:
        header_win = curses.newwin(header_h, usable_x, padding, padding)
        body_win = curses.newwin(body_h, usable_x, padding + header_h + 1, padding)
    except curses.error as e:
        logging.error(f"Failed to create curses windows: {e}", exc_info=True)
        raise ValueError(f"Failed to initialize UI windows: {e}") from e

    # stdscr.bkgd(' ', curses.color_pair(1)) # Color removed
    stdscr.clear()
    stdscr.refresh()

    playlist_uri = playlist_info.get('uri')
    first_track_uri = None
    if tracks and tracks[0] and tracks[0].get("id"):
         first_track_uri = f"spotify:track:{tracks[0]['id']}"


    if not playlist_uri or not first_track_uri:
        body_win.addstr(0, 0, "Error: Cannot start playback - missing playlist or track URI.", curses.A_BOLD) # Bold error
        body_win.addstr(1, 0, "Ensure playlist has valid tracks.", curses.A_BOLD) # Bold error
        body_win.noutrefresh()
        stdscr.addstr(max_y - padding -1, padding, "Press any key to return.", curses.A_NORMAL)
        stdscr.noutrefresh()
        curses.doupdate()
        stdscr.nodelay(False); stdscr.getch(); stdscr.nodelay(True) # Wait for key press
        try:
            if 'header_win' in locals() and header_win: header_win.clear(); del header_win
            if 'body_win' in locals() and body_win: body_win.clear(); del body_win
        except NameError: pass
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
        body_win.addstr(0, 0, "Failed to start playback (Spotify API Error).", curses.A_BOLD) # Bold error
        body_win.addstr(1, 0, truncate_text(str(e), usable_x -1), curses.A_BOLD) # Bold error detail
        body_win.addstr(2, 0, "Check device status, Premium account, or playlist validity.", curses.A_NORMAL)
        body_win.noutrefresh()
        stdscr.addstr(max_y - padding -1, padding, "Press any key to return.", curses.A_NORMAL)
        stdscr.noutrefresh()
        curses.doupdate()
        stdscr.nodelay(False); stdscr.getch(); stdscr.nodelay(True) # Wait for key press
        try:
            if 'header_win' in locals() and header_win: header_win.clear(); del header_win
            if 'body_win' in locals() and body_win: body_win.clear(); del body_win
        except NameError: pass
        stdscr.clear()
        stdscr.refresh()
        return True
    except Exception as e:
        logging.error(f"Unexpected error starting playback: {e}", exc_info=True)
        body_win.addstr(0, 0, "Failed to start playback (Unexpected Error).", curses.A_BOLD) # Bold error
        body_win.addstr(1, 0, truncate_text(str(e), usable_x -1), curses.A_BOLD) # Bold error detail
        body_win.addstr(2, 0, "Note: Playback control requires a Spotify Premium account.", curses.A_NORMAL)
        body_win.noutrefresh()
        stdscr.addstr(max_y - padding -1, padding, "Press any key to return.", curses.A_NORMAL)
        stdscr.noutrefresh()
        curses.doupdate()
        stdscr.nodelay(False); stdscr.getch(); stdscr.nodelay(True) # Wait for key press
        try:
            if 'header_win' in locals() and header_win: header_win.clear(); del header_win
            if 'body_win' in locals() and body_win: body_win.clear(); del body_win
        except NameError: pass
        stdscr.clear()
        stdscr.refresh()
        return True


    cached_playback_state = None
    last_api_error = None

    needs_redraw = True
    last_poll_time = 0
    POLLING_INTERVAL = 2.0
    current_volume_percent = None
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
                  logging.debug(f"Could not get initial volume from devices list: {e}")


    except Exception as e:
         logging.debug(f"Could not get initial playback state or volume: {e}")


    running = True
    exit_program = False

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
                    raise ValueError(f"Terminal resized too small. Needs at least {min_required_y} lines total. Current size: {max_y}x{max_x}")

                try:
                    if 'header_win' in locals() and header_win: header_win.clear(); del header_win
                    if 'body_win' in locals() and body_win: body_win.clear(); del body_win
                except NameError: pass
                except Exception as e: logging.warning(f"Error deleting old windows during resize: {e}", exc_info=True)

                try:
                    header_win = curses.newwin(header_h, usable_x, padding, padding)
                    body_win = curses.newwin(body_h, usable_x, padding + header_h + 1, padding)
                except curses.error as e:
                    logging.error(f"Failed to create curses windows: {e}", exc_info=True)
                    raise ValueError(f"Failed to resize UI windows: {e}") from e

                stdscr.clear()
                # stdscr.bkgd(' ', curses.color_pair(1)) # Color removed
                stdscr.touchwin()
                needs_redraw = True

            current_time = time.time()
            poll_needed = (current_time - last_poll_time >= POLLING_INTERVAL) or needs_redraw

            if poll_needed:
                try:
                    new_playback_state = sp_client.current_playback(market='from_token')
                    last_poll_time = current_time

                    state_changed = (new_playback_state != cached_playback_state)
                    if state_changed:
                        needs_redraw = True
                        cached_playback_state = new_playback_state
                        last_api_error = None

                        if cached_playback_state and cached_playback_state.get("device", {}).get("id") == device_id and cached_playback_state.get("device", {}).get("supports_volume"):
                            new_volume = cached_playback_state["device"].get("volume_percent")
                            if new_volume is not None and new_volume != current_volume_percent:
                                logging.debug(f"Volume updated via API state: {new_volume}%")
                                current_volume_percent = new_volume


                except Exception as e:
                    logging.error(f"Error fetching playback state: {e}", exc_info=True)
                    last_api_error = f"API Error: {truncate_text(str(e), usable_x - 15)}"
                    needs_redraw = True

            key = stdscr.getch()

            if key != -1:

                if key == ord('?'):
                    commands_list = [
                        ("Enter/P", "play/pause"),
                        ("h/Left Arrow", "prev track"),
                        ("l/Right Arrow", "next track"),
                        ("j/Down Arrow", "volume down"),
                        ("k/Up Arrow", "volume up"),
                        ("S", "shuffle toggle"),
                        ("ESC/q", "back to search"),
                        ("X", "exit program"),
                    ]
                    display_commands_popup(stdscr, commands_list, "Playback Commands")
                    needs_redraw = True
                    # Force redraw after popup closes
                    stdscr.clear()
                    # stdscr.bkgd(' ') # Ensure background is cleared
                    stdscr.touchwin()
                    if 'header_win' in locals() and header_win: header_win.touchwin()
                    if 'body_win' in locals() and body_win: body_win.touchwin()


                elif key in (ord("q"), ord("Q"), 27):
                    logging.info("Exiting playback UI via q, Q, or ESC. Attempting to pause playback.")
                    try:
                        pause_device_id = cached_playback_state.get("device", {}).get("id") if cached_playback_state and cached_playback_state.get("device") else selected_device['id']
                        if pause_device_id:
                             if cached_playback_state is None or cached_playback_state.get("is_playing", True):
                                 sp_client.pause_playback(device_id=pause_device_id)
                                 logging.info(f"Playback paused on device {pause_device_id} on UI exit.")
                             else:
                                 logging.debug("Playback was already paused, no need to pause on UI exit.")
                        else:
                             logging.warning("Could not determine device to pause on UI exit.")
                    except Exception as e:
                        logging.warning(f"Could not pause playback on UI exit: {e}")

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

                         last_poll_time = 0; cached_playback_state = None; needs_redraw = True; last_api_error = None

                     except Exception as e:
                         logging.error(f"Error toggling playback: {e}", exc_info=True)
                         last_api_error = f"Cmd Error: {truncate_text(str(e), usable_x - 15)}"
                         needs_redraw = True


                elif key in (curses.KEY_RIGHT, ord('l'), ord('L')):
                    try:
                        target_device_id = cached_playback_state.get("device", {}).get("id") if cached_playback_state and cached_playback_state.get("device") else selected_device['id']
                        sp_client.next_track(device_id=target_device_id)
                        logging.info("Skipped to next track.")
                        last_poll_time = 0; cached_playback_state = None; needs_redraw = True; last_api_error = None
                    except Exception as e:
                        logging.error(f"Error skipping to next track: {e}", exc_info=True)
                        last_api_error = f"Cmd Error: {truncate_text(str(e), usable_x - 15)}"
                        needs_redraw = True

                elif key in (curses.KEY_LEFT, ord('h'), ord('H')):
                    try:
                        target_device_id = cached_playback_state.get("device", {}).get("id") if cached_playback_state and cached_playback_state.get("device") else selected_device['id']
                        sp_client.previous_track(device_id=target_device_id)
                        logging.info("Skipped to previous track.")
                        last_poll_time = 0; cached_playback_state = None; needs_redraw = True; last_api_error = None
                    except Exception as e:
                        logging.error(f"Error returning to previous track: {e}", exc_info=True)
                        last_api_error = f"Cmd Error: {truncate_text(str(e), usable_x - 15)}"
                        needs_redraw = True

                elif key in (curses.KEY_UP, ord('k'), ord('K')):
                     if device_supports_volume:
                          if current_volume_percent is None:
                               logging.debug("Volume up received but current_volume_percent is None, forcing poll.")
                               last_poll_time = 0; needs_redraw = True
                          else:
                              try:
                                  new_volume = min(100, current_volume_percent + 5)
                                  sp_client.volume(new_volume, device_id=device_id)
                                  logging.info(f"Increased volume to {new_volume}%.")
                                  current_volume_percent = new_volume
                                  last_poll_time = 0; needs_redraw = True; last_api_error = None
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
                               last_poll_time = 0; needs_redraw = True
                          else:
                              try:
                                  new_volume = max(0, current_volume_percent - 5)
                                  sp_client.volume(new_volume, device_id=device_id)
                                  logging.info(f"Decreased volume to {new_volume}%.")
                                  current_volume_percent = new_volume
                                  last_poll_time = 0; needs_redraw = True; last_api_error = None
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
                        time.sleep(0.1); last_poll_time = 0; cached_playback_state = None; needs_redraw = True; last_api_error = None
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
                         logging.warning(f"Could not pause playback on X key exit: {e}")

                     running = False
                     exit_program = True


            if needs_redraw:
                header_win.clear(); body_win.clear()

                header = "- Spotify Playlist Player"
                header_win.addstr(0, 0, truncate_text(header, usable_x), curses.A_BOLD) # Bold header
                header_win.noutrefresh()

                # Store label, content, row
                item_display_data = []

                if playlist_info:
                    item_display_data.append((
                        "Playlist:",
                        f"{playlist_info['name']} by {playlist_info['owner']['display_name']}",
                        0
                    ))

                item_display_data.append((
                    "Device:",
                    device_name,
                    1
                ))

                display_playback_state = cached_playback_state if cached_playback_state else {}
                display_track_info = display_playback_state.get("item")

                if display_track_info:
                    item = display_track_info
                    track_name = item.get("name", "Unknown Track")
                    artists = ", ".join([a.get("name", "Unknown Artist") for a in item.get("artists", [])]) if item.get("artists") else "Unknown Artist"
                    album = item.get("album", {}).get("name", "Unknown Album")
                    release_date = item.get("album", {}).get("release_date", "----")
                    album_year = release_date[:4] if release_date and release_date[:4].isdigit() else "----"
                    album_line = f"{album} ({album_year})"

                    item_display_data.extend([
                        ("Track:", track_name, 3),
                        ("Artist:", artists, 4),
                        ("Album:", album_line, 5),
                    ])

                    status_row_in_body = 7


                else:
                    waiting_message_start_col_in_body = 0
                    body_win.addstr(3, waiting_message_start_col_in_body, truncate_text("Waiting for playback info...", usable_x - waiting_message_start_col_in_body), curses.A_NORMAL)
                    if cached_playback_state is None:
                        body_win.addstr(4, waiting_message_start_col_in_body, truncate_text("Attempting to fetch playback state...", usable_x - waiting_message_start_col_in_body), curses.A_NORMAL)
                        body_win.addstr(5, waiting_message_start_col_in_body, truncate_text("Ensure a device is active and playing.", usable_x - waiting_message_start_col_in_body), curses.A_NORMAL)
                    else:
                        body_win.addstr(4, waiting_message_start_col_in_body, truncate_text("Playback currently stopped or no track loaded.", usable_x - waiting_message_start_col_in_body), curses.A_NORMAL)
                        current_active_device_name = display_playback_state.get("device", {}).get("name")
                        if current_active_device_name:
                             body_win.addstr(5, waiting_message_start_col_in_body, truncate_text(f"Currently Active Device: {current_active_device_name}", usable_x - waiting_message_start_col_in_body), curses.A_NORMAL)

                    status_row_in_body = 7


                labels = [label for label, _, _ in item_display_data]
                max_label_len = max(len(label) for label in labels) if labels else 0

                content_start_col_in_body = max_label_len + 2
                max_content_start_col = usable_x // 3
                content_start_col_in_body = min(content_start_col_in_body, max_content_start_col)
                if content_start_col_in_body < 1: content_start_col_in_body = 1


                for label, content, row_in_body in item_display_data:
                    if row_in_body < body_h:
                        label_col_end = content_start_col_in_body - 1
                        label_start_col_in_body = label_col_end - len(label)
                        label_start_col_in_body = max(0, label_start_col_in_body)


                        body_win.addstr(row_in_body, label_start_col_in_body, label, curses.A_NORMAL) # Normal label

                        content_max_width = usable_x - content_start_col_in_body - 1
                        if content_max_width < 0: content_max_width = 0

                        # Use A_BOLD for Track name for emphasis
                        attr = curses.A_BOLD if label == "Track:" else curses.A_NORMAL
                        body_win.addstr(row_in_body, content_start_col_in_body, truncate_text(content, content_max_width), attr)


                separator_row_in_body = 2
                if separator_row_in_body < body_h:
                     body_win.hline(separator_row_in_body, 0, curses.ACS_HLINE, usable_x)


                display_is_playing = display_playback_state.get("is_playing", False)
                display_shuffle_state = display_playback_state.get("shuffle_state", False)
                display_volume_percent = cached_playback_state.get("device", {}).get("volume_percent") if cached_playback_state and cached_playback_state.get("device", {}).get("supports_volume") else None

                if status_row_in_body < body_h:
                    play_status = "▶ Playing" if display_is_playing else "⏸ Paused"
                    # Use A_BOLD for Playing status for emphasis
                    status_attr = curses.A_BOLD if display_is_playing else curses.A_NORMAL
                    body_win.addstr(status_row_in_body, 0, play_status, status_attr)

                    shuffle_text = "Shuffle: On" if display_shuffle_state else "Shuffle:Off"
                    # Use A_BOLD for Shuffle On for emphasis
                    shuffle_attr = curses.A_BOLD if display_shuffle_state else curses.A_NORMAL
                    shuffle_col_in_body = len(play_status) + 3
                    if shuffle_col_in_body < usable_x:
                         body_win.addstr(status_row_in_body, shuffle_col_in_body, truncate_text(shuffle_text, usable_x - shuffle_col_in_body - 1), shuffle_attr)

                    if device_supports_volume:
                         volume_text = f"Volume: {display_volume_percent}%" if display_volume_percent is not None else "Volume: N/A"
                         volume_col_in_body = shuffle_col_in_body + len(truncate_text(shuffle_text, usable_x - shuffle_col_in_body - 1)) + 3
                         if volume_col_in_body < usable_x:
                              body_win.addstr(status_row_in_body, volume_col_in_body, truncate_text(volume_text, usable_x - volume_col_in_body - 1), curses.A_NORMAL)

                # Removed redundant 'else' block for when status_row_in_body >= body_h,
                # as the previous 'else' block for 'if display_track_info' already covers this.

                error_row_in_body = body_h - 1
                min_error_row_needed_in_body = status_row_in_body + 1

                if error_row_in_body >= max(0, min_error_row_needed_in_body) and error_row_in_body >= 0:
                     if last_api_error:
                          body_win.clrtoeol()
                          # Use A_REVERSE for errors
                          body_win.addstr(error_row_in_body, 0, truncate_text(last_api_error, usable_x - 1), curses.A_REVERSE)
                     else:
                          body_win.move(error_row_in_body, 0)
                          body_win.clrtoeol()


                body_win.noutrefresh()

                commands_hint_line = "Press '?' for commands."
                stdscr.addstr(max_y - 1, padding, truncate_text(commands_hint_line, max_x - 2*padding), curses.A_NORMAL)
                stdscr.clrtoeol()


                curses.doupdate()

                needs_redraw = False

    except Exception as e:
         logging.error(f"Unhandled error inside playback_curses: {e}", exc_info=True)
         raise

    finally:
        logging.debug("Cleaning up windows in playback_curses finally block")
        try:
            if 'header_win' in locals() and header_win: header_win.clear(); del header_win
            if 'body_win' in locals() and body_win: body_win.clear(); del body_win
        except NameError: pass
        except Exception as e: logging.warning(f"Error cleaning up windows in playback_curses finally: {e}", exc_info=True)

        try:
             stdscr.clear()
             stdscr.refresh()
             logging.debug("stdscr cleared and refreshed in playback_curses finally")
        except Exception as e:
             logging.warning(f"Failed to clear/refresh stdscr in playback_curses finally: {e}", exc_info=True)

    return not exit_program


def cleanup_playback(sp_client):
    """Attempts to pause the current playback."""
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
                 print(" see you :)")
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

            selected_playlist = None # Initialize outside try block
            try:
                 selected_playlist = curses.wrapper(select_playlist_curses, playlists)

                 if selected_playlist is None:
                      clear_screen() # Clear curses screen before printing
                      print("Returning to search.")
                      continue

                 clear_screen() # Clear curses screen before printing
                 print(f"Selected Playlist: {selected_playlist['name']} by {selected_playlist['owner']['display_name']}")

            except ValueError as ve:
                 clear_screen()
                 print(f"\nError: {ve}")
                 print("Playlist selection aborted due to terminal issue.")
                 print("Returning to search.")
                 input("Press Enter to continue...")
                 continue
            except Exception as e:
                 clear_screen()
                 logging.error(f"Unhandled error during playlist selection (curses): {e}", exc_info=True)
                 print(f"\nAn unexpected error occurred during playlist selection: {e}")
                 print("Returning to search.")
                 input("Press Enter to continue...")
                 continue


            tracks = get_all_playlist_tracks(selected_playlist["id"])

            if not tracks:
                print("No playable tracks found in the selected playlist.")
                input("Press Enter to continue...")
                continue

            print(f"Successfully fetched {len(tracks)} playable tracks.")

            selected_device = None # Initialize outside try block
            try:
                 selected_device = curses.wrapper(select_device_curses)

                 if selected_device is None:
                      clear_screen() # Clear curses screen before printing
                      print("Returning to search.")
                      continue

                 clear_screen() # Clear curses screen before printing
                 print(f"Selected Device: {selected_device.get('name', 'Unknown Device')}")

            except ValueError as ve:
                 clear_screen()
                 print(f"\nError: {ve}")
                 print("Device selection aborted due to terminal issue.")
                 print("Returning to search.")
                 input("Press Enter to continue...")
                 continue
            except Exception as e:
                 clear_screen()
                 logging.error(f"Unhandled error during device selection (curses): {e}", exc_info=True)
                 print(f"\nAn unexpected error occurred during device selection: {e}")
                 print("Returning to search.")
                 input("Press Enter to continue...")
                 continue


            try:
                continue_main_loop = curses.wrapper(playback_curses, sp, selected_playlist, tracks, selected_device)

                if not continue_main_loop:
                     logging.info("Received signal to exit program from playback UI.")
                     clear_screen() # Clear curses screen before printing
                     print("Exiting program.")
                     break

                logging.info("Playback UI exited normally (ESC/q/Q). Returning to search.")
                clear_screen() # Clear curses screen before next search prompt


            except ValueError as ve:
                # Need to ensure curses is ended before printing
                # curses.wrapper should handle this, but explicit clear helps
                clear_screen()
                print(f"\nError: {ve}")
                print("Playback session aborted due to terminal issue.")
                print("Press Enter to continue...")
                try: input()
                except (KeyboardInterrupt, EOFError): pass
                clear_screen() # Clear screen before next search prompt

            except Exception as e:
                # Need to ensure curses is ended before printing
                clear_screen()
                logging.error(f"Unhandled error during playback (curses mode) caught by wrapper: {e}", exc_info=True)
                print(f"\nAn unexpected error occurred during playback: {e}")
                print("Exiting playback mode.")
                print("Press Enter to continue...")
                try: input()
                except (KeyboardInterrupt, EOFError): pass
                clear_screen() # Clear screen before next search prompt


    except KeyboardInterrupt:
        clear_screen() # Clear screen before printing exit messages
        print("\nCtrl+C detected.")
        cleanup_playback(sp)
        print("Exiting program.")
        sys.exit(0)

    except Exception as e:
        clear_screen() # Clear screen before printing exit messages
        logging.error(f"Unhandled critical error in main loop: {e}", exc_info=True)
        print(f"\nAn unexpected critical error occurred: {e}")
        cleanup_playback(sp)
        print("Exiting.")
        sys.exit(1)

if __name__ == "__main__":
    main()

# --- END OF FILE spolistplay.py ---
