# spolistplay: Command-Line Spotify Playlist Player

[日本語版はこちら](https://github.com/256x/spolistplay/blob/main/README_ja.md)

`spolistplay` is a simple command-line tool written in Python that allows you to search for Spotify playlists, select one, choose a playback device, and control playback directly from your terminal using an interactive interface.

**Note:** This tool requires a **Spotify Premium account** for playback control features via the API.

## Features

*   Search for Spotify playlists by keyword or list your own playlists.
*   Select a playlist to play.
*   Choose an available Spotify device for playback.
*   Interactive terminal interface for playback control (Play/Pause, Next, Previous, Shuffle, Exit).
*   Basic error handling and logging.

## Requirements

*   Python 3.x
*   A **Spotify Premium account**
*   A running Spotify client/device logged into your account

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd spolistplay
    ```
    *(Replace `<repository_url>` with the actual URL of your Git repository).*

2.  **Install dependencies:**
    Use pip to install the required libraries.
    ```bash
    pip install -r requirements.txt
    ```
    If you are on **Windows** and encounter issues with the terminal interface, you might need the `windows-curses` package:
    ```bash
    pip install windows-curses
    ```

## Initial Setup (Spotify API Authentication)

`spolistplay` uses the Spotify Web API to interact with your account. You need to create a Spotify Developer application and provide its credentials.

1.  **Go to the Spotify Developer Dashboard:**
    Visit [https://developer.spotify.com/dashboard/applications](https://developer.spotify.com/dashboard/applications) and log in with your Spotify account.

2.  **Create an Application:**
    Click "Create app". Give it a name (e.g., "spolistplay") and a description. Agree to the terms.

3.  **Get Client ID and Client Secret:**
    Once the app is created, you will see its Dashboard. Your "Client ID" is visible here. Click "Show Client Secret" to reveal your secret. **Keep your Client Secret confidential.**

4.  **Configure Redirect URIs:**
    Click "Edit Settings". Under "Redirect URIs", add the exact URI that `spolistplay` will use. The default in the script is `https://127.0.0.1/`. You must add *this exact URI* to the list in your Spotify application settings. You can add multiple URIs if needed, but make sure the one used by the script is present.
    *Example:* `https://127.0.0.1/`

5.  **Set Environment Variables:**
    The script reads your Client ID, Client Secret, and Redirect URI from environment variables. Set these in your terminal session before running the script.

    *   **Bash/Zsh (Linux, macOS):**
        ```bash
        export SPOTIPY_CLIENT_ID="YOUR_CLIENT_ID"
        export SPOTIPY_CLIENT_SECRET="YOUR_CLIENT_SECRET"
        export SPOTIPY_REDIRECT_URI="https://127.0.0.1/" # Or your chosen URI
        ```
    *   **PowerShell (Windows):**
        ```powershell
        $env:SPOTIPY_CLIENT_ID="YOUR_CLIENT_ID"
        $env:SPOTIPY_CLIENT_SECRET="YOUR_CLIENT_SECRET"
        $env:SPOTIPY_REDIRECT_URI="https://127.0.0.1/" # Or your chosen URI
        ```
    *   **Command Prompt (Windows):**
        ```cmd
        set SPOTIPY_CLIENT_ID="YOUR_CLIENT_ID"
        set SPOTIPY_CLIENT_SECRET="YOUR_CLIENT_SECRET"
        set SPOTIPY_REDIRECT_URI="https://127.0.0.1/" # Or your chosen URI
        ```
    *(Replace `"YOUR_CLIENT_ID"` and `"YOUR_CLIENT_SECRET"` with your actual credentials).*

    For permanent setup, consider adding these lines to your shell's profile file (`~/.bashrc`, `~/.zshrc`, `~/.profile`, etc.) or setting system-wide environment variables.

6.  **First Run Authorization:**
    The first time you run the script after setting the environment variables, it will likely open a web browser prompting you to log in to Spotify and authorize your application. After authorization, the browser will redirect to the specified Redirect URI.

    **Manual Authorization (if automatic redirection fails):**
    Sometimes the automatic redirection or token retrieval doesn't work. If your browser opens and redirects to `https://127.0.0.1/` (or your chosen URI) but the script doesn't proceed:
    *   Look at the URL in your browser's address bar. It should look something like `https://127.0.0.1/?code=AQC...&state=...`.
    *   **Copy the *entire* URL** from the browser's address bar.
    *   Go back to your terminal where the `spolistplay.py` script is running. The script might be waiting for input, or display an error message.
    *   **Paste the copied URL** into the terminal and press Enter. The script should now be able to retrieve the authorization token and proceed.

    Subsequent runs should use a cached token and not require browser interaction unless the token expires or the cache is invalid.

    The cache file is stored in `~/.cache/spotify/.spotify_cache`.

## Usage

1.  Make sure you have completed the initial setup and set the environment variables.
2.  Ensure a Spotify client (desktop, mobile, web player) is running and logged into your account, and that the desired playback device is available.
3.  Run the script from your terminal:
    ```bash
    python spolistplay.py
    ```
4.  **Search or List Playlists:**
    *   Enter a search term (e.g., "rock hits") and press Enter to search for playlists.
    *   Enter `0` and press Enter to list your own saved playlists.
    *   Press `ESC` during search input to exit the program.
5.  **Select Playlist:**
    A list of found playlists will be displayed. Enter the number corresponding to the playlist you want to play and press Enter.
6.  **Select Device:**
    A list of available Spotify devices will be shown. Enter the number corresponding to the device you want to play on and press Enter.
7.  **Playback Interface:**
    Once a playlist and device are selected, the script will switch to an interactive terminal interface showing playback information and controls.

    **Playback Controls:**

    | Key       | Action                       |
    | :-------- | :--------------------------- |
    | `P` or `p` | Toggle Play/Pause            |
    | `<` or `,` | Play Previous Track          |
    | `>` or `.` | Play Next Track              |
    | `S` or `s` | Toggle Shuffle On/Off        |
    | `ESC`     | Return to Playlist Search    |
    | `X` or `x` | Exit Program (pauses playback) |

    The interface will periodically update to show the current track, artist, album, playback status, and shuffle state.

## Tips & Troubleshooting

*   **Spotify Premium:** Playback control via the API (starting playback on a specific device, skipping, pausing, shuffling) requires Spotify Premium.
*   **Device Not Found:** Ensure your Spotify client (desktop, mobile) is running, logged in, and visible on your network. Sometimes, you might need to start playback manually on a device once to make it discoverable by the API.
*   **Authentication Errors:** Double-check your Client ID, Client Secret, and Redirect URI environment variables and the settings in your Spotify Developer Dashboard. Ensure the Redirect URI is *exactly* the same. Try deleting the cache file (`~/.cache/spotify/.spotify_cache`) to force re-authentication. If the browser opens but the script hangs, remember to copy the final URL from the browser and paste it into the terminal.
*   **Terminal Compatibility:** The interactive interface uses terminal capabilities. Ensure your terminal supports basic full-screen and key input handling. If you are on Windows, installing `windows-curses` might help.
*   **`getch` Issues:** The character input (`getch`) is implemented with basic methods. It might not work perfectly on all terminal types or configurations.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Credits

*   Uses the `spotipy` library ([https://spotipy.readthedocs.io/en/2.24.0/](https://spotipy.readthedocs.io/en/2.24.0/)) for interacting with the Spotify Web API.

