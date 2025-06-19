import json
import os
import socket
import sys
from typing import Optional, List, Dict, Any, Union # 型ヒントに必要なモジュールをインポート

from flask import Flask, render_template, request, redirect, url_for, session, make_response, Response
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import spotify_player_rpi.config as config

import importlib.resources 


# Flaskアプリケーションのインスタンスを生成
app = Flask(__name__, 
            template_folder=importlib.resources.files('spotify_player_rpi').joinpath('templates'),
            static_folder=importlib.resources.files('spotify_player_rpi').joinpath('static'))
app.secret_key = os.urandom(24) 

# File paths using config.PROJECT_ROOT
ACCOUNTS_FILE: str = os.path.join(config.PROJECT_ROOT, 'accounts.json')
CURRENT_ACCOUNT_INDEX_FILE: str = os.path.join(config.PROJECT_ROOT, 'current_account_index.txt')
SPOTIPY_CACHE_DIR: str = config.PROJECT_ROOT 

# --- Helper functions for account management ---
def get_oauth_instance(user_name: str) -> SpotifyOAuth:
    """
    ユーザー名に基づいてSpotifyOAuthインスタンスを取得または作成します。
    Client IDとClient Secretはconfigから読み込まれます。
    """
    client_id: Optional[str] = config.SPOTIPY_CLIENT_ID
    client_secret: Optional[str] = config.SPOTIPY_CLIENT_SECRET

    # Spotipyキャッシュファイルのパスを生成
    cache_path: str = os.path.join(SPOTIPY_CACHE_DIR, f'.spotify_cache_{user_name.replace(" ", "_")}')
    
    # config.pyでClient ID/SecretがNoneになる可能性があるのでチェック
    if client_id is None or client_secret is None:
        raise ValueError("Spotify Client ID/Secret are not configured in .env.")

    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=config.SPOTIPY_REDIRECT_URI,
        scope=config.SCOPE,
        cache_path=cache_path,
        show_dialog=True, 
        listen_hostname='0.0.0.0'
    )

def load_accounts_data_from_file() -> List[Dict[str, Any]]:
    """ユーザーアカウントデータをaccounts.jsonファイルからロードします。"""
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, 'r') as f:
                data: Any = json.load(f) # ロードされるデータの可能性のある型
                if isinstance(data, list):
                    return data
                else:
                    print(f"WARNING: {ACCOUNTS_FILE} has unexpected format. Expected a list. Returning empty list.")
                    return []
        except json.JSONDecodeError:
            print(f"WARNING: {ACCOUNTS_FILE} is corrupted or empty. Returning empty list.")
            return []
    return []

def save_accounts_data_to_file(user_accounts_data: List[Dict[str, Any]]) -> None:
    """ユーザーアカウントデータをaccounts.jsonファイルに保存します。"""
    with open(ACCOUNTS_FILE, 'w') as f:
        json.dump(user_accounts_data, f, indent=4)
    print("User accounts saved via web server.")

def delete_user_account_and_cache(index: int) -> bool:
    """指定されたインデックスのユーザーアカウントを削除し、関連するSpotipyキャッシュファイルも削除します。"""
    user_accounts: List[Dict[str, Any]] = load_accounts_data_from_file()
    if 0 <= index < len(user_accounts):
        deleted_user_account_name: str = user_accounts[index].get('name', f"User {index+1}") 
        del user_accounts[index]
        save_accounts_data_to_file(user_accounts)

        # 関連するSpotipyキャッシュファイルを削除
        cache_file: str = os.path.join(SPOTIPY_CACHE_DIR, f'.spotify_cache_{deleted_user_account_name.replace(" ", "_")}') 
        if os.path.exists(cache_file):
            try:
                os.remove(cache_file)
                print(f"Deleted cache file for {deleted_user_account_name}")
            except Exception as e:
                print(f"Error removing cache file {cache_file}: {e}")
        print(f"User account '{deleted_user_account_name}' deleted.")
        return True
    return False

def notify_daemon_current_account_change(index: Optional[int] = None) -> None:
    """
    メインデーモンに、現在のアクティブなユーザーアカウントのインデックスを通知します。
    これはcurrent_account_index.txtファイルを通じて行われます。
    """
    try:
        if index is not None:
            with open(CURRENT_ACCOUNT_INDEX_FILE, 'w') as f:
                f.write(str(index))
            print(f"Daemon notified to switch to user account index: {index}")
        elif os.path.exists(CURRENT_ACCOUNT_INDEX_FILE):
            os.remove(CURRENT_ACCOUNT_INDEX_FILE) 
            print("Daemon notification file cleared (no active user account selected).")
    except Exception as e:
        print(f"Error notifying daemon: {e}")

def get_ip_address() -> str:
    """Raspberry PiのローカルIPアドレスを取得します。"""
    try:
        s: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)) 
        ip_address: str = s.getsockname()[0]
        s.close()
        return ip_address
    except Exception:
        return "Unknown IP"


# --- Flask Routes ---
@app.route('/')
def index() -> str: # render_templateはstrを返す
    """メイン設定ページを表示します。"""
    user_accounts: List[Dict[str, Any]] = load_accounts_data_from_file()
    
    app_keys_configured: bool = bool(config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET)

    current_active_idx: int = -1 
    if os.path.exists(CURRENT_ACCOUNT_INDEX_FILE):
        try:
            with open(CURRENT_ACCOUNT_INDEX_FILE, 'r') as f:
                current_active_idx = int(f.read().strip())
        except (ValueError, IOError):
            pass 

    current_account_name: Optional[str] = None 
    if 0 <= current_active_idx < len(user_accounts):
        current_account_name = user_accounts[current_active_idx].get('name', f"User {current_active_idx+1}")

    pi_ip: str = get_ip_address() 

    return render_template('index.html', 
                            app_keys_configured=app_keys_configured,
                            user_accounts=user_accounts, 
                            current_account_name=current_account_name,
                            pi_ip=pi_ip)


@app.route('/add_user_account', methods=['GET', 'POST'])
def add_user_account() -> Union[Response, str]: # redirectはResponse, render_templateはstr
    """新しいSpotifyユーザーアカウントを追加するためのページを表示または認証フローを開始します。"""
    if not (config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET):
        return render_template('error_message.html', message="Client ID/Secret is not set in .env. Please configure it first.", redirect_url=url_for('index'))

    if request.method == 'POST':
        user_name: str = request.form['user_name'].strip()
        if not user_name:
            return make_response("User account name cannot be empty!", 400) # make_responseはResponseを返す

        session['auth_user_name'] = user_name 

        sp_oauth: SpotifyOAuth = get_oauth_instance(user_name)
        auth_url: str = sp_oauth.get_authorize_url()
        return redirect(auth_url) # redirectはResponseを返す
    
    return render_template('add_user_account.html') # render_templateはstrを返す

@app.route('/callback')
def callback() -> Union[Response, str]: # redirectとmake_responseはResponse, render_templateはstr
    """Spotify認証後のコールバックURIを処理します。"""
    user_name: Optional[str] = session.pop('auth_user_name', None) 
    if not user_name:
        return make_response("Authentication error: User name missing from session.", 400)

    if not (config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET):
        return make_response("Authentication failed: App Client ID/Secret not set in .env.", 400)

    sp_oauth: SpotifyOAuth = get_oauth_instance(user_name)
    code: Optional[str] = request.args.get('code')

    if not code:
        error: str = request.args.get('error', 'unknown error') 
        return make_response(f"Authentication failed: {error}. <a href='{url_for('index')}'>Back to settings</a>", 400)

    try:
        token_info: Dict[str, Any] = sp_oauth.get_access_token(code)
        
        user_accounts: List[Dict[str, Any]] = load_accounts_data_from_file()
        found_index: int = -1 
        for i, acc in enumerate(user_accounts):
            if acc.get('name') == user_name:
                found_index = i
                break
        
        new_user_account_data: Dict[str, Any] = {
            "name": user_name,
            "access_token": token_info['access_token'],
            "refresh_token": token_info['refresh_token'],
            "expires_at": token_info['expires_at']
        }

        if found_index != -1:
            user_accounts[found_index] = new_user_account_data
            print(f"Updated existing user account: {user_name}")
            notify_daemon_current_account_change(found_index) 
        else:
            user_accounts.append(new_user_account_data)
            print(f"Added new user account: {user_name}")
            notify_daemon_current_account_change(len(user_accounts) - 1) 
        
        save_accounts_data_to_file(user_accounts)
        
        return redirect(url_for('index')) # redirectはResponseを返す

    except spotipy.exceptions.SpotifyException as e:
        return make_response(f"Spotify API Error during authentication: {e}. <a href='{url_for('index')}'>Back to settings</a>", 500)
    except Exception as e:
        return make_response(f"An unexpected error occurred during authentication: {e}. <a href='{url_for('index')}'>Back to settings</a>", 500)

@app.route('/set_current_account/<int:index>')
def set_current_account(index: int) -> Response: # redirectはResponseを返す
    """メインデーモンに、現在アクティブにするユーザーアカウントを通知します。"""
    user_accounts: List[Dict[str, Any]] = load_accounts_data_from_file()
    if 0 <= index < len(user_accounts):
        notify_daemon_current_account_change(index)
        print(f"Set current user account index to {index} via web GUI.")
    else:
        print(f"Attempted to set invalid user account index {index}.")
    return redirect(url_for('index'))

@app.route('/delete_user_account/<int:index>')
def delete_user_account(index: int) -> Response: # redirectはResponseを返す
    """指定されたインデックスのユーザーアカウントを削除します。"""
    user_accounts: List[Dict[str, Any]] = load_accounts_data_from_file()

    if 0 <= index < len(user_accounts):
        if delete_user_account_and_cache(index):
            current_active_idx: int = -1 
            if os.path.exists(CURRENT_ACCOUNT_INDEX_FILE):
                try:
                    with open(CURRENT_ACCOUNT_INDEX_FILE, 'r') as f_read:
                        current_active_idx = int(f_read.read().strip())
                except (ValueError, IOError):
                    pass
            
            if current_active_idx == index: 
                notify_daemon_current_account_change(None) 
            elif current_active_idx > index:
                notify_daemon_current_account_change(current_active_idx - 1) 
            elif not load_accounts_data_from_file(): 
                 notify_daemon_current_account_change(None) 

        print(f"Deleted user account at index {index}.")
    return redirect(url_for('index'))


# --- Flask Web Server Startup (デバッグ/開発用) ---
if __name__ == '__main__':
    ssl_cert_path: str = os.path.join(config.PROJECT_ROOT, 'ssl', 'server.crt')
    ssl_key_path: str = os.path.join(config.PROJECT_ROOT, 'ssl', 'server.key')

    if os.path.exists(ssl_cert_path) and os.path.exists(ssl_key_path):
        print("--- web_server.py Debug Test (HTTPS) ---")
        print(f"Starting Flask web server on https://0.0.0.0:5000") 
        print("Requires .env with Spotify credentials.")
        
        def get_local_ip_address() -> str: 
            try:
                s: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80)) 
                ip_address: str = s.getsockname()[0]
                s.close()
                return ip_address
            except Exception:
                return "Unknown IP"
        
        pi_ip: str = get_local_ip_address() 
        print(f"Access via https://{pi_ip}:5000") 
        print(f"Or via hostname: https://{socket.gethostname()}.local:5000 (if mDNS works and certificate CN matches hostname)") 

        app.run(
            host='0.0.0.0',
            port=5000, 
            debug=True,
            ssl_context=(ssl_cert_path, ssl_key_path) 
        )
    else:
        print("--- web_server.py Debug Test (HTTP) ---")
        print(f"WARNING: SSL certificate or key not found at {ssl_cert_path} / {ssl_key_path}")
        print("Falling back to HTTP. Redirect URIs for Spotify will likely fail without HTTPS.")
        print("Please generate them using openssl in the 'ssl' subdirectory of your project root.")
        print("Example command: openssl req -x509 -newkey rsa:4096 -nodes -out server.crt -keyout server.key -days 365 -subj \"/CN=your_hostname.local\"")
        
        def get_local_ip_address() -> str: 
            try:
                s: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80)) 
                ip_address: str = s.getsockname()[0]
                s.close()
                return ip_address
            except Exception:
                return "Unknown IP"
        
        pi_ip: str = get_local_ip_address() 
        print(f"Starting Flask web server on http://0.0.0.0:5000") 
        print(f"Access via http://{pi_ip}:5000")
        print(f"Or via hostname: http://{socket.gethostname()}.local:5000")

        app.run(
            host='0.0.0.0',
            port=5000,
            debug=True
        )