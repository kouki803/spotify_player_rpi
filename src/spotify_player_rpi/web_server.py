# web_server.py
from flask import Flask, render_template, request, redirect, url_for, session, make_response
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import spotify_player_rpi.config as config
import json
import os

app = Flask(__name__)
# Flask's secret_key is crucial for session security (e.g., flash messages, CSRF protection).
# Use a strong, random key in production. os.urandom(24) is good for simple setups.
app.secret_key = os.urandom(24) 

# File paths
ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), 'accounts.json')
CURRENT_ACCOUNT_INDEX_FILE = os.path.join(os.path.dirname(__file__), 'current_account_index.txt')
SPOTIPY_CACHE_DIR = os.path.dirname(__file__) # Directory where spotipy cache files are stored

# --- Helper functions for account management ---
def get_oauth_instance(user_name):
    """Retrieves or creates a SpotifyOAuth instance for a given user name."""
    cache_path = os.path.join(SPOTIPY_CACHE_DIR, f'.spotify_cache_{user_name.replace(" ", "_")}')
    # show_dialog=True ensures the user is always prompted to authorize, which is good
    # when adding multiple distinct accounts.
    return SpotifyOAuth(
        client_id=config.SPOTIPY_CLIENT_ID,
        client_secret=config.SPOTIPY_CLIENT_SECRET,
        redirect_uri=config.SPOTIPY_REDIRECT_URI,
        scope=config.SCOPE,
        cache_path=cache_path,
        show_dialog=True 
    )

def load_accounts():
    """Loads all registered Spotify accounts from accounts.json."""
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: {ACCOUNTS_FILE} is corrupted or empty. Starting with no accounts.")
            return []
    return []

def save_accounts(accounts_data):
    """Saves the current list of Spotify accounts to accounts.json."""
    with open(ACCOUNTS_FILE, 'w') as f:
        json.dump(accounts_data, f, indent=4)
    print("Accounts saved via web server.")

def delete_account_and_cache(index):
    """Deletes an account by index and its associated spotipy cache file."""
    accounts = load_accounts()
    if 0 <= index < len(accounts):
        deleted_account_name = accounts[index].get('name', f"User {index+1}")
        del accounts[index]
        save_accounts(accounts)

        # Delete associated spotipy cache file
        cache_file = os.path.join(SPOTIPY_CACHE_DIR, f'.spotify_cache_{deleted_account_name.replace(" ", "_")}')
        if os.path.exists(cache_file):
            os.remove(cache_file)
            print(f"Deleted cache file for {deleted_account_name}")
        print(f"Account '{deleted_account_name}' deleted.")
        return True
    return False

def notify_daemon_current_account_change(index=None):
    """Notifies the main daemon about the current active account index."""
    try:
        if index is not None:
            with open(CURRENT_ACCOUNT_INDEX_FILE, 'w') as f:
                f.write(str(index))
            print(f"Daemon notified to switch to account index: {index}")
        elif os.path.exists(CURRENT_ACCOUNT_INDEX_FILE):
            os.remove(CURRENT_ACCOUNT_INDEX_FILE) # Clear notification if no account is selected
            print("Daemon notification file cleared (no active account selected).")
    except Exception as e:
        print(f"Error notifying daemon: {e}")

# --- Flask Routes ---
@app.route('/')
def index():
    accounts = load_accounts()
    
    # Determine which account is currently active from accounts.json (if set)
    # The current_account_index.txt is read by the daemon, not necessarily by the web_server.
    # To show the active account in the GUI, we'd need a mechanism for the daemon to tell the GUI,
    # or the GUI assumes the last set account is active. For simplicity, we can assume the
    # current_account_index.txt reflects the daemon's active account.
    current_active_idx = -1
    if os.path.exists(CURRENT_ACCOUNT_INDEX_FILE):
        try:
            with open(CURRENT_ACCOUNT_INDEX_FILE, 'r') as f:
                current_active_idx = int(f.read().strip())
        except (ValueError, IOError):
            pass # File might be empty or corrupted

    current_account_name = None
    if 0 <= current_active_idx < len(accounts):
        current_account_name = accounts[current_active_idx].get('name', f"User {current_active_idx+1}")

    # config を直接テンプレートに渡す (WEB_SERVER_LIFETIME は不要だが、安全のためそのまま渡す)
    return render_template('index.html', accounts=accounts, current_account_name=current_account_name, config=config)

@app.route('/add_account', methods=['GET', 'POST'])
def add_account():
    if request.method == 'POST':
        user_name = request.form['user_name'].strip()
        if not user_name:
            return "Account name cannot be empty!", 400

        # Store user_name in session to retrieve after Spotify redirect
        session['auth_user_name'] = user_name 

        sp_oauth = get_oauth_instance(user_name)
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    
    return render_template('add_account.html')

@app.route('/callback')
def callback():
    user_name = session.pop('auth_user_name', None) # Retrieve and remove from session
    if not user_name:
        return "Authentication error: User name missing from session.", 400

    sp_oauth = get_oauth_instance(user_name) # Get instance for the user
    code = request.args.get('code') # Get authorization code from Spotify redirect

    if not code:
        error = request.args.get('error', 'unknown error')
        return f"Authentication failed: {error}. Please try again. <a href='{url_for('index')}'>Back to settings</a>", 400

    try:
        token_info = sp_oauth.get_access_token(code) # Exchange code for tokens
        
        # Add or update account info in accounts.json
        accounts = load_accounts()
        found_index = -1
        for i, acc in enumerate(accounts):
            if acc.get('name') == user_name:
                found_index = i
                break
        
        new_account_data = {
            "name": user_name,
            "access_token": token_info['access_token'],
            "refresh_token": token_info['refresh_token'],
            "expires_at": token_info['expires_at']
        }

        if found_index != -1:
            accounts[found_index] = new_account_data
            print(f"Updated existing account: {user_name}")
            notify_daemon_current_account_change(found_index) # Notify daemon to re-authenticate this account
        else:
            accounts.append(new_account_data)
            print(f"Added new account: {user_name}")
            # Automatically set the newly added account as active for the daemon
            notify_daemon_current_account_change(len(accounts) - 1) 
        
        save_accounts(accounts)
        
        return redirect(url_for('index'))

    except spotipy.exceptions.SpotifyException as e:
        return f"Spotify API Error during authentication: {e}. <a href='{url_for('index')}'>Back to settings</a>", 500
    except Exception as e:
        return f"An unexpected error occurred during authentication: {e}. <a href='{url_for('index')}'>Back to settings</a>", 500

@app.route('/set_current_account/<int:index>')
def set_current_account(index):
    accounts = load_accounts()
    if 0 <= index < len(accounts):
        notify_daemon_current_account_change(index)
        print(f"Set current account index to {index} via web GUI.")
    else:
        print(f"Attempted to set invalid account index {index}.")
    return redirect(url_for('index'))

@app.route('/delete_account/<int:index>')
def delete_account(index):
    accounts = load_accounts()
    if 0 <= index < len(accounts):
        if delete_account_and_cache(index):
            # If the deleted account was active, clear daemon's active account
            current_active_idx = -1
            if os.path.exists(CURRENT_ACCOUNT_INDEX_FILE):
                try:
                    with open(CURRENT_ACCOUNT_INDEX_FILE, 'r') as f_read:
                        current_active_idx = int(f_read.read().strip())
                except (ValueError, IOError):
                    pass
            
            if current_active_idx == index: # If the deleted account was the active one
                notify_daemon_current_account_change(None) # Notify daemon to clear active account
            elif current_active_idx > index: # If an account before the active one was deleted
                notify_daemon_current_account_change(current_active_idx - 1) # Adjust daemon's index
            # If accounts list is empty after deletion, ensure daemon knows
            elif not load_accounts():
                 notify_daemon_current_account_change(None) # Notify daemon no accounts are left

        print(f"Deleted account at index {index}.")
    return redirect(url_for('index'))

# --- Flask Web Server Startup ---
if __name__ == '__main__':
    # デバッグ用途なので debug=True に設定
    # production環境では False にし、GunicornやuWSGIなどのWSGIサーバーを使うべき
    app.run(host='0.0.0.0', port=5000, debug=True)
