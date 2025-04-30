# spolistplay

[English Version](README.md)

![spolistplay demo gif](https://github.com/user-attachments/assets/26c22414-2cb2-4e26-a5db-219ecaf04398)

`curses` ライブラリを使用した、ターミナルベースの Spotify プレイリストプレイヤーです。ターミナルから直接、プレイリストの検索、選択、アクティブな Spotify デバイスの選択、再生コントロールを行えます。

Git URL: https://github.com/256x/spolistplay

**❗ 重要な注意: 再生コントロールには Spotify Premium が必要です ❗**

再生の開始・一時停止、曲送り・戻し、音量調整、シャッフル切り替えなどの完全な再生コントロール機能を利用するには、**Spotify Premium アカウントが必須**です。無料アカウントでもプレイリストの検索や一覧表示は可能かもしれませんが、再生をコントロールしようとするとエラーが発生したり、機能が制限されたりします。

## 機能

*   Spotify 上の公開プレイリストを検索
*   自分が保存したプレイリストを取得（検索時に "0" を入力）
*   `curses` ベースの UI で検索結果からプレイリストを選択
*   `curses` ベースの UI でアクティブな Spotify デバイス（デスクトップクライアント、ウェブプレイヤー、スピーカーなど）を選択
*   再生コントロール (Premium が必要):
    *   再生 / 一時停止
    *   次の曲 / 前の曲
    *   音量アップ / ダウン（デバイスが対応している場合）
    *   シャッフルのオン / オフ切り替え
*   現在再生中の曲情報を表示
*   ターミナルのリサイズにある程度追従するレスポンシブな `curses` UI

## 要件

*   **Python:** 3.6 以上
*   **pip:** Python パッケージインストーラー
*   **Spotify アカウント:** Spotify アカウントが必要です。**再生コントロール機能には Spotify Premium アカウントが必須**です。
*   **Spotify API クレデンシャル:**
    *   クライアント ID (Client ID)
    *   クライアントシークレット (Client Secret)
    *   リダイレクト URI (Redirect URI)
*   **curses ライブラリ:** ほとんどの Unix 系システム（Linux, macOS）には標準で含まれています。Windows の場合は `windows-curses` のインストールが必要な場合があります (`pip install windows-curses`)。ただし、Windows での互換性は環境によって異なる可能性があります。

## インストール

1.  **リポジトリをクローン:**
    ```bash
    git clone https://github.com/256x/spolistplay.git
    cd spolistplay
    ```

2.  **依存関係をインストール:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Windows では、必要に応じて `pip install windows-curses` も実行してください。)*

## セットアップ

### 1. Spotify API クレデンシャルの取得

1.  [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/) にアクセスします。
2.  お使いの Spotify アカウントでログインします。
3.  新しいアプリケーションを作成します（または既存のものを使用します）。
4.  **Client ID** と **Client Secret** をメモします。
5.  アプリケーションの設定画面 (`Edit Settings`) を開きます。
6.  **Redirect URI** を追加します。ローカル開発で一般的な URI は `http://localhost:8888/callback` や `https://127.0.0.0/` です。**重要:** ここで設定した URI は、後述する環境変数 `SPOTIPY_REDIRECT_URI` と**完全に一致**させる必要があります。環境変数が設定されていない場合、スクリプトはデフォルトで `https://127.0.0.0/` を使用します。

### 2. 環境変数の設定

以下の環境変数をシステムに設定します:

*   `SPOTIPY_CLIENT_ID`: Spotify アプリケーションの Client ID。
*   `SPOTIPY_CLIENT_SECRET`: Spotify アプリケーションの Client Secret。
*   `SPOTIPY_REDIRECT_URI`: Spotify Developer Dashboard で設定した Redirect URI (例: `https://127.0.0.0/`)。

**例 (Linux/macOS - 現在のセッションで一時的に設定):**

```bash
export SPOTIPY_CLIENT_ID='your_client_id'
export SPOTIPY_CLIENT_SECRET='your_client_secret'
export SPOTIPY_REDIRECT_URI='https://127.0.0.0/' # または設定した URI
```

*(恒久的に設定する場合は、`.bashrc` や `.zshrc` などのシェル設定ファイルにこれらの行を追加してください。)*

**例 (Windows - コマンドプロンプト - 一時的):**

```cmd
set SPOTIPY_CLIENT_ID=your_client_id
set SPOTIPY_CLIENT_SECRET=your_client_secret
set SPOTIPY_REDIRECT_URI=https://127.0.0.0/
```

**例 (Windows - PowerShell - 一時的):**

```powershell
$env:SPOTIPY_CLIENT_ID = 'your_client_id'
$env:SPOTIPY_CLIENT_SECRET = 'your_client_secret'
$env:SPOTIPY_REDIRECT_URI = 'https://127.0.0.0/'
```

*(Windows で恒久的に設定する場合は、「システムのプロパティ」->「環境変数」パネルを使用してください。)*

### 3. 初回実行と認証

1.  スクリプトを実行します:
    ```bash
    python spolistplay.py
    ```
2.  初回実行時、自動的にウェブブラウザが開き、Spotify へのログインとアプリケーションの認証を求められます。
3.  認証後、Spotify は指定した `REDIRECT_URI` にリダイレクトします。
4.  **重要:** スクリプトはリダイレクトから認証コードを自動的に取得しようと試みますが、システム設定によっては失敗することがあります。
    *   **成功した場合:** 「Authentication successful」というメッセージが表示され、スクリプトが続行します。
    *   **失敗した場合:** ブラウザはおそらくリダイレクト先のページで「Cannot GET /」のようなエラーを表示します（ローカルサーバーが動作していない場合、これは正常です）。**この時、ブラウザのアドレスバーに表示されている *URL 全体* を手動でコピーする必要があります**（`https://127.0.0.0/?code=AQB...` のような形式です）。
    *   コピーした URL 全体を、スクリプトが待機しているターミナルに貼り付けて Enter キーを押してください。
5.  認証が完了すると、スクリプトはキャッシュファイル（Linux/macOS では `~/.cache/spotify/.spotify_cache`、Windows ではユーザーディレクトリ内の類似パス）を作成します。これにより、次回以降は認証が不要になります。

## 使い方

1.  **スクリプトを実行:**
    ```bash
    python spolistplay.py
    ```

2.  **検索:**
    *   プレイリストの検索クエリを入力します（例: 「80年代 ロック」、「作業用BGM」）。
    *   `0` を入力すると、自分のライブラリ内のプレイリストを取得します。
    *   `Enter` キーで検索を実行します。
    *   入力中に `ESC` キーを押すと終了します。

3.  **プレイリスト選択:**
    *   見つかったプレイリストのリストが表示されます。
    *   `↑`/`↓` キーまたは `j`/`k` キーで項目を移動します。
    *   `←`/`→` キーまたは `h`/`l` キーでページを切り替えます。
    *   プレイリストの番号を入力して `Enter` キーを押すと直接選択できます。
    *   ハイライトされている項目上で `Enter` キーを押して選択します。
    *   `ESC` キーで検索プロンプトに戻ります。
    *   `?` キーで利用可能なコマンドをポップアップ表示します。

4.  **デバイス選択:**
    *   アクティブな Spotify デバイスのリストが表示されます。
    *   プレイリスト選択と同様に操作して選択します（`↑`/`↓`/`j`/`k`、番号 + `Enter`、ハイライト上で `Enter`）。
    *   `ESC` キーまたは `q` キーで検索プロンプトに戻ります。
    *   `?` キーで利用可能なコマンドを表示します。

5.  **再生コントロール (Premium が必要):**
    *   プレイリストとデバイスを選択すると、自動的に再生が開始されます。
    *   画面には現在の曲情報や再生ステータスなどが表示されます。
    *   **主なコマンド:**
        *   `Enter` または `p`: 再生 / 一時停止
        *   `→` または `l`: 次の曲
        *   `←` または `h`: 前の曲
        *   `↑` または `k`: 音量アップ（対応デバイスのみ）
        *   `↓` または `j`: 音量ダウン（対応デバイスのみ）
        *   `s`: シャッフル切り替え
        *   `?`: コマンドのポップアップ表示
        *   `ESC` または `q`: 再生を停止して検索に戻る
        *   `x`: 再生を停止してアプリケーション全体を終了する

## 注意事項

*   **Spotify Premium:** 上述の通り、再生コントロールには Premium が必須です。無料アカウントでは機能が制限されます。
*   **ターミナルサイズ:** `curses` UI は最低限のターミナルサイズを必要とします。ターミナルが小さすぎると、スクリプトがエラーを発生させるか、表示が崩れる可能性があります。
*   **Windows での互換性:** Windows での `curses` のサポートは Linux/macOS ほど安定していない場合があります。Windows Terminal や WSL (Windows Subsystem for Linux) を使用すると、より良い体験が得られる可能性があります。
*   **認証キャッシュ:** 認証に関する問題が続く場合は、キャッシュファイル (`~/.cache/spotify/.spotify_cache`) を削除して再認証を試みてください。

## ライセンス

このプロジェクトは MIT ライセンスの下で公開されています。詳細は [LICENSE](LICENSE) ファイルを参照してください。
