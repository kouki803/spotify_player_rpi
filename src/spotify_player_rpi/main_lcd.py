from spotify_player_rpi.display.AQM1602I2C import AQM1602I2C
from spotify_player_rpi.spotify_client import SpotifyClient
import spotify_player_rpi.config as config


def main():
    # LCDの初期化

    lcd = AQM1602I2C()
    lcd.message("Starting...\nPlease wait")
    
    # Spotifyクライアントの初期化
    spotify_client = SpotifyClient(
        client_id=config.SPOTIFY_CLIENT_ID,
        client_secret=config.SPOTIFY_CLIENT_SECRET,
        redirect_uri=config.SPOTIFY_REDIRECT_URI,
        scope="user-read-playback-state"
    )
    
    # 再生情報の取得とLCD表示
    playback_info = spotify_client.get_current_playback()
    
    if playback_info and playback_info.is_playing:
        track_name = playback_info.item.name
        artists = ", ".join(artist.name for artist in playback_info.item.artists)
        display_text = f"Playing:\n{track_name}\nby {artists}"
    else:
        display_text = "No track is\ncurrently playing."
    
    lcd.message(display_text)