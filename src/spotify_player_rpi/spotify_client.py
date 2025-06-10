# spotify_client.py
import spotipy
from spotipy.oauth2 import SpotifyOAuth

import spotify_player_rpi.config as config # config.py から認証情報を読み込む

import json
import os
import sys
import time

class SpotifyClient:
    def __init__(self, accounts_file='accounts.json'):
        self.accounts_file = accounts_file
        # accounts_data はユーザーアカウントのリストのみ
        self.accounts_data = [] 
        self.current_account_index = -1
        self.sp = None
        self.sp_oauth = None
        self._load_accounts() 

    def _load_accounts(self):
        """Loads user account data from the JSON file."""
        if os.path.exists(self.accounts_file):
            try:
                with open(self.accounts_file, 'r') as f:
                    # accounts.json がユーザーアカウントのリストのみを保持する前提
                    self.accounts_data = json.load(f)
                print(f"Loaded {len(self.accounts_data)} Spotify user accounts.")
            except json.JSONDecodeError:
                print(f"Error decoding {self.accounts_file}. Starting with no user accounts.")
                self.accounts_data = []
        else:
            print(f"No {self.accounts_file} found. Starting with no user accounts.")
            self.accounts_data = []
        
        # After loading, check if current_account_index is still valid
        if self.current_account_index >= len(self.accounts_data):
            self.current_account_index = 0 if self.accounts_data else -1 

    def _save_accounts(self):
        """Saves current user account data to the JSON file."""
        with open(self.accounts_file, 'w') as f:
            json.dump(self.accounts_data, f, indent=4)
        print("User accounts saved.")


    def set_current_account(self, index):
        """
        Sets the specified user account as the current active account and attempts to authenticate.
        Client ID/Secretはconfig.pyから自動的に読み込まれる。
        Returns True on successful authentication, False otherwise.
        """
        # アプリケーションキーがconfig.pyからロードされているかここで直接チェック
        if not (config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET):
            print("Spotify Client ID/Secret not set in .env. Cannot authenticate user account.")
            self.sp = None
            self.sp_oauth = None
            return False

        if not self.accounts_data: # accounts_data は user_accounts のリストになった
            print("No user accounts available to set.")
            self.sp = None
            self.sp_oauth = None
            return False

        if 0 <= index < len(self.accounts_data):
            self.current_account_index = index
            return self._authenticate_current_account()
        else:
            print(f"Invalid user account index: {index}. Cannot set current account.")
            self.sp = None
            self.sp_oauth = None
            return False

    def _authenticate_current_account(self):
        """
        Attempts to authenticate with the currently selected user account using cached tokens or refreshing.
        Returns True on successful authentication, False otherwise.
        """
        if self.current_account_index == -1 or not self.accounts_data:
            self.sp = None
            self.sp_oauth = None
            return False

        user_account_info = self.accounts_data[self.current_account_index] # accounts_data は user_accounts のリストになった
        user_name = user_account_info.get('name', f"User {self.current_account_index + 1}")
        print(f"Attempting to authenticate user account: {user_name}")

        # Client ID と Client Secret を config.py から直接取得
        client_id = config.SPOTIPY_CLIENT_ID
        client_secret = config.SPOTIPY_CLIENT_SECRET
        
        if not client_id or not client_secret:
            print("App Client ID/Secret missing from .env. Cannot proceed with user authentication.")
            self.sp = None
            self.sp_oauth = None
            return False

        cache_path = os.path.join(os.path.dirname(__file__), f'.spotify_cache_{user_name.replace(" ", "_")}')

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
            if self.sp_oauth.is_token_expired(token_info):
                print(f"Access token for {user_name} expired, refreshing...")
                try:
                    token_info = self.sp_oauth.refresh_access_token(token_info['refresh_token'])
                    user_account_info.update({
                        "access_token": token_info['access_token'],
                        "expires_at": token_info['expires_at'],
                        "refresh_token": token_info['refresh_token']
                    })
                    self._save_accounts()
                except Exception as e:
                    print(f"Failed to refresh token for {user_name}: {e}")
                    token_info = None
            
            if token_info:
                self.sp = spotipy.Spotify(auth=token_info['access_token'])
                print(f"Spotify authentication successful for {user_name}.")
                return True
        
        print(f"Authentication failed for {user_name}. Token missing or invalid.")
        self.sp = None
        self.sp_oauth = None
        return False
    
    def add_user_account_token(self, user_name, access_token, refresh_token, expires_at):
        """
        Adds or updates a user account with provided token info.
        This method is called by the web_server after successful OAuth for a user.
        """
        # アプリケーションキーがconfig.pyからロードされているかここで直接チェック
        if not (config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET):
            print("Cannot add user account: Spotify Client ID/Secret not set in .env.")
            return False # 追加できない場合はFalseを返す

        new_user_account_data = {
            "name": user_name,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at
        }
        
        found = False
        for i, acc in enumerate(self.accounts_data): # accounts_data は user_accounts のリストになった
            if acc.get('name') == user_name:
                self.accounts_data[i] = new_user_account_data
                print(f"Updated existing user account: {user_name}")
                found = True
                break
        if not found:
            self.accounts_data.append(new_user_account_data)
            print(f"Added new user account: {user_name}")
        
        self._save_accounts()
        return True # 正常に追加されたことを示す

    def delete_user_account(self, index):
        """Deletes a user account by index and its associated cache file."""
        if 0 <= index < len(self.accounts_data): # accounts_data は user_accounts のリストになった
            deleted_user_account_name = self.accounts_data[index].get('name', f"User {index+1}")
            del self.accounts_data[index]
            self._save_accounts()

            cache_file = os.path.join(os.path.dirname(__file__), f'.spotify_cache_{deleted_user_account_name.replace(" ", "_")}')
            if os.path.exists(cache_file):
                os.remove(cache_file)
                print(f"Deleted cache file for {deleted_user_account_name}")
            print(f"Deleted user account: {deleted_user_account_name}")
            return True
        return False

    def switch_to_next_account(self):
        """Switches to the next user account in the list (for physical button)."""
        # アプリケーションキーがconfig.pyからロードされているかここで直接チェック
        if not (config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET):
            print("App Client ID/Secret not set in .env. Cannot switch user accounts.")
            self.sp = None
            self.sp_oauth = None
            return False

        if not self.accounts_data: # accounts_data は user_accounts のリストになった
            print("No user accounts to switch. Add an account first.")
            self.sp = None
            self.sp_oauth = None
            return False
        
        next_index = (self.current_account_index + 1) % len(self.accounts_data)
        print(f"Attempting to switch to next user account (index: {next_index})...")
        return self.set_current_account(next_index)

    # get_current_playback, toggle_playback は変更なし (self.sp を利用)
    # ただし、get_current_playbackの最初でClient ID/Secretの存在チェックを追加
    def get_current_playback(self):
        """Retrieves the current playback state from Spotify API."""
        if self.sp is None:
            return {'is_playing': False, 'track_name': None, 'artist_name': None, 'track_url': None}
        # ... (以下、既存のロジック) ...
        try:
            # ... (既存のアクセストークン更新ロジック) ...
            # accounts_data["user_accounts"][self.current_account_index].update(...) -> self.accounts_data[self.current_account_index].update(...)
            self.accounts_data[self.current_account_index].update({
                    "access_token": token_info['access_token'],
                    "expires_at": token_info['expires_at'],
                    "refresh_token": token_info['refresh_token']
                })
            # ...
        except spotipy.exceptions.SpotifyException as e:
            # ...
        except Exception as e:
            # ...

    def toggle_playback(self):
        if not (config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET):
            print("Spotify Client ID/Secret not set. Cannot toggle playback.")
            return
        if self.sp is None:
            print("Spotify client not authenticated. Cannot toggle playback.")
            return
        # ... (以下、既存のロジック) ...