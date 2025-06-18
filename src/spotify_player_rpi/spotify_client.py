# spotify_client.py
import json
import os
import time

import spotipy
from spotipy.oauth2 import SpotifyOAuth

import spotify_player_rpi.config as config # config.py からAPI認証情報を読み込む
from spotify_player_rpi.types.playbackinfo import PlaybackInfo


class SpotifyClient:
    def __init__(self):
        # accounts.json のパスをconfig.PROJECT_ROOTから構築
        self.accounts_file = os.path.join(config.PROJECT_ROOT, 'accounts.json')
        self.accounts_data = [] 
        self.current_account_index = -1
        self.sp = None # Spotipy Spotify client instance
        self.sp_oauth = None # Spotipy SpotifyOAuth instance
        self._load_accounts() # コンストラクタでアカウントデータをロード

    def _load_accounts(self):
        """ユーザーアカウントデータをaccounts.jsonファイルからロードする。"""
        if os.path.exists(self.accounts_file):
            try:
                with open(self.accounts_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.accounts_data = data
                    else:
                        print(f"WARNING: {self.accounts_file} has unexpected format. Expected a list. Resetting to empty list.")
                        self.accounts_data = []
                print(f"INFO: Loaded {len(self.accounts_data)} Spotify user accounts.")
                print(f"DEBUG: Accounts file path: {self.accounts_file}")
                if self.accounts_data:
                    print("DEBUG: Loaded accounts data (first entry):")
                    # 機密情報なので一部だけ表示
                    first_account = self.accounts_data[0]
                    print(f"  name: {first_account.get('name')}")
                    print(f"  access_token (first 5 chars): {first_account.get('access_token', '')[:5]}...")
                    print(f"  refresh_token (first 5 chars): {first_account.get('refresh_token', '')[:5]}...")
                    print(f"  expires_at: {first_account.get('expires_at')}")
                else:
                    print("DEBUG: accounts.json was loaded but is empty or malformed.")

            except json.JSONDecodeError:
                print(f"ERROR: Could not decode {self.accounts_file}. File might be corrupted. Starting with no user accounts.")
                self.accounts_data = []
            except Exception as e: # その他の読み込みエラーも捕捉
                print(f"ERROR: Unexpected error reading {self.accounts_file}: {e}")
                self.accounts_data = []
        else:
            print(f"INFO: No {self.accounts_file} found. Starting with no user accounts.")
            self.accounts_data = []
            
            # ロード後、現在のcurrent_account_indexが有効範囲内かチェック
            if self.current_account_index >= len(self.accounts_data):
                self.current_account_index = 0 if self.accounts_data else -1 

    def _save_accounts(self):
        """現在のユーザーアカウントデータをaccounts.jsonファイルに保存する。"""
        try:
            with open(self.accounts_file, 'w') as f:
                json.dump(self.accounts_data, f, indent=2)
            print("INFO: User accounts saved successfully.")
        except Exception as e:
            print(f"ERROR: Failed to save user accounts to {self.accounts_file}: {e}")

    def set_current_account(self, index):
        """
        指定されたユーザーアカウントを現在のアクティブアカウントとして設定し、認証を試みる。
        成功した場合はTrue、失敗した場合はFalseを返す。
        """
        # Client IDとClient Secretが設定されているか確認
        if not (config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET):
            print("ERROR: Spotify Client ID/Secret not set in .env. Cannot authenticate user account.")
            self.sp = None
            self.sp_oauth = None
            return False

        if not self.accounts_data:
            print("INFO: No user accounts available to set.")
            self.sp = None
            self.sp_oauth = None
            return False

        if 0 <= index < len(self.accounts_data):
            self.current_account_index = index
            return self._authenticate_current_account()
        else:
            print(f"ERROR: Invalid user account index: {index}. Cannot set current account.")
            self.sp = None
            self.sp_oauth = None
            return False

    def _authenticate_current_account(self):
        """
        現在選択されているユーザーアカウントで、キャッシュされたトークンを使用するか、
        リフレッシュして認証を試みる。成功した場合はTrue、失敗した場合はFalseを返す。
        """
        if self.current_account_index == -1 or not self.accounts_data:
            print("ERROR: No current account selected or no accounts data for authentication.")
            self.sp = None
            self.sp_oauth = None
            return False

        user_account_info = self.accounts_data[self.current_account_index]
        user_name = user_account_info.get('name', f"Unnamed User {self.current_account_index + 1}")
        print(f"INFO: Attempting to authenticate user account: '{user_name}'")

        client_id = config.SPOTIPY_CLIENT_ID
        client_secret = config.SPOTIPY_CLIENT_SECRET
        
        if not client_id or not client_secret:
            print("ERROR: App Client ID/Secret missing from .env. Cannot proceed with user authentication.")
            self.sp = None
            self.sp_oauth = None
            return False

        cache_path = os.path.join(config.PROJECT_ROOT, f'.spotify_cache_{user_name.replace(" ", "_")}')

        self.sp_oauth = SpotifyOAuth(
            client_id=client_id, 
            client_secret=client_secret, 
            redirect_uri=config.SPOTIPY_REDIRECT_URI,
            scope=config.SCOPE,
            cache_path=cache_path,
            show_dialog=True 
        )
        
        token_info = self.sp_oauth.get_cached_token()
        if token_info:
            print(f"INFO: Cached token found for '{user_name}'.")
            if self.sp_oauth.is_token_expired(token_info):
                print(f"INFO: Access token for '{user_name}' expired, attempting to refresh...")
                try:
                    token_info = self.sp_oauth.refresh_access_token(token_info['refresh_token'])
                    print(f"INFO: Token refreshed successfully for '{user_name}'.")
                    # 更新されたトークン情報をaccounts.jsonに保存
                    user_account_info.update({
                        "access_token": token_info['access_token'],
                        "expires_at": token_info['expires_at'],
                        "refresh_token": token_info['refresh_token'] # リフレッシュトークンも更新される場合がある
                    })
                    self._save_accounts()
                except Exception as e:
                    print(f"ERROR: Failed to refresh token for '{user_name}': {e}")
                    token_info = None # トークン更新失敗として扱う
            
            if token_info:
                self.sp = spotipy.Spotify(auth=token_info['access_token'])
                print(f"SUCCESS: Spotify authentication successful for '{user_name}'.")
                return True
        else:
            print(f"INFO: No cached token found for '{user_name}'. Manual re-authentication required (via Web UI or get_tokens.py).")
        
        print(f"ERROR: Authentication failed for '{user_name}'. Token missing or invalid after all attempts.")
        self.sp = None # 認証失敗時はSpotipyクライアントをリセット
        self.sp_oauth = None
        return False

    def add_user_account_token(self, user_name, access_token, refresh_token, expires_at):
        """
        ユーザーアカウントを新しいトークン情報で追加または更新する。
        Webサーバーが認証後に呼び出すメソッド
        """
        if not (config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET):
            print("ERROR: Cannot add user account: Spotify Client ID/Secret not set in .env.")
            return False

        new_user_account_data = {
            "name": user_name,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at
        }
        
        found = False
        for i, acc in enumerate(self.accounts_data):
            if acc.get('name') == user_name:
                self.accounts_data[i] = new_user_account_data
                print(f"INFO: Updated existing user account: '{user_name}'.")
                found = True
                break
        if not found:
            self.accounts_data.append(new_user_account_data)
            print(f"INFO: Added new user account: '{user_name}'.")
        
        self._save_accounts()
        return True

    def delete_user_account(self, index):
        """ユーザーアカウントを指定したインデックスで削除し、関連するキャッシュファイルも削除する。"""
        if 0 <= index < len(self.accounts_data):
            deleted_user_account_name = self.accounts_data[index].get('name', f"Unnamed User {index+1}")
            del self.accounts_data[index]
            self._save_accounts()

            cache_file = os.path.join(config.PROJECT_ROOT, f'.spotify_cache_{deleted_user_account_name.replace(" ", "_")}')
            if os.path.exists(cache_file):
                try:
                    os.remove(cache_file)
                    print(f"INFO: Deleted cache file for '{deleted_user_account_name}'.")
                except Exception as e:
                    print(f"ERROR: Failed to remove cache file {cache_file}: {e}")
            print(f"INFO: Deleted user account: '{deleted_user_account_name}'.")
            return True
        return False

    def switch_to_next_account(self):
        """リスト内の次のユーザーアカウントに切り替える（物理ボタン用）。"""
        if not (config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET):
            print("ERROR: App Client ID/Secret not set in .env. Cannot switch user accounts.")
            self.sp = None
            self.sp_oauth = None
            return False

        if not self.accounts_data:
            print("INFO: No user accounts to switch. Add an account first.")
            self.sp = None
            self.sp_oauth = None
            return False
        
        # 次のアカウントのインデックスを計算
        next_index = (self.current_account_index + 1) % len(self.accounts_data)
        print(f"INFO: Attempting to switch to next user account (index: {next_index})...")
        return self.set_current_account(next_index)

    def get_current_playback(self) -> PlaybackInfo:
        """Spotify APIから現在の再生状態を取得する。"""
        if not (config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET):
            print("ERROR: Spotify Client ID/Secret not set. Cannot get playback info.")
            return PlaybackInfo(track_name="", artist_name="", is_playing=False)           
        if self.sp is None:
            print("ERROR: Spotify client not authenticated. Cannot get playback info.")
            return PlaybackInfo(track_name="", artist_name="", is_playing=False)
        
        try:
            # トークン自動更新のロジック
            # spotipyはget_cached_token()とrefresh_access_token()で自動的に処理するため、
            # ここではAPI呼び出し時にエラーが発生した場合の再認証を主に行う
            
            playback = self.sp.current_playback()
            if playback: # playbackがNoneでないことを確認
                if playback['is_playing']:
                    track = playback['item']
                    track_name = track['name']
                    artist_name = ", ".join([artist['name'] for artist in track['artists']])
                    track_url = track['external_urls']['spotify']
                    print(f"INFO: Currently playing: '{track_name}' by '{artist_name}'.")
                    return PlaybackInfo(
                        track_name=track_name,
                        artist_name=artist_name,
                        track_url=track_url,
                        is_playing=True
                    )
                else:
                    print("INFO: Music is paused or not playing.")
                    return PlaybackInfo(
                        track_name=track_name,
                        artist_name=artist_name,
                        track_url=track_url,
                        is_playing=False
                    )
            else:
                print("INFO: No playback context found.")
                return PlaybackInfo(track_name="", artist_name="", is_playing=False)

        except spotipy.exceptions.SpotifyException as e:
            print(f"ERROR: Spotify API Error during playback check: {e}")
            if "expired token" in str(e).lower() or "invalid_grant" in str(e).lower():
                print("INFO: Current user account token might be invalid or expired. Attempting to re-authenticate current account.")
                self.set_current_account(self.current_account_index) # トークン無効なら再認証を試みる
            self.sp = None # 認証失敗時はSpotifyクライアントをリセット
            return PlaybackInfo(track_name="", artist_name="", is_playing=False)

        except Exception as e:
            print(f"FATAL ERROR: An unexpected error occurred during playback check: {e}")
            self.sp = None
            return PlaybackInfo(track_name="", artist_name="", is_playing=False)
            
    def toggle_playback(self):
        """Spotifyで再生/一時停止を切り替える。"""
        if not (config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET):
            print("ERROR: Spotify Client ID/Secret not set. Cannot toggle playback.")
            return
        if self.sp is None:
            print("ERROR: Spotify client not authenticated. Cannot toggle playback.")
            return

        try:
            playback = self.sp.current_playback()
            if playback and playback['is_playing']:
                self.sp.pause_playback()
                print("INFO: Playback paused.")
            else:
                self.sp.start_playback()
                print("INFO: Playback started/resumed.")
        except spotipy.exceptions.SpotifyException as e:
            print(f"ERROR: Spotify API Error toggling playback: {e}")
            if "expired token" in str(e).lower() or "invalid_grant" in str(e).lower():
                print("INFO: Current user account token might be invalid or expired. Attempting to re-authenticate current account.")
                self.set_current_account(self.current_account_index)
        except Exception as e:
            print(f"FATAL ERROR: An unexpected error occurred toggling playback: {e}")



if __name__ == '__main__':
    print("--- spotify_client.py Debug Test ---")
    print("This test verifies Spotify API client functionality including authentication and playback.")
    print("Ensure .env file is configured and accounts.json has at least one user account.")

    client = SpotifyClient()
    
    if not (config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET):
        print("\n[SETUP REQUIRED] Spotify Client ID/Secret not set in .env. Skipping Spotify API tests.")
        print("Please edit your .env file in the project root (~/codes/spotify_player_rpi/.env) and set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET.")
        print("Example: SPOTIPY_CLIENT_ID=YOUR_ID\n         SPOTIPY_CLIENT_SECRET=YOUR_SECRET")
    elif not client.accounts_data:
        print("\n[SETUP REQUIRED] No user accounts found in accounts.json. Skipping Spotify API tests.")
        print("Please run 'poetry run python get_tokens.py' to add an account automatically.")
    else:
        print("\n--- Testing Account Authentication and Playback ---")
        for i, account in enumerate(client.accounts_data):
            account_name = account.get('name', f"Unnamed Account {i}")
            print(f"\n--- Testing Account '{account_name}' (Index: {i}) ---")
            
            if client.set_current_account(i):
                print(f"Successfully authenticated '{account_name}'.")
                
                # Test playback state multiple times to check refresh logic
                print("\nAttempting to get current playback (x3) to test refresh...")
                for _ in range(3):
                    playback = client.get_current_playback()
                    if playback['is_playing']:
                        print(f"  > Playing: {playback['track_name']} by {playback['artist_name']}")
                    else:
                        print("  > Not playing.")
                    time.sleep(5) 
                
                # Test toggle playback (user interaction)
                toggle_choice = input(f"\nDo you want to toggle playback for '{account_name}'? (y/n): ").lower()
                if toggle_choice == 'y':
                    client.toggle_playback()
                    time.sleep(2)
                    client.toggle_playback() # もう一度トグルして元に戻す（希望があれば）
                else:
                    print("Skipping playback toggle.")
            else:
                print(f"Failed to authenticate '{account_name}'. Token might be expired or invalid. Try running 'get_tokens.py' again.")
        
        # Test switching to next account via method
        if len(client.accounts_data) > 1:
            print("\n--- Testing switch_to_next_account() ---")
            initial_index = client.current_account_index
            print(f"Current active index: {initial_index}")
            if client.switch_to_next_account():
                print(f"Switched to next account successfully. New active index: {client.current_account_index}")
            else:
                print("Failed to switch to next account.")
            # 元に戻す
            if client.set_current_account(initial_index):
                print(f"Switched back to initial account: {client.current_account_index}")
            else:
                print("Failed to switch back.")

    print("\n--- Test Complete ---")