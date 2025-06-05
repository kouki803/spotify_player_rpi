import os
from dotenv import load_dotenv

# .env ファイルをロード
load_dotenv() 

# Spotify API Credentials 
SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = 'http://127.0.0.1:8888/callback'

if not SPOTIPY_CLIENT_ID or not SPOTIPY_CLIENT_SECRET:
    raise ValueError("Spotify Client ID and Client Secret must be set in the .env file in the project root.")

# Spotify API Scopes
SCOPE = "user-read-playback-state user-modify-playback-state user-read-currently-playing"

# e-ink display settings
E_PAPER_LIB_PATH = './lib/'

# GPIO Pin Configuration (BCM numbering)
BUTTON_PLAY_PAUSE_PIN = 23
BUTTON_SWITCH_ACCOUNT_PIN = 24

# Web Server Settings
WEB_SERVER_LIFETIME = 300