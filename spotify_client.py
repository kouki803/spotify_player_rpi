# spotify_client.py
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import config
import json
import os
import sys
import time

class SpotifyClient:
    def __init__(self, accounts_file='accounts.json'):
        self.accounts_file = accounts_file
        self.accounts_data = [] # Stores list of account dictionaries
        self.current_account_index = -1 # Index of the currently active account in accounts_data
        self.sp = None # Spotipy Spotify client instance
        self.sp_oauth = None # Spotipy SpotifyOAuth instance
        self.load_accounts() # Load accounts on initialization

    def load_accounts(self):
        """Loads account data from the JSON file."""
        if os.path.exists(self.accounts_file):
            try:
                with open(self.accounts_file, 'r') as f:
                    self.accounts_data = json.load(f)
                print(f"Loaded {len(self.accounts_data)} Spotify accounts.")
                # After loading, check if current_account_index is still valid
                if self.current_account_index >= len(self.accounts_data):
                    self.current_account_index = 0 if self.accounts_data else -1 # Reset if out of bounds
            except json.JSONDecodeError:
                print(f"Error decoding {self.accounts_file}. Starting with no accounts.")
                self.accounts_data = []
        else:
            print(f"No {self.accounts_file} found. Starting with no accounts.")
            self.accounts_data = []

    def _save_accounts(self):
        """Saves current account data to the JSON file."""
        with open(self.accounts_file, 'w') as f:
            json.dump(self.accounts_data, f, indent=4)
        print("Accounts saved.")

    def set_current_account(self, index):
        """
        Sets the specified account as the current active account and attempts to authenticate.
        Returns True on successful authentication, False otherwise.
        """
        if not self.accounts_data:
            print("No accounts available to set.")
            self.sp = None
            self.sp_oauth = None
            return False

        if 0 <= index < len(self.accounts_data):
            self.current_account_index = index
            return self._authenticate_current_account()
        else:
            print(f"Invalid account index: {index}. Cannot set current account.")
            self.sp = None
            self.sp_oauth = None
            return False

    def _authenticate_current_account(self):
        """
        Attempts to authenticate with the currently selected account using cached tokens or refreshing.
        Returns True on successful authentication, False otherwise.
        """
        if self.current_account_index == -1 or not self.accounts_data:
            self.sp = None
            self.sp_oauth = None
            return False

        account_info = self.accounts_data[self.current_account_index]
        user_name = account_info.get('name', f"User {self.current_account_index + 1}")
        print(f"Attempting to authenticate account: {user_name}")

        # Each account gets its own cache file based on its name
        cache_path = os.path.join(os.path.dirname(__file__), f'.spotify_cache_{user_name.replace(" ", "_")}')

        self.sp_oauth = SpotifyOAuth(
            client_id=config.SPOTIPY_CLIENT_ID,
            client_secret=config.SPOTIPY_CLIENT_SECRET,
            redirect_uri=config.SPOTIPY_REDIRECT_URI,
            scope=config.SCOPE,
            cache_path=cache_path,
            # show_dialog=True ensures user is prompted for approval every time they re-authenticate,
            # useful for adding multiple accounts via web_server.py
            show_dialog=True 
        )
        
        token_info = self.sp_oauth.get_cached_token()

        if token_info:
            if self.sp_oauth.is_token_expired(token_info):
                print(f"Access token for {user_name} expired, refreshing...")
                try:
                    token_info = self.sp_oauth.refresh_access_token(token_info['refresh_token'])
                    # Update token info in accounts_data and save
                    account_info.update({
                        "access_token": token_info['access_token'],
                        "expires_at": token_info['expires_at'],
                        "refresh_token": token_info['refresh_token'] # Refresh token might also change
                    })
                    self._save_accounts()
                except Exception as e:
                    print(f"Failed to refresh token for {user_name}: {e}")
                    token_info = None # Treat as authentication failure
            
            if token_info:
                self.sp = spotipy.Spotify(auth=token_info['access_token'])
                print(f"Spotify authentication successful for {user_name}.")
                return True
        
        print(f"Authentication failed for {user_name}. Token missing or invalid.")
        self.sp = None # Reset Spotify client on failure
        self.sp_oauth = None
        return False

    def add_new_account_token(self, user_name, access_token, refresh_token, expires_at):
        """
        Adds or updates an account with provided token info.
        This method is called by the web_server after successful OAuth.
        """
        new_account_data = {
            "name": user_name,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at
        }
        
        # Check if an account with this name already exists and update it
        found = False
        for i, acc in enumerate(self.accounts_data):
            if acc.get('name') == user_name:
                self.accounts_data[i] = new_account_data
                print(f"Updated existing account: {user_name}")
                found = True
                break
        if not found:
            self.accounts_data.append(new_account_data)
            print(f"Added new account: {user_name}")
        
        self._save_accounts()

    def delete_account(self, index):
        """Deletes an account by index and its associated cache file."""
        if 0 <= index < len(self.accounts_data):
            deleted_account_name = self.accounts_data[index].get('name', f"User {index+1}")
            del self.accounts_data[index]
            self._save_accounts()

            # Delete associated cache file
            cache_file = os.path.join(os.path.dirname(__file__), f'.spotify_cache_{deleted_account_name.replace(" ", "_")}')
            if os.path.exists(cache_file):
                os.remove(cache_file)
                print(f"Deleted cache file for {deleted_account_name}")
            print(f"Deleted account: {deleted_account_name}")
            return True
        return False

    def switch_to_next_account(self):
        """Switches to the next account in the list (for physical button)."""
        if not self.accounts_data:
            print("No accounts to switch. Add an account first.")
            self.sp = None
            self.sp_oauth = None
            return False
        
        next_index = (self.current_account_index + 1) % len(self.accounts_data)
        print(f"Attempting to switch to next account (index: {next_index})...")
        return self.set_current_account(next_index)

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
                print("Current account token might be invalid or expired. Attempting to re-authenticate current account.")
                self.set_current_account(self.current_account_index) # Try to re-authenticate
        except Exception as e:
            print(f"An unexpected error occurred toggling playback: {e}")
