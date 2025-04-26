# Spotify Playlist BGM Player (JP/EN)

---

## 日本語

### 概要

このスクリプトは、Spotify Web APIを使用して、指定したキーワードでプレイリストを検索し、選択したプレイリストをBGM用途で再生するためのシンプルなツールです。再生中は基本的にユーザー操作はできませんが、`CTRL+C`で再生を中断して検索画面に戻ることができます。

### 特徴

*   Spotifyプレイリストの検索機能
*   検索結果からのプレイリスト選択
*   利用可能なデバイスへの再生開始
*   再生中の曲情報表示（BGM用途）
*   `CTRL+C`による再生中断と検索メニューへの復帰
*   Spotify認証情報の自動キャッシュ

### 必要条件

*   Python 3.6以上
*   インターネット接続
*   Spotifyアカウント（無料またはPremium）
*   Spotify開発者アカウントおよび、作成したアプリケーションの Client ID, Client Secret, Redirect URI

### セットアップ（インストール）

#### 1. スクリプトの入手

このコードを `spolistplay.py` という名前でファイルに保存します。

#### 2. 必要なライブラリのインストール

pipを使って、必要なライブラリ `spotipy` をインストールします。

```bash
pip install spotipy
```

#### 3. Spotify開発者設定

1.  [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/) にアクセスし、ログインします。
2.  新しいアプリケーションを作成します（例: `My BGM Player`）。
3.  作成したアプリケーションのページで、`Client ID` と `Client Secret` を確認します。これらは後で使用します。
4.  アプリケーションの設定（Edit Settings）を開きます。
5.  `Redirect URIs` に、`https://127.0.0.1/` を追加します。他のURIが設定されていても構いませんが、スクリプトのデフォルト設定に合わせて `https://127.0.0.1/` を含めてください。
6.  設定を保存します。

#### 4. 環境変数の設定

スクリプトがSpotify APIに接続するためには、以下の環境変数を設定する必要があります。

*   `SPOTIPY_CLIENT_ID`: Spotify開発者ダッシュボードで取得したClient ID
*   `SPOTIPY_CLIENT_SECRET`: Spotify開発者ダッシュボードで取得したClient Secret
*   `SPOTIPY_REDIRECT_URI`: Spotify開発者ダッシュボードで設定したRedirect URI (例: `https://127.0.0.1/`)

これらの環境変数は、スクリプトを実行するシェルで設定するか、`.env` ファイルなどを使用して管理することができます。

**例：bash/zsh の場合**

```bash
export SPOTIPY_CLIENT_ID='your_client_id_here'
export SPOTIPY_CLIENT_SECRET='your_client_secret_here'
export SPOTIPY_REDIRECT_URI='https://127.0.0.1/'
```

**注意:** 環境変数の設定方法は、使用しているOSやシェルによって異なります。

### 使い方

1.  環境変数が正しく設定されていることを確認します。
2.  スクリプトを実行します。

    ```bash
    python spolistplay.py
    ```

3.  初回実行時には、ブラウザが開きSpotifyアカウントへのアクセス許可を求められます。承認してください。承認後、ブラウザのアドレスバーに表示されるURLにリダイレクトされます。このURLをターミナルに貼り付けてEnterを押すように求められる場合があります（Redirect URIの設定やブラウザの挙動によります）。
4.  認証が完了すると、検索プロンプトが表示されます。再生したいプレイリストのキーワードを入力してEnterを押します。**自分のプレイリストを検索したい場合は、「0」を入力してください。**

    ```
    - spotify playlist player

    search: [検索したいキーワード]
    ```

5.  検索結果が表示されます。再生したいプレイリストの番号を入力してEnterを押します。

    ```
    Playlists:
    1. [プレイリスト名 1] ([トラック数] tracks) - [オーナー名]
    2. [プレイリスト名 2] ([トラック数] tracks) - [オーナー名]
    ...

    No.: [番号]
    ```

6.  次に、再生に使用するデバイスを選択するプロンプトが表示されます。利用可能なデバイスの番号を入力してEnterを押します。

    ```
    Active Spotify Devices:
    1. [デバイス名 1] ([タイプ]) [Active]
    2. [デバイス名 2] ([タイプ])
    ...

    device: [番号]
    ```

7.  デバイスを選択すると、プレイリストの再生が開始されます。

    ```
    ♪ [曲名] / [アーティスト名]
    󰀥 [アルバム名] ([年])

    ...
    ```

    **重要:**
    *   **再生が始まると、基本的にユーザーからの操作（一時停止、スキップなど）はできません。** スクリプトはBGM用途を想定しており、再生中は現在再生されている曲情報の表示のみを行います。
    *   シャッフル再生が有効になります。

8.  再生を中断したい場合や、別のプレイリストを検索したい場合は、**`CTRL+C`** を押してください。再生が一時停止され、検索プロンプトに戻ります。
9.  プログラム自体を終了したい場合は、検索プロンプトが表示されている状態で再度 **`CTRL+C`** を押してください。

### 注意点

*   このスクリプトは、BGMとしてプレイリストを流し続けることに特化しています。細かい再生制御機能は含まれていません。
*   再生中に`CTRL+C`を押すと、現在の再生セッションは一時停止され、スクリプトはプレイリスト検索のステップに戻ります。
*   Spotifyの認証情報は、ユーザーのホームディレクトリ内の隠しフォルダ (`~/.cache/spotify/.spotify_cache`) にキャッシュされます。これにより、二回目以降の実行時に認証がスキップされます。認証をやり直したい場合は、このファイルを削除してください。
*   再生可能なデバイスが検出されない場合、デバイス選択ステップでエラーとなり再生を開始できません。事前にSpotifyアプリなどで再生を開始し、アクティブなデバイスがある状態にしておいてください。

---

## English

### Overview

This script is a simple tool that uses the Spotify Web API to search for playlists based on a keyword and play the selected playlist for background music (BGM) purposes. Once playback begins, user interaction is generally not possible, but you can interrupt playback and return to the search screen by pressing `CTRL+C`.

### Features

*   Search for Spotify playlists
*   Select a playlist from search results
*   Start playback on an available device
*   Display current track information (for BGM use)
*   Interrupt playback and return to the search menu using `CTRL+C`
*   Automatic caching of Spotify authentication credentials

### Requirements

*   Python 3.6 or higher
*   Internet connection
*   Spotify account (Free or Premium)
*   Spotify Developer account and the Client ID, Client Secret, and Redirect URI for a created application

### Setup (Installation)

#### 1. Get the Script

Save the provided code into a file named `spolistplay.py`.

#### 2. Install Dependencies

Install the required `spotipy` library using pip.

```bash
pip install spotipy
```

#### 3. Spotify Developer Setup

1.  Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/) and log in.
2.  Create a new application (e.g., `My BGM Player`).
3.  On your application's page, find the `Client ID` and `Client Secret`. You will need these later.
4.  Open the application's settings (Edit Settings).
5.  Add `https://127.0.0.1/` to the `Redirect URIs`. You can have other URIs set up, but make sure `https://127.0.0.1/` is included to match the script's default.
6.  Save the settings.

#### 4. Set Environment Variables

The script requires the following environment variables to connect to the Spotify API.

*   `SPOTIPY_CLIENT_ID`: Your Client ID from the Spotify Developer Dashboard.
*   `SPOTIPY_CLIENT_SECRET`: Your Client Secret from the Spotify Developer Dashboard.
*   `SPOTIPY_REDIRECT_URI`: The Redirect URI you set in the Spotify Developer Dashboard (e.g., `https://127.0.0.1/`).

You can set these variables in the shell where you run the script or manage them using a `.env` file or similar methods.

**Example: For bash/zsh**

```bash
export SPOTIPY_CLIENT_ID='your_client_id_here'
export SPOTIPY_CLIENT_SECRET='your_client_secret_here'
export SPOTIPY_REDIRECT_URI='https://127.0.0.1/'
```

**Note:** The method for setting environment variables varies depending on your OS and shell.

### How to Use

1.  Ensure that the environment variables are correctly set.
2.  Run the script:

    ```bash
    python spolistplay.py
    ```

3.  The first time you run it, a browser window will open asking for permission to access your Spotify account. Authorize it. After authorization, you may be redirected to a URL in your browser's address bar. You might be prompted to paste this URL back into the terminal and press Enter (this depends on your Redirect URI settings and browser behavior).
4.  Once authentication is complete, a search prompt will appear. Enter keywords for the playlist you want to find and press Enter. **If you want to search for your own playlists, enter "0".**

    ```
    - spotify playlist player

    search: [your search query]
    ```

5.  Search results will be displayed. Enter the number corresponding to the playlist you want to play and press Enter.

    ```
    Playlists:
    1. [Playlist Name 1] ([Number of Tracks] tracks) - [Owner Name]
    2. [Playlist Name 2] ([Number of Tracks] tracks) - [Owner Name]
    ...

    No.: [number]
    ```

6.  Next, you will be prompted to select the device to use for playback. Enter the number of an available device and press Enter.

    ```
    Active Spotify Devices:
    1. [Device Name 1] ([Type]) [Active]
    2. [Device Name 2] ([Type])
    ...

    device: [number]
    ```

7.  After selecting a device, playback of the playlist will start.

    ```
    ♪ [Track Title] / [Artist Name]
    󰀥 [Album Name] ([Year])

    ...
    ```

    **Important Notes during Playback:**
    *   **Once playback starts, user controls (like pause, skip) are generally not available.** The script is designed for BGM use and primarily shows current track info during playback.
    *   Shuffle playback will be enabled.

8.  If you want to interrupt playback or search for another playlist, press **`CTRL+C`**. Playback will pause, and the script will return to the search prompt.
9.  To exit the program completely, press **`CTRL+C`** again when you are *not* in playback (i.e., at a menu or the search prompt).

### Notes

*   This script is specialized for continuous playback of a playlist as BGM. It does not include detailed playback control features.
*   Pressing `CTRL+C` during playback will pause the current session and return the script to the playlist search step.
*   Spotify authentication credentials are cached in a hidden directory within your user's home directory (`~/.cache/spotify/.spotify_cache`). This allows subsequent runs to skip authentication. If you need to re-authenticate, delete this file.
*   If no playable devices are detected, the device selection step will fail, and playback cannot start. Ensure you have an active Spotify device (e.g., by starting playback in the Spotify app) before using this script.
```
