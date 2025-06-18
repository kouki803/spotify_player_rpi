# main_daemon.py
import time
import os
import socket

import qrcode
from PIL import Image, ImageDraw

import spotify_player_rpi.config as config
from spotify_player_rpi.display_manager import DisplayManager
from spotify_player_rpi.spotify_client import SpotifyClient
from spotify_player_rpi.hardware_controller import HardwareController 


# --- Global Variables ---
current_track_info = {"track_name": None, "artist_name": None, "track_url": None}
display_sleeping = False
last_display_update_time = time.time()
display_manager = None
spotify_client = None
hardware_controller = None 

# --- Helper Functions ---
def get_ip_address():
    """Raspberry PiのローカルIPアドレスを取得する。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)) 
        ip_address = s.getsockname()[0]
        s.close()
        return ip_address
    except Exception:
        return "Unknown IP"

def generate_qr_code(data):
    """QRコード画像を作成する。"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=4,
        border=1,
    )
    if not data:
        data = "https://open.spotify.com/intl-ja" # デフォルトはSpotifyトップページ
    else:
        qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img.convert("1")

# --- GPIO Callbacks ---
# Play/Pauseボタンコールバック
def play_pause_button_callback(channel):
    global spotify_client
    # DisplayManager.IS_RPI を使って、実GPIOかモックかを示す
    print(f"[{'REAL' if DisplayManager.IS_RPI else 'MOCK'}] Play/Pause button pressed on GPIO {channel}")
    if spotify_client:
        spotify_client.toggle_playback()

# アカウント切り替えボタンコールバック
def switch_account_button_callback(channel):
    global spotify_client, display_manager, current_track_info
    print(f"[{'REAL' if DisplayManager.IS_RPI else 'MOCK'}] Switch Account button pressed on GPIO {channel}")
    if spotify_client:
        if display_manager:
            display_manager.wake_up()
            display_manager.clear_display()
            temp_img = Image.new('1', (display_manager.width, display_manager.height), 255)
            temp_draw = ImageDraw.Draw(temp_img)
            temp_draw.text((5, 5), "Switching Account...", font=display_manager.font_medium, fill=0)
            display_manager.epd.display(display_manager.getbuffer(temp_img))
        
        if spotify_client.switch_to_next_account():
            current_track_info = {"track_name": None, "artist_name": None, "track_url": None}
        else:
            print("Failed to switch account.")
            if display_manager:
                display_manager.clear_display()
                temp_img = Image.new('1', (display_manager.width, display_manager.height), 255)
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.text((5, 5), "No Accounts or Fail", font=display_manager.font_medium, fill=0)
                display_manager.epd.display(display_manager.getbuffer(temp_img))

# --- Main Daemon Loop ---
def main():
    global current_track_info, display_sleeping, last_display_update_time, display_manager, spotify_client, hardware_controller

    try:
        # --- Initialize HardwareController ---
        hardware_controller = HardwareController() # GPIOモード設定はここで行われる
        print("HardwareController initialized.")

        # --- Initialize other Components ---
        display_manager = DisplayManager() # DisplayManagerは初期化済みのGPIO環境を利用
        spotify_client = SpotifyClient()

        # --- Setup Buttons via HardwareController ---
        # HardwareController.setup_button内でIS_RPIをチェックし、物理ボタンを設定またはモック
        hardware_controller.setup_button(config.BUTTON_PLAY_PAUSE_PIN, play_pause_button_callback)
        hardware_controller.setup_button(config.BUTTON_SWITCH_ACCOUNT_PIN, switch_account_button_callback)
        print("Buttons setup completed.")

        print("Starting Spotify music display daemon...")

        # --- Initial Setup Check (on startup) ---
        # .envファイルにClient ID/Secretが設定されているか確認
        if not (config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET):
            print("Spotify Client ID/Secret not found in .env. Displaying setup message and waiting for daemon restart.")
            # ディスプレイが有効な場合のみ表示
            if display_manager and display_manager.epd: 
                display_manager.wake_up()
                display_manager.clear_display()
                temp_img = Image.new('1', (display_manager.width, display_manager.height), 255)
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.text((5, 5), "Setup Required:", font=display_manager.font_medium, fill=0)
                temp_draw.text((5, 25), "Set Client ID/Secret", font=display_manager.font_small, fill=0)
                temp_draw.text((5, 45), "in .env (restart daemon)", font=display_manager.font_small, fill=0) 
                display_manager.epd.display(display_manager.getbuffer(temp_img))
                display_sleeping = False
            else: # ディスプレイが有効でない場合のモック出力
                print("Display mock: Setup Required: Set Client ID/Secret in .env (restart daemon)")

            # .env は動的に読み込まれないため、daemonの再起動を促す
            while not (config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET):
                print("Waiting for Client ID/Secret to be set in .env. Please edit .env and restart daemon.")
                time.sleep(30) 
                continue 

        # --- Main Loop ---
        while True:
            # Check for current user account index updates from Web GUI
            current_index_file = os.path.join(config.PROJECT_ROOT, 'current_account_index.txt')
            if os.path.exists(current_index_file):
                try:
                    with open(current_index_file, 'r') as f:
                        requested_index = int(f.read().strip())
                    
                    spotify_client._load_accounts() 

                    if spotify_client.accounts_data and 0 <= requested_index < len(spotify_client.accounts_data):
                        if (spotify_client.current_account_index != requested_index) or (spotify_client.sp is None):
                            print(f"Web GUI requested user account switch to index: {requested_index}")
                            if spotify_client.set_current_account(requested_index):
                                current_track_info = {"track_name": None, "artist_name": None, "track_url": None}
                            else:
                                print("Failed to switch user account from web GUI request.")
                        elif spotify_client.sp is None:
                            print(f"Web GUI requested current user account {requested_index} again. Re-authenticating just in case.")
                            if spotify_client.set_current_account(requested_index):
                                current_track_info = {"track_name": None, "artist_name": None, "track_url": None}
                    else:
                        print(f"Requested index {requested_index} is out of bounds or no user accounts. Deleting request file.")
                except ValueError:
                    print("Invalid content in current_account_index.txt. Deleting.")
                except Exception as e:
                    print(f"Error processing current_account_index.txt: {e}")
                finally:
                    if os.path.exists(current_index_file):
                        os.remove(current_index_file)

            # --- Main Display Logic ---
            # .envにClient ID/Secretが設定されていない場合は、メッセージ表示ループに留まる
            if not (config.SPOTIPY_CLIENT_ID and config.SPOTIPY_CLIENT_SECRET):
                time.sleep(5) 
                continue 

            # Spotifyユーザーアカウントがある場合のみ処理
            if spotify_client.accounts_data:
                # ディスプレイマネージャーとepdが有効な場合のみディスプレイ操作
                if display_manager and display_manager.epd: 
                    if spotify_client.sp: # Spotifyクライアントが認証済みの場合
                        playback_data = spotify_client.get_current_playback()
                        
                        new_track_name = playback_data.get('track_name')
                        new_artist_name = playback_data.get('artist_name')
                        new_track_url = playback_data.get('track_url')
                        is_playing = playback_data.get('is_playing')

                        # 楽曲情報が変更されたか、ディスプレイがスリープ中なら更新
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
                            
                        # 20秒後にスリープ（再生中かつスリープ中でない場合）
                        if not display_sleeping and is_playing and (time.time() - last_display_update_time > 20):
                            display_manager.sleep()
                            display_sleeping = True
                        elif not is_playing and not display_sleeping: # 再生中でない場合、すぐにスリープ
                            display_manager.clear_display()
                            display_manager.sleep()
                            display_sleeping = True
                    else: # Spotifyクライアントが未認証の場合の表示
                        if display_manager and not display_sleeping:
                            display_manager.clear_display()
                            temp_img = Image.new('1', (display_manager.width, display_manager.height), 255)
                            temp_draw = ImageDraw.Draw(temp_img)
                            temp_draw.text((5, 5), "User Auth Failed/Idle", font=display_manager.font_medium, fill=0)
                            temp_draw.text((5, 25), "Check Web UI (Port 5000)", font=display_manager.font_small, fill=0)
                            display_manager.epd.display(display_manager.getbuffer(temp_img))
                            display_sleeping = True
                else: # display_manager または epd の初期化に失敗した場合
                    print("Display not initialized. Cannot show music info.")
                    print("Check e-ink hardware connection and SPI/GPIO settings.")
                    time.sleep(5) 
            else: # アプリキーはあるが、ユーザーアカウントが一つもない場合
                if display_manager and display_manager.epd and not display_sleeping:
                    display_manager.wake_up()
                    display_manager.clear_display()
                    temp_img = Image.new('1', (display_manager.width, display_manager.height), 255)
                    temp_draw = ImageDraw.Draw(temp_img)
                    temp_draw.text((5, 5), "No User Account", font=display_manager.font_medium, fill=0)
                    temp_draw.text((5, 25), "Add User in Web UI (Port 5000)", font=display_manager.font_small, fill=0)
                    display_manager.epd.display(display_manager.getbuffer(temp_img))
                    display_sleeping = False
                else: # ディスプレイもモックで表示もできない場合
                    print("Display mock: No User Account. Add user in Web UI.")
                    time.sleep(5)


            time.sleep(5)

    except KeyboardInterrupt:
        print("Exiting program due to KeyboardInterrupt.")
    except Exception as e:
        print(f"An unexpected error occurred in main_daemon: {e}")
    finally:
        if display_manager:
            display_manager.clear_display()
            display_manager.close() # display_managerのclose()がWaveshare Dev_exitとepdconfig.module_exitを行う
        if hardware_controller:
            hardware_controller.cleanup_gpio() # HardwareControllerのcleanupを呼び出す
        print("Daemon cleanup complete.")

if __name__ == '__main__':
    print("--- main_daemon.py Debug Test ---")
    print("This will run the main daemon loop.")
    print("Requires .env with Spotify credentials, accounts.json with user accounts.")
    if HardwareController.IS_RPI: # HardwareControllerからIS_RPIフラグを参照
        print("Running on Raspberry Pi, GPIO and e-ink display will be used.")
    else:
        print("Running with GPIO mock, e-ink display will be simulated in console.")
    print("Press Ctrl+C to stop the daemon loop.")
    main()
