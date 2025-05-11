# spolistplay

[Japanese Version (日本語版はこちら)](README_jp.md)

![spolistplay demo gif](https://github.com/user-attachments/assets/26c22414-2cb2-4e26-a5db-219ecaf04398)

A terminal-based Spotify playlist player using the `curses` library. Search for playlists, select one, choose an active Spotify device, and control playback directly from your terminal.

Git URL: https://github.com/256x/spolistplay

**❗ Important Note: Spotify Premium Required for Playback Control ❗**

Full playback control features (starting/pausing playback, skipping tracks, volume control, shuffle toggle) **require a Spotify Premium account**. While the script might allow searching and listing playlists with a free account, you will likely encounter errors or limitations when trying to control playback.

## Features

*   Search for public playlists on Spotify.
*   Fetch your own saved playlists (by searching for "0").
*   Select playlists from search results using a `curses`-based UI.
*   Select an active Spotify device (e.g., desktop client, web player, speaker) using a `curses`-based UI.
*   Control playback (Requires Premium):
    *   Play/Pause
    *   Next/Previous Track
    *   Volume Up/Down (if device supports it)
    *   Toggle Shuffle
*   View currently playing track information.
*   Responsive `curses` UI that adapts to terminal resizing (within limits).

## Requirements

 *   **Python:** 3.6 or higher.
 *   **pip:** Python package installer (or `uv`).
 *   **Spotify Account:** A Spotify account is required. **A Spotify Premium account is required** for playback control features.
 *   **Spotify API Credentials:**
     *   Client ID
     *   Client Secret
     *   Redirect URI
 *   **curses library:** Standard on most Unix-like systems (Linux, macOS). For Windows, you might need to install `windows-curses`: `pip install windows-curses` or `uv pip install windows-curses`. Note that Windows compatibility might vary.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/256x/spolistplay.git
    cd spolistplay
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(On Windows, you might need `pip install windows-curses` as well if it's not already handled.)*
    **Using `uv` (a fast Python package installer and resolver):**

    If you have `uv` installed (see [uv's official documentation](https://github.com/astral-sh/uv) for installation instructions), you can use it to create a virtual environment and install dependencies:
    ```bash
    # Optionally, create and activate a virtual environment
    uv venv .venv
    source .venv/bin/activate  # On Linux/macOS
    # .venv\Scripts\activate  # On Windows (Command Prompt)
    # .venv\Scripts\Activate.ps1 # On Windows (PowerShell)

    # Install dependencies using uv
    uv pip install -r requirements.txt
    ```
    *(On Windows, if `curses` is not readily available, you might also need to install `windows-curses`: `uv pip install windows-curses` if it's not handled by `requirements.txt`.)*

## Setup

### 1. Get Spotify API Credentials

1.  Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
2.  Log in with your Spotify account.
3.  Create a new application (or use an existing one).
4.  Note down the **Client ID** and **Client Secret**.
5.  Go to the application's settings (`Edit Settings`).
6.  Add a **Redirect URI**. A common one for local development is `http://localhost:8888/callback` or `https://127.0.0.0/`. **Important:** The URI you set here *must exactly match* the `SPOTIPY_REDIRECT_URI` environment variable you will set below. The script defaults to `https://127.0.0.0/` if the environment variable is not set.

### 2. Set Environment Variables

Set the following environment variables in your system:

*   `SPOTIPY_CLIENT_ID`: Your Spotify application's Client ID.
*   `SPOTIPY_CLIENT_SECRET`: Your Spotify application's Client Secret.
*   `SPOTIPY_REDIRECT_URI`: The Redirect URI you set in the Spotify Developer Dashboard (e.g., `https://127.0.0.0/`).

**Example (Linux/macOS - temporary for the current session):**

```bash
export SPOTIPY_CLIENT_ID='your_client_id'
export SPOTIPY_CLIENT_SECRET='your_client_secret'
export SPOTIPY_REDIRECT_URI='https://127.0.0.0/' # Or your chosen URI
```

*(Add these lines to your `.bashrc`, `.zshrc`, or equivalent shell profile for permanent setup.)*

**Example (Windows - Command Prompt - temporary):**

```cmd
set SPOTIPY_CLIENT_ID=your_client_id
set SPOTIPY_CLIENT_SECRET=your_client_secret
set SPOTIPY_REDIRECT_URI=https://127.0.0.0/
```

**Example (Windows - PowerShell - temporary):**

```powershell
$env:SPOTIPY_CLIENT_ID = 'your_client_id'
$env:SPOTIPY_CLIENT_SECRET = 'your_client_secret'
$env:SPOTIPY_REDIRECT_URI = 'https://127.0.0.0/'
```

*(For permanent setup on Windows, use the System Properties -> Environment Variables panel.)*

### 3. First Run & Authentication

1.  Run the script:
    ```bash
    python spolistplay.py
    ```
2.  On the first run, your web browser should open automatically, asking you to log in to Spotify and authorize the application.
3.  After you authorize, Spotify will redirect you to the `REDIRECT_URI` you specified.
4.  **IMPORTANT:** The script attempts to automatically capture the authentication code from the redirect. However, this might fail depending on your system setup.
    *   **If successful:** The script will proceed after showing an "Authentication successful" message.
    *   **If it fails:** The browser will likely show a "Cannot GET /" or similar error on the redirect page (this is normal if no local server is running). **You need to manually copy the *entire URL* from your browser's address bar** (it will look something like `https://127.0.0.0/?code=AQB...`).
    *   Paste this full URL back into the terminal where the script is waiting for input.
5.  Once authenticated, the script will create a cache file (`~/.cache/spotify/.spotify_cache` on Linux/macOS, similar path in user directory on Windows) so you don't have to authenticate every time.

## Usage

1.  **Run the script:**
    ```bash
    python spolistplay.py
    ```

2.  **Search:**
    *   Enter a search query for playlists (e.g., "80s rock", "coding focus").
    *   Enter `0` to fetch your own saved playlists.
    *   Press `Enter` to search.
    *   Press `ESC` during input to exit.

3.  **Select Playlist:**
    *   A list of found playlists will be displayed.
    *   Use `Up/Down` arrows or `j/k` keys to navigate.
    *   Use `Left/Right` arrows or `h/l` keys to change pages.
    *   Type the number of the playlist and press `Enter` for direct selection.
    *   Press `Enter` on the highlighted item to select.
    *   Press `ESC` to go back to the search prompt.
    *   Press `?` to see available commands in a popup.

4.  **Select Device:**
    *   A list of your active Spotify devices will be shown.
    *   Navigate and select similarly to the playlist selection (`Up/Down/j/k`, number + `Enter`, `Enter` on highlight).
    *   Press `ESC` or `q` to go back to the search prompt.
    *   Press `?` to see available commands.

5.  **Playback Control (Requires Premium):**
    *   Once a playlist and device are selected, playback starts automatically.
    *   The screen shows current track info, playback status, etc.
    *   **Key Commands:**
        *   `Enter` or `p`: Play/Pause
        *   `Right Arrow` or `l`: Next Track
        *   `Left Arrow` or `h`: Previous Track
        *   `Up Arrow` or `k`: Volume Up (if supported)
        *   `Down Arrow` or `j`: Volume Down (if supported)
        *   `s`: Toggle Shuffle
        *   `?`: Show commands popup.
        *   `ESC` or `q`: Stop playback and return to search.
        *   `x`: Stop playback and exit the entire application.

## Notes

*   **Spotify Premium:** As mentioned above, Premium is required for controlling playback. Free accounts will have limited functionality.
*   **Terminal Size:** The `curses` UI requires a minimum terminal size. If your terminal is too small, the script may raise an error or display incorrectly.
*   **Windows Compatibility:** `curses` support on Windows can be less stable than on Linux/macOS. Using Windows Terminal or WSL (Windows Subsystem for Linux) might provide a better experience.
*   **Authentication Cache:** If you encounter persistent authentication issues, try deleting the cache file (`~/.cache/spotify/.spotify_cache`) and re-authenticating.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

