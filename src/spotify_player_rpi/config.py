import os
from dotenv import load_dotenv

# .env ファイルをロード
load_dotenv() 

# ProjectのPath
# poetryのライブラリパスの二階層上をROOTに
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SELF_LIB_ROOT = os.path.dirname(os.path.abspath(__file__))

# Spotify API Credentials 
SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = 'http://127.0.0.1:8888/callback'

if not SPOTIPY_CLIENT_ID or not SPOTIPY_CLIENT_SECRET:
    raise ValueError("Spotify Client ID and Client Secret must be set in the .env file in the project root.")

# Spotify API Scopes
SCOPE = "user-read-playback-state user-modify-playback-state user-read-currently-playing"

# GPIO Pin Configuration (BCM numbering)
BUTTON_PLAY_PAUSE_PIN = 23
BUTTON_SWITCH_ACCOUNT_PIN = 24
BUTTON_DEBOUNCE_TIME = 300 # ボタンのチャタリング防止時間 (ms)


# Web Server Settings
WEB_SERVER_LIFETIME = 300

if __name__ == '__main__':
    print("--- config.py Debug Test ---")
    print(f'PROJECT_ROOT: {PROJECT_ROOT}')
    print(f'SELF_LIB_ROOT: {SELF_LIB_ROOT}')
    print(f"SPOTIPY_CLIENT_ID: {SPOTIPY_CLIENT_ID if SPOTIPY_CLIENT_ID else 'NOT SET'}")
    print(f"SPOTIPY_CLIENT_SECRET: {'***' if SPOTIPY_CLIENT_SECRET else 'NOT SET'}")
    print(f"SPOTIPY_REDIRECT_URI: {SPOTIPY_REDIRECT_URI}")
    print("--- Test Complete ---")