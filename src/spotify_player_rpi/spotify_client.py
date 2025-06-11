# spotify_client.py
import json
import os
import time

import spotipy
from spotipy.oauth2 import SpotifyOAuth

import spotify_player_rpi.config as config # config.py からAPI認証情報を読み込む


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

    # get_current_playback, toggle_playback は変更なし (self.sp を利用)
    # ただし、get_current_playbackの最初でClient ID/Secretの存在チェックを追加
    def get_current_playback(self):
        """Retrieves the current playback state from Spotify API."""
        if self.sp is None:
            return {'is_playing': False, 'track_name': None, 'artist_name': None, 'track_url': None}
        
        try:
            # Check token expiration and refresh if necessary before making API call
            token_info = self.sp_oauth.get_cached_token()
            if token_info and self.sp_oauth.is_token_expired(token_info):
                print("Access token expired during playback check, refreshing...")
                token_info = self.sp_oauth.refresh_access_token(token_info['refresh_token'])
                self.sp = spotipy.Spotify(auth=token_info['access_token'])
                # Update accounts_data with refreshed token info
                self.accounts_data[self.current_account_index].update({
                    "access_token": token_info['access_token'],
                    "expires_at": token_info['expires_at'],
                    "refresh_token": token_info['refresh_token']
                })
                self._save_accounts()

            playback = self.sp.current_playback()
            if playback and playback['is_playing']:
                track = playback['item']
                track_name = track['name']
                artist_name = ", ".join([artist['name'] for artist in track['artists']])
                track_url = track['external_urls']['spotify']
                return {
                    'track_name': track_name,
                    'artist_name': artist_name,
                    'track_url': track_url,
                    'is_playing': True
                }
            elif playback and not playback['is_playing']:
                return {'is_playing': False, 'track_name': None, 'artist_name': None, 'track_url': None}
            else: # No playback found
                return {'is_playing': False, 'track_name': None, 'artist_name': None, 'track_url': None}
        except spotipy.exceptions.SpotifyException as e:
            print(f"Spotify API Error during playback check: {e}")
            if "expired token" in str(e).lower() or "invalid_grant" in str(e).lower():
                print("Current account token might be invalid or expired. Attempting to re-authenticate current account.")
                self.set_current_account(self.current_account_index) # Try to re-authenticate
            self.sp = None # Ensure sp is None if authentication fails
            return {'is_playing': False, 'track_name': None, 'artist_name': None, 'track_url': None}
        except Exception as e:
            print(f"An unexpected error occurred during playback check: {e}")
            self.sp = None
            return {'is_playing': False, 'track_name': None, 'artist_name': None, 'track_url': None}
         
    def toggle_playback(self):
        """Toggles playback (play/pause) on Spotify."""
        if self.sp is None:
            print("Spotify client not authenticated. Cannot toggle playback.")
            return

        try:
            playback = self.sp.current_playback()
            if playback and playback['is_playing']:
                self.sp.pause_playback()
                print("Playback paused.")
            else:
                self.sp.start_playback()
                print("Playback started/resumed.")
        except spotipy.exceptions.SpotifyException as e:
            print(f"Spotify API Error toggling playback: {e}")
            if "expired token" in str(e).lower() or "invalid_grant" in str(e).lower():
                print("Current user account token might be invalid or expired. Attempting to re-authenticate current account.")
                self.set_current_account(self.current_account_index)
        except Exception as e:
            print(f"An unexpected error occurred toggling playback: {e}")