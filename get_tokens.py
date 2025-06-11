import os
import sys
import json
import time
from pprint import pprint

from spotify_player_rpi import config
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime

print("--- Spotify Token Retrieval Script ---")
ACCOUNTS_FILE = os.path.join(config.PROJECT_ROOT, 'accounts.json')


def load_accounts_data():
    """accounts.jsonからデータをロードする。ファイルが存在しない場合は空リストを返す。"""
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                else:
                    print(f"WARNING: {ACCOUNTS_FILE} has unexpected format. Expected a list. Returning empty list.")
                    return []
        except json.JSONDecodeError:
            print(f"WARNING: {ACCOUNTS_FILE} is corrupted. Returning empty list.")
            return []
    return []

def save_accounts_data(data):
    """accounts.jsonにデータを保存する。"""
    try:
        with open(ACCOUNTS_FILE, 'w') as f:
            json.dump(data, f, indent=2) # indent=2で見やすいように整形
        print(f"\nINFO: Successfully saved tokens to {ACCOUNTS_FILE}")
    except Exception as e:
        print(f"ERROR: Failed to save accounts data to {ACCOUNTS_FILE}: {e}")


print("--- Spotify Token Retrieval Script ---")

# .env ファイルの存在を確認
dotenv_path = os.path.join(config.PROJECT_ROOT, '.env')
if not os.path.exists(dotenv_path):
    print(f"ERROR: .env file not found at {dotenv_path}. Please create it and set Client ID/Secret.")
    sys.exit(1)

CLIENT_ID = config.SPOTIPY_CLIENT_ID
CLIENT_SECRET = config.SPOTIPY_CLIENT_SECRET
# このスクリプトはlocalhostで動作するので、リダイレクトURIもlocalhostに設定
REDIRECT_URI = 'http://127.0.0.1:8888/callback' 
SCOPE = config.SCOPE

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: SPOTIPY_CLIENT_ID or SPOTIPY_CLIENT_SECRET not found in .env.")
    print("Please ensure they are set in your .env file in the project root.")
    sys.exit(1)

print(f"INFO: Using Client ID: {CLIENT_ID}")
print(f"INFO: Using Redirect URI: {REDIRECT_URI}")
print(f"INFO: Using Scope: {SCOPE}")

# --- デバッグ出力 ---
# cache_path の最終的な値を確認
user_name_placeholder = "test_user" # cache_path構築時の仮のユーザー名
test_cache_path_format = os.path.join(config.PROJECT_ROOT, f'.spotify_cache_{user_name_placeholder.replace(" ", "_")}')
print(f"DEBUG: Expected cache_path format: {test_cache_path_format}")
# --- デバッグ出力ここまで ---

# SpotifyOAuthインスタンスを作成
# cache_path を指定することで、spotipyが自動的にキャッシュファイルを保存・読み込みます
sp_oauth = SpotifyOAuth(client_id=CLIENT_ID,
                        client_secret=CLIENT_SECRET,
                        redirect_uri=REDIRECT_URI,
                        scope=SCOPE,
                        cache_path=os.path.join(config.PROJECT_ROOT, f'.spotify_cache_{time.time()}')) # ★重要: ここを元に戻す

# 注意: 上のcache_pathはテスト用。ユーザー名で特定するため、後で正確なcache_pathを使う。

auth_url = sp_oauth.get_authorize_url()
print("\n--- Authorization Step ---")
print("1. Please navigate to this URL in your web browser:")
print(f"\n{auth_url}\n")
print("2. Log in with your Spotify account and authorize the application.")
print("3. After successful authorization, your browser will be redirected to a 'This site can't be reached' or 'Connection refused' page.")
print("4. Copy the FULL URL from your browser's address bar (it will start with 'http://127.0.0.1:8888/callback?code=...')")

response_url = input("\n5. Paste the copied URL here and press Enter: ")

try:
    code = sp_oauth.parse_response_code(response_url)
    print("DEBUG: Successfully parsed response code from URL.")

    # この get_access_token() 呼び出しが成功するかを調べる
    token_info = sp_oauth.get_access_token(code) 
    print("DEBUG: Successfully called get_access_token() and received token_info.")

    print("\n--- Successfully Retrieved Tokens! ---")
    print(f"Access Token:   {token_info['access_token']}")
    print(f"Refresh Token:  {token_info['refresh_token']}")
    print(f"Expires At (Unix): {token_info['expires_at']}")
    expires_datetime = datetime.fromtimestamp(token_info['expires_at'])
    print(f"Expires At (Local Time): {expires_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # --- accounts.json に自動保存するロジック ---
    account_name = input("Enter a name for this account (e.g., 'My Main Account', 'Family Member'): ").strip()
    if not account_name:
        account_name = f"Unnamed Account {int(time.time())}"
        print(f"No name entered, using default: {account_name}")

    user_accounts = load_accounts_data()
    
    found = False
    for i, account in enumerate(user_accounts):
        if account.get("name") == account_name:
            user_accounts[i] = {
                "name": account_name,
                "access_token": token_info['access_token'],
                "refresh_token": token_info['refresh_token'],
                "expires_at": token_info['expires_at']
            }
            print(f"INFO: Updated existing account '{account_name}'.")
            found = True
            break
    
    if not found:
        user_accounts.append({
            "name": account_name,
            "access_token": token_info['access_token'],
            "refresh_token": token_info['refresh_token'],
            "expires_at": token_info['expires_at']
        })
        print(f"INFO: Added new account '{account_name}'.")

    save_accounts_data(user_accounts)

    # --- spotipyのキャッシュファイルを適切に保存する ---
    final_cache_path = os.path.join(config.PROJECT_ROOT, f'.spotify_cache_{account_name.replace(" ", "_")}')
    try:
        with open(final_cache_path, 'w') as f:
            json.dump(token_info, f, indent=2)
        print(f"INFO: Manually confirmed cache file saved to {final_cache_path}")
    except Exception as e:
        print(f"ERROR: Failed to manually save cache file to {final_cache_path}: {e}")

    # 古いSpotipyキャッシュファイルを削除
    cache_dir = config.PROJECT_ROOT
    for f_name in os.listdir(cache_dir):
        if f_name.startswith('.spotify_cache_') and f_name != os.path.basename(final_cache_path): # 今作ったファイルは消さない
            try:
                os.remove(os.path.join(cache_dir, f_name))
                print(f"INFO: Removed old cache file: {f_name}")
            except Exception as e:
                print(f"ERROR: Failed to remove old cache file {f_name}: {e}")

    print("\n--- Setup Complete ---")
    print("You can now run the main daemon and web server. Remember to use the Web UI to select an active account if you have multiple.")


except Exception as e:
    print(f"\nERROR: Failed to retrieve or save tokens. Specific error: {e}")
    print("Please ensure you copied the full redirected URL correctly.")
    print("Also check your Client ID/Secret and Redirect URI in Spotify Developer Dashboard (http://127.0.0.1:8888/callback is needed for this script).")

print("\n--- Script Finished ---")