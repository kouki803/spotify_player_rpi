from PIL import Image, ImageDraw, ImageFont


from spotify_player_rpi.hardware_controller import HardwareController
from src.spotify_player_rpi.display.epd_driver import EpdDriver
from spotify_player_rpi.types.types import DisplayInfos, PlaybackInfo, DisplayMode


class DisplayManager:
    IS_RPI = HardwareController.IS_RPI # Raspberry Pi環境かどうかを示すフラグ

    def __init__(self):
        self.epd = None 
        self.epdconfig = None # epdconfigモジュールを保持する変数

        try:
            if self.IS_RPI:
                # Raspberry Pi 環境 waveshareライブラリをインポート
                from spotify_player_rpi.lib.waveshare_epd import epdconfig as actual_epdconfig # epdconfigを別名でインポート
                from spotify_player_rpi.lib.waveshare_epd import epd2in13_V2 # epd2in13_V2もここでインポート
                self.epdconfig = actual_epdconfig # 実物のepdconfigを使用

                # epdconfig内のGPIOピン初期化とSPI初期化を一括で行う
                self.epdconfig.module_init() 
                print("DisplayManager: SPI and display pins initialized via epdconfig.module_init().")
                
                self.epd = epd2in13_V2.EPD()
                self.epd.init()
                self.epd.Clear(0xFF)
                self.width = self.epd.width
                self.height = self.epd.height
                print("DisplayManager initialized successfully on Raspberry Pi.")
            else:
                # Raspberry Pi 以外の環境 epdとepdconfigをモック（またはダミーオブジェクト）
                print("DisplayManager running in mock mode. e-ink display operations will be simulated.")
                self.width = 122 # モック時のダミーサイズ
                self.height = 250 # モック時のダミーサイズ
                
                # epdconfigのモック（module_initとmodule_exitを持つダミークラス）
                class MockEpdConfig:
                    def module_init(self_mock): print("MockEpdConfig: module_init() called.")
                    def module_exit(self_mock): print("MockEpdConfig: module_exit() called.")
                    # その他の必要なダミー定数などがあれば追加
                    RST_PIN = 17; DC_PIN = 25; CS_PIN = 8; BUSY_PIN = 24 # ダミー値を定義
                    # ...
                self.epdconfig = MockEpdConfig() # モックのepdconfigを使用
                # self.epd は None のままにし、display_infoなどでNoneチェックを行う
        except Exception as e:
            print(f"Error initializing e-ink display on Raspberry Pi: {e}")
            print("Ensure SPI is enabled (sudo raspi-config), hardware is connected correctly, and epdconfig.py has correct pin/bus settings.")
            print("Display functionality will be disabled.")
            self.epd = None 

        try:
            self.font_large = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
            self.font_medium = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
            self.font_small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 10)
        except IOError:
            print("Warning: Font not found. Using default font.")
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()

    def display_info(self, track_name, artist_name, qr_code_image=None):
        if self.epd is None:
            print(f"Mock Display: Now playing - {track_name} by {artist_name}")
            if qr_code_image:
                print("Mock Display: QR code also generated (but not shown).")
            return

        image = Image.new('1', (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)
        draw.text((5, 5), track_name, font=self.font_large, fill=0)
        draw.text((5, 30), artist_name, font=self.font_medium, fill=0)
        if qr_code_image:
            qr_size = min(self.width, self.height) // 2 - 10 
            qr_code_image = qr_code_image.resize((qr_size, qr_size))
            x_offset = self.width - qr_size - 5 
            y_offset = self.height - qr_size - 5 
            image.paste(qr_code_image, (x_offset, y_offset))
        self.epd.display(self.epd.getbuffer(image))

    def clear_display(self):
        if self.epd is None: 
            print("Mock Display: Cleared.")
            return
        self.epd.Clear(0xFF)

    def sleep(self):
        if self.epd is None: 
            print("Mock Display: Going to sleep.")
            return
        print("e-ink display going to sleep...")
        self.epd.sleep()

    def wake_up(self):
        if self.epd is None: 
            print("Mock Display: Waking up.")
            return
        print("e-ink display waking up...")
        self.epd.init()

    def close(self):
        if self.epd is None: 
            print("Mock Display: Closing.")
            return
        print("Closing e-ink display.")

        try:
            self.epd.Dev_exit() # SPIのモジュール終了

            if self.epdconfig: # epdconfigモックがあるか確認
                self.epdconfig.module_exit() 
                print("DisplayManager: SPI module exited through epdconfig.module_exit().")
        except Exception as e:
            print(f"Error during e-ink display Dev_exit/module_exit: {e}")
        

if __name__ == '__main__':
    import time
    # HardwareControllerを初期化して、DisplayManagerにGPIO設定がなされている状態を作る
    hc = HardwareController() 

    print("--- display_manager.py Debug Test ---")
    print("Attempting to initialize e-ink display...")
    dm = DisplayManager() 
    
    if dm.epd: # Raspberry Pi環境
        try:
            dm.display_info("Test Song (Real)", "Test Artist (Real)", None)
            print("Displayed test info. Waiting 3 seconds...")
            time.sleep(3)
            dm.clear_display()
            print("Cleared display. Waiting 3 seconds...")
            time.sleep(3)
            dm.sleep()
            print("Display put to sleep. Test complete.")
        except Exception as e:
            print(f"Error during real display test: {e}")
        finally:
            dm.close() 
            hc.cleanup_gpio() 

    else: # Raspberry Pi以外の環境（モック）の場合
        try:
            dm.display_info("Test Song (Mock)", "Test Artist (Mock)", None)
            print("Displayed mock info. Waiting 3 seconds...")
            time.sleep(3)
            dm.clear_display()
            print("Cleared mock display. Waiting 3 seconds...")
            time.sleep(3)
            dm.sleep()
            print("Mock Display test complete.")
        except Exception as e:
            print(f"Error during mock display test: {e}")
        finally:
            hc.cleanup_gpio() 
    print("--- Test Complete ---")
