# main_daemon.py
import time
import qrcode
from PIL import Image, ImageDraw, ImageFont
import RPi.GPIO as GPIO
import spotify_player_rpi.config as config
from spotify_player_rpi.display_manager import DisplayManager
from spotify_player_rpi.spotify_client import SpotifyClient
import os
import json
# import subprocess # Webサーバーの制御をしないため不要
# import signal     # Webサーバーの制御をしないため不要
# import import socket     # Webサーバー起動時のIP表示が不要

# --- Global Variables ---
current_track_info = {"track_name": None, "artist_name": None, "track_url": None}
display_sleeping = False
last_display_update_time = time.time()
display_manager = None
spotify_client = None

# Web server control variablesは削除

# --- Helper Functions ---
# get_ip_address 関数は、Webサーバー起動時のディスプレイ表示に使われていたので、
# 不要であれば削除しても良い。ここでは削除する前提で進める。
# def get_ip_address():
#    ...

def generate_qr_code(data):
    """Generates a QR code image from given data."""
    if not data:
        return None
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=4, # Adjust size as needed for e-ink display
        border=1,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img.convert("1") # Convert to 1-bit grayscale for e-ink

# --- GPIO Callbacks ---
def play_pause_button_callback(channel):
    global spotify_client
    print(f"Play/Pause button pressed on GPIO {channel}")
    if spotify_client:
        spotify_client.toggle_playback()

def switch_account_button_callback(channel):
    global spotify_client, display_manager, current_track_info
    print(f"Switch Account button pressed on GPIO {channel}")
    if spotify_client:
        if display_manager:
            display_manager.wake_up()
            display_manager.clear_display()
            temp_img = Image.new('1', (display_manager.width, display_manager.height), 255)
            temp_draw = ImageDraw.Draw(temp_img)
            temp_draw.text((5, 5), "Switching Account...", font=display_manager.font_medium, fill=0)
            display_manager.epd.display(display_manager.epd.getbuffer(temp_img))
        
        if spotify_client.switch_to_next_account():
            current_track_info = {"track_name": None, "artist_name": None, "track_url": None}
        else:
            print("Failed to switch account.")
            if display_manager:
                display_manager.clear_display()
                temp_img = Image.new('1', (display_manager.width, display_manager.height), 255)
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.text((5, 5), "No Accounts or Fail", font=display_manager.font_medium, fill=0)
                display_manager.epd.display(display_manager.epd.getbuffer(temp_img))

# settings_toggle_button_callback は削除

# --- Main Daemon Loop ---
def main():
    global current_track_info, display_sleeping, last_display_update_time, display_manager, spotify_client

    # --- GPIO Setup ---
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(config.BUTTON_PLAY_PAUSE_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(config.BUTTON_SWITCH_ACCOUNT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    # BUTTON_SETTINGS_TOGGLE_PIN の設定は削除

    try:
        # --- Initialize Components ---
        display_manager = DisplayManager()
        accounts_file_path = os.path.join(os.path.dirname(__file__), 'accounts.json')
        spotify_client = SpotifyClient(accounts_file=accounts_file_path)

        # --- Attach Button Event Detectors ---
        GPIO.add_event_detect(config.BUTTON_PLAY_PAUSE_PIN, GPIO.FALLING, callback=play_pause_button_callback, bouncetime=300)
        GPIO.add_event_detect(config.BUTTON_SWITCH_ACCOUNT_PIN, GPIO.FALLING, callback=switch_account_button_callback, bouncetime=300)
        # BUTTON_SETTINGS_TOGGLE_PIN のイベント検出は削除

        print("Starting Spotify music display daemon (Web server is external)...")

        # --- Initial Setup Check (on startup) ---
        if not spotify_client.accounts_data:
            print("No Spotify accounts found on startup. Displaying setup message (Web GUI is always available).")
            if display_manager:
                display_manager.wake_up()
                display_manager.clear_display()
                temp_img = Image.new('1', (display_manager.width, display_manager.height), 255)
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.text((5, 5), "No Spotify Account", font=display_manager.font_medium, fill=0)
                temp_draw.text((5, 25), "Access Web UI (Port 5000)", font=display_manager.font_small, fill=0)
                display_manager.epd.display(display_manager.getbuffer(temp_img))
                display_sleeping = False
            time.sleep(2)

        # --- Main Loop ---
        while True:
            # Webサーバーの自動停止チェックは削除

            # Check for current account index updates from Web GUI
            current_index_file = 'current_account_index.txt'
            if os.path.exists(current_index_file):
                try:
                    with open(current_index_file, 'r') as f:
                        requested_index = int(f.read().strip())
                    
                    spotify_client.load_accounts() 

                    if spotify_client.accounts_data and 0 <= requested_index < len(spotify_client.accounts_data):
                        if (spotify_client.current_account_index != requested_index) or (spotify_client.sp is None):
                            print(f"Web GUI requested account switch to index: {requested_index}")
                            if spotify_client.set_current_account(requested_index):
                                current_track_info = {"track_name": None, "artist_name": None, "track_url": None}
                            else:
                                print("Failed to switch account from web GUI request.")
                        elif spotify_client.sp is None:
                            print(f"Web GUI requested current account {requested_index} again. Re-authenticating just in case.")
                            if spotify_client.set_current_account(requested_index):
                                current_track_info = {"track_name": None, "artist_name": None, "track_url": None}
                    else:
                        print(f"Requested index {requested_index} is out of bounds or no accounts. Deleting request file.")
                except ValueError:
                    print("Invalid content in current_account_index.txt. Deleting.")
                except Exception as e:
                    print(f"Error processing current_account_index.txt: {e}")
                finally:
                    if os.path.exists(current_index_file):
                        os.remove(current_index_file)

            # --- Main Display Logic ---
            # Webサーバーが常に起動している前提なので、web_server_process のチェックは不要
            if spotify_client.accounts_data:
                if spotify_client.sp: 
                    playback_data = spotify_client.get_current_playback()
                    
                    new_track_name = playback_data.get('track_name')
                    new_artist_name = playback_data.get('artist_name')
                    new_track_url = playback_data.get('track_url')
                    is_playing = playback_data.get('is_playing')

                    if (new_track_name != current_track_info['track_name'] or
                        new_artist_name != current_track_info['artist_name'] or
                        display_sleeping):
                        
                        if display_sleeping:
                            display_manager.wake_up()
                            display_sleeping = False
                        
                        current_track_info['track_name'] = new_track_name
                        current_track_info['artist_name'] = new_artist_name
                        current_track_info['track_url'] = new_track_url
                        
                        qr_code_img = None
                        if current_track_info['track_url']:
                            qr_code_img = generate_qr_code(current_track_info['track_url'])

                        if current_track_info['track_name'] and current_track_info['artist_name']:
                            print(f"Now playing: {current_track_info['track_name']} by {current_track_info['artist_name']}")
                            display_manager.display_info(
                                current_track_info['track_name'],
                                current_track_info['artist_name'],
                                qr_code_img
                            )
                        else:
                            print("No music playing or information unavailable.")
                            display_manager.clear_display()
                        
                        last_display_update_time = time.time()
                        
                    if not display_sleeping and is_playing and (time.time() - last_display_update_time > 20):
                        display_manager.sleep()
                        display_sleeping = True
                    elif not is_playing and not display_sleeping:
                        display_manager.clear_display()
                        display_manager.sleep()
                        display_sleeping = True
                else:
                    # Spotifyクライアントが未認証の場合の表示
                    if display_manager and not display_sleeping:
                        display_manager.clear_display()
                        temp_img = Image.new('1', (display_manager.width, display_manager.height), 255)
                        temp_draw = ImageDraw.Draw(temp_img)
                        temp_draw.text((5, 5), "Auth Failed/Idle", font=display_manager.font_medium, fill=0)
                        temp_draw.text((5, 25), "Access Web UI (Port 5000)", font=display_manager.font_small, fill=0)
                        display_manager.epd.display(display_manager.getbuffer(temp_img))
                        display_sleeping = True
            elif not spotify_client.accounts_data:
                # アカウントが設定されていない場合の表示 (常時Webサーバーなので、その旨を表示)
                if display_manager and not display_sleeping:
                    display_manager.wake_up()
                    display_manager.clear_display()
                    temp_img = Image.new('1', (display_manager.width, display_manager.height), 255)
                    temp_draw = ImageDraw.Draw(temp_img)
                    temp_draw.text((5, 5), "No Spotify Account", font=display_manager.font_medium, fill=0)
                    temp_draw.text((5, 25), "Access Web UI (Port 5000)", font=display_manager.font_small, fill=0)
                    display_manager.epd.display(display_manager.getbuffer(temp_img))
                    display_sleeping = False

            time.sleep(5)

    except KeyboardInterrupt:
        print("Exiting program due to KeyboardInterrupt.")
    except Exception as e:
        print(f"An unexpected error occurred in main_daemon: {e}")
    finally:
        # Webサーバーは別プロセスなので、ここでの停止処理は不要
        if display_manager:
            display_manager.clear_display()
            display_manager.close()
        GPIO.cleanup()
        print("Daemon cleanup complete.")

if __name__ == '__main__':
    main()
