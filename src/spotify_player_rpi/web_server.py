# web_server.py
from flask import Flask, render_template, request, redirect, url_for, session, make_response
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import spotify_player_rpi.config as config
import json
import os
import socket


# Flaskアプリケーションのインスタンスを生成

app = Flask(__name__, 
            template_folder=os.path.join(config.SELF_LIB_ROOT, 'templates'),
            static_folder=os.path.join(config.SELF_LIB_ROOT, 'static'))
app.secret_key = os.urandom(24) 

# File paths using config.PROJECT_ROOT
# accounts.json, current_account_index.txt, Spotipyキャッシュはプロジェクトのルートに配置
ACCOUNTS_FILE = os.path.join(config.PROJECT_ROOT, 'accounts.json')
CURRENT_ACCOUNT_INDEX_FILE = os.path.join(config.PROJECT_ROOT, 'current_account_index.txt')
SPOTIPY_CACHE_DIR = config.PROJECT_ROOT 

# --- Helper functions for account management ---
def get_oauth_instance(user_name):
    """
    ユーザー名に基づいてSpotifyOAuthインスタンスを取得または作成します。
    Client IDとClient Secretはconfigから読み込まれます。
    """
    client_id = config.SPOTIPY_CLIENT_ID
    client_secret = config.SPOTIPY_CLIENT_SECRET

    # Spotipyキャッシュファイルのパスを生成
    cache_path = os.path.join(SPOTIPY_CACHE_DIR, f'.spotify_cache_{user_name.replace(" ", "_")}')
    
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=config.SPOTIPY_REDIRECT_URI,
        scope=config.SCOPE,
        cache_path=cache_path,
        show_dialog=True # ユーザーが毎回承認を求められるようにする（複数アカウント追加時に便利）
    )

def load_accounts_data_from_file():
    """ユーザーアカウントデータをaccounts.jsonファイルからロードします。"""
    if os.path.exists(ACCOUNTS_FILE):
        try:
            # accounts.jsonはユーザーアカウントのリストのみを保持する前提
            with open(ACCOUNTS_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                else:
                    print(f"Warning: {ACCOUNTS_FILE} has unexpected format. Expected a list. Returning empty list.")
                    return []
        except json.JSONDecodeError:
            print(f"Warning: {ACCOUNTS_FILE} is corrupted or empty. Returning empty list.")
            return []
    return []

def save_accounts_data_to_file(user_accounts_data):
    """ユーザーアカウントデータをaccounts.jsonファイルに保存します。"""
    with open(ACCOUNTS_FILE, 'w') as f:
        json.dump(user_accounts_data, f, indent=4)
    print("User accounts saved via web server.")

def delete_user_account_and_cache(index):
    """指定されたインデックスのユーザーアカウントを削除し、関連するSpotipyキャッシュファイルも削除します。"""
    user_accounts = load_accounts_data_from_file()
    if 0 <= index < len(user_accounts):
        deleted_user_account_name = user_accounts[index].get('name', f"User {index+1}")
        del user_accounts[index]
        save_accounts_data_to_file(user_accounts)

        # 関連するSpotipyキャッシュファイルを削除
        cache_file = os.path.join(SPOTIPY_CACHE_DIR, f'.spotify_cache_{deleted_user_account_name.replace(" ", "_")}')
        if os.path.exists(cache_file):
            os.remove(cache_file)
            print(f"Deleted cache file for {deleted_user_account_name}")
        print(f"User account '{deleted_user_account_name}' deleted.")
        return True
    return False

def notify_daemon_current_account_change(index=None):
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

def get_ip_address():
    """Raspberry PiのローカルIPアドレスを取得します。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)) 
        ip_address = s.getsockname()[0]
        s.close()
        return ip_address
    except Exception:
        return "Unknown IP"


# --- Flask Routes ---
@app.route('/')
def index():
    """メイン設定ページを表示します。"""
    user_accounts = load_accounts_data_from_file()
    
    # configからClient IDとClient Secretが設定されているか確認
    app_keys_configured = bool(config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET)

    # current_account_index.txtから現在アクティブなアカウントのインデックスを読み込む
    current_active_idx = -1
    if os.path.exists(CURRENT_ACCOUNT_INDEX_FILE):
        try:
            with open(CURRENT_ACCOUNT_INDEX_FILE, 'r') as f:
                current_active_idx = int(f.read().strip())
        except (ValueError, IOError):
            pass 

    current_account_name = None
    if 0 <= current_active_idx < len(user_accounts):
        current_account_name = user_accounts[current_active_idx].get('name', f"User {current_active_idx+1}")

    pi_ip = get_ip_address()

    # テンプレートをレンダリングし、必要なデータを渡す
    return render_template('index.html', 
                            app_keys_configured=app_keys_configured,
                            user_accounts=user_accounts, 
                            current_account_name=current_account_name,
                            pi_ip=pi_ip)


@app.route('/add_user_account', methods=['GET', 'POST'])
def add_user_account():
    """新しいSpotifyユーザーアカウントを追加するためのページを表示または認証フローを開始します。"""
    # Client IDとClient Secretが設定されていない場合、エラーメッセージを表示
    if not (config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET):
        # テンプレート 'error_message.html' が別途必要
        return render_template('error_message.html', message="Client ID/Secret is not set in .env. Please configure it first.", redirect_url=url_for('index'))

    if request.method == 'POST':
        user_name = request.form['user_name'].strip()
        if not user_name:
            return "User account name cannot be empty!", 400

        # 認証中のユーザー名をセッションに保存し、認証後に取得できるようにする
        session['auth_user_name'] = user_name 

        # Spotifyの認証URLを生成し、ユーザーをリダイレクト
        sp_oauth = get_oauth_instance(user_name)
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    
    # GETリクエストの場合、ユーザーアカウント追加フォームを表示
    return render_template('add_user_account.html')

@app.route('/callback')
def callback():
    """Spotify認証後のコールバックURIを処理します。"""
    # セッションから認証中のユーザー名を取得
    user_name = session.pop('auth_user_name', None) 
    if not user_name:
        return "Authentication error: User name missing from session.", 400

    # Client IDとClient Secretが設定されていない場合、エラー
    if not (config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET):
        return "Authentication failed: App Client ID/Secret not set in .env.", 400

    # 認証インスタンスを再取得し、認証コードをアクセストークンと交換
    sp_oauth = get_oauth_instance(user_name)
    code = request.args.get('code')

    if not code:
        error = request.args.get('error', 'unknown error')
        return f"Authentication failed: {error}. <a href='{url_for('index')}'>Back to settings</a>", 500

    try:
        token_info = sp_oauth.get_access_token(code)
        
        # 既存のユーザーアカウントをロード
        user_accounts = load_accounts_data_from_file()
        found_index = -1
        # 同じ名前のアカウントがあれば更新、なければ追加
        for i, acc in enumerate(user_accounts):
            if acc.get('name') == user_name:
                found_index = i
                break
        
        # 新しいアカウントデータを作成
        new_user_account_data = {
            "name": user_name,
            "access_token": token_info['access_token'],
            "refresh_token": token_info['refresh_token'],
            "expires_at": token_info['expires_at']
        }

        if found_index != -1:
            user_accounts[found_index] = new_user_account_data
            print(f"Updated existing user account: {user_name}")
            notify_daemon_current_account_change(found_index) # メインデーモンに更新を通知
        else:
            user_accounts.append(new_user_account_data)
            print(f"Added new user account: {user_name}")
            notify_daemon_current_account_change(len(user_accounts) - 1) # メインデーモンに新規追加を通知
        
        # 更新されたユーザーアカウントリストを保存
        save_accounts_data_to_file(user_accounts)
        
        # メイン設定ページにリダイレクト
        return redirect(url_for('index'))

    except spotipy.exceptions.SpotifyException as e:
        return f"Spotify API Error during authentication: {e}. <a href='{url_for('index')}'>Back to settings</a>", 500
    except Exception as e:
        return f"An unexpected error occurred during authentication: {e}. <a href='{url_for('index')}'>Back to settings</a>", 500

@app.route('/set_current_account/<int:index>')
def set_current_account(index):
    """メインデーモンに、現在アクティブにするユーザーアカウントを通知します。"""
    user_accounts = load_accounts_data_from_file()
    if 0 <= index < len(user_accounts):
        notify_daemon_current_account_change(index)
        print(f"Set current user account index to {index} via web GUI.")
    else:
        print(f"Attempted to set invalid user account index {index}.")
    return redirect(url_for('index'))

@app.route('/delete_user_account/<int:index>')
def delete_user_account(index):
    """指定されたインデックスのユーザーアカウントを削除します。"""
    user_accounts = load_accounts_data_from_file()

    if 0 <= index < len(user_accounts):
        if delete_user_account_and_cache(index):
            # 削除されたアカウントが現在アクティブだった場合、デーモンの状態を更新
            current_active_idx = -1
            if os.path.exists(CURRENT_ACCOUNT_INDEX_FILE):
                try:
                    with open(CURRENT_ACCOUNT_INDEX_FILE, 'r') as f_read:
                        current_active_idx = int(f_read.read().strip())
                except (ValueError, IOError):
                    pass
            
            if current_active_idx == index: 
                notify_daemon_current_account_change(None) # アクティブアカウントをクリア
            elif current_active_idx > index:
                notify_daemon_current_account_change(current_active_idx - 1) # 削除によりインデックスがずれた場合、調整
            elif not load_accounts_data_from_file(): # 全てのアカウントが削除された場合
                 notify_daemon_current_account_change(None) 

        print(f"Deleted user account at index {index}.")
    return redirect(url_for('index'))


# --- Flask Web Server Startup (デバッグ/開発用) ---
if __name__ == '__main__':
    print("--- web_server.py Debug Test ---")
    print("Starting Flask web server on http://0.0.0.0:5000")
    print("Requires .env with Spotify credentials.")
    print(f"Access via http://{get_ip_address()}:5000") # 自身のIPアドレスを表示
    app.run(host='0.0.0.0', port=5000, debug=True)