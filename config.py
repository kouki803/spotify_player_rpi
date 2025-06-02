# config.py

# Spotify API Credentials
# Replace with your actual Client ID and Client Secret from Spotify Developer Dashboard
SPOTIPY_CLIENT_ID = 'YOUR_SPOTIPY_CLIENT_ID'
SPOTIPY_CLIENT_SECRET = 'YOUR_SPOTIPY_CLIENT_SECRET'
SPOTIPY_REDIRECT_URI = 'http://localhost:8888/callback' # Must match your Spotify App settings

# Spotify API Scopes
# user-read-playback-state: Read current playback state
# user-modify-playback-state: Control playback (play/pause)
# user-read-currently-playing: Read currently playing track
SCOPE = "user-read-playback-state user-modify-playback-state user-read-currently-playing"

# e-ink display settings
# Adjust path if your Waveshare lib directory is structured differently
# Assumes 'lib' directory is in the same directory as this script.
# Make sure to update this if your 'lib' directory is somewhere else.
E_PAPER_LIB_PATH = './lib/'

# GPIO Pin Configuration (BCM numbering)
BUTTON_PLAY_PAUSE_PIN = 23      # Example: GPIO 23 (Physical pin 16)
BUTTON_SWITCH_ACCOUNT_PIN = 24  # Example: GPIO 24 (Physical pin 18)
# BUTTON_SETTINGS_TOGGLE_PIN = 25 # 常時Webサーバーのため不要
