import time
from PIL import Image, ImageDraw, ImageFont

import spotify_player_rpi.config as config
from spotify_player_rpi.hardware_controller import HardwareController


class EpdDriver:
    """
    e-inkディスプレイの低レベルなハードウェア操作とモックを管理するドライバークラス。
    """
    
    def __init__(self):
        self.epd = None 
        self.epdconfig = None 
        self.width: int = 0
        self.height: int = 0

        # HardwareControllerからの実機判定とconfigからの強制モック設定に基づいて判断
        self.should_init_real_epd = HardwareController.IS_RPI and not config.FORCE_DISPLAY_MOCK
        self.is_mock_mode = not self.should_init_real_epd # このドライバーがモックモードで動作するかどうか

        try:
            if self.should_init_real_epd:
                from spotify_player_rpi.lib.waveshare_epd import epdconfig as actual_epdconfig 
                from spotify_player_rpi.lib.waveshare_epd import epd2in13_V2 
                self.epdconfig = actual_epdconfig 

                self.epdconfig.module_init() 
                print("EpdDriver: SPI and display pins initialized via epdconfig.module_init().")
                
                self.epd = epd2in13_V2.EPD()
                self.epd.init()
                self.epd.Clear(0xFF)
                self.width = self.epd.width
                self.height = self.epd.height
                print("EpdDriver initialized successfully on Raspberry Pi (real display).")
            else:
                print("EpdDriver running in mock mode (forced or non-Pi).")
                self.width = 122 
                self.height = 250 
                
                class MockEpdConfig:
                    def module_init(self_mock): print("MockEpdConfig: module_init() called.")
                    def module_exit(self_mock): print("MockEpdConfig: module_exit() called.")
                    RST_PIN = 17; DC_PIN = 25; CS_PIN = 8; BUSY_PIN = 24 
                self.epdconfig = MockEpdConfig() 
        except Exception as e:
            print(f"Error initializing real e-ink display on Raspberry Pi: {e}")
            print("EpdDriver: Display functionality will be in mock mode due to initialization failure.")
            self.epd = None 
            self.is_mock_mode = True # 初期化失敗時は強制的にモックモードへ切り替える

    def display_image(self, image: Image.Image): 
        """
        PIL.Imageオブジェクトを物理ディスプレイに表示します。
        モックモードの場合はコンソールに出力します。
        """
        if self.is_mock_mode: 
            print(f"Mock EpdDriver: Displaying image (size: {image.width}x{image.height}).")
            return
        
        # epdがNoneでないことを確認 (初期化失敗の場合)
        if self.epd is not None:
            self.epd.display(self.epd.getbuffer(image))
            print("EpdDriver: Image displayed on real e-ink.")
        else: # is_mock_modeではないがepdがNoneの場合 (初期化は試みたが失敗)
            print("EpdDriver: Attempted to display image, but real EPD is not initialized. (already logged as error).")

    def clear(self):
        """ディスプレイをクリアします。"""
        if self.is_mock_mode:
            print("Mock EpdDriver: Cleared.")
            return
        
        if self.epd is not None:
            self.epd.Clear(0xFF)
            print("EpdDriver: Display cleared.")
        else:
            print("EpdDriver: Attempted to clear, but real EPD is not initialized.")

    def sleep(self):
        """ディスプレイを低消費電力モードに入れます（表示内容は維持）。"""
        if self.is_mock_mode: 
            print("Mock EpdDriver: Going to sleep.")
            return
        
        if self.epd is not None:
            print("EpdDriver: e-ink display going to sleep.")
            self.epd.sleep()
        else:
            print("EpdDriver: Attempted to sleep, but real EPD is not initialized.")

    def wake_up(self):
        """ディスプレイをスリープモードから復帰させます。"""
        if self.is_mock_mode:
            print("Mock EpdDriver: Waking up.")
            return
        
        if self.epd is not None:
            print("EpdDriver: e-ink display waking up.")
            self.epd.init()
        else:
            print("EpdDriver: Attempted to wake up, but real EPD is not initialized.")

    def close(self):
        """ディスプレイのリソースを解放します。"""
        if self.is_mock_mode: 
            print("Mock EpdDriver: Closing.")
            return
        
        print("EpdDriver: Closing e-ink display resources.")
        if self.epd is not None: # 実機のepdが有効な場合のみDev_exitを呼ぶ
            try:
                self.epd.Dev_exit() 
                if self.epdconfig: # epdconfigも実機の場合
                    self.epdconfig.module_exit() 
                    print("EpdDriver: SPI module exited through epdconfig.module_exit().")
            except Exception as e:
                print(f"Error during EpdDriver Dev_exit/module_exit: {e}")
        else:
            print("EpdDriver: Attempted to close, but real EPD was not initialized.")
        
if __name__ == '__main__':
    from PIL import Image, ImageDraw, ImageFont # フォントはImageFontからロードする
    print("--- epd_driver.py Debug Test ---")
    print("This tests the low-level e-ink display driver and its mocking.")
    print("Ensure HardwareController has been initialized before running this test in a real environment.")

    class MockHardwareController: # HardwareControllerをモック
        IS_RPI = True # テストのために実機と仮定（ただしconfig.FORCE_DISPLAY_MOCKで上書き可）
        def get_ip_address(self_mock): return "127.0.0.1" 

    HardwareController = MockHardwareController() 

    # config.pyのFORCE_DISPLAY_MOCKを設定してテスト可能
    # config.FORCE_DISPLAY_MOCK = False # Real Pi + Real Display (or init failure)
    # config.FORCE_DISPLAY_MOCK = True  # Real Pi + Mock Display

    print(f"Debug: HardwareController.IS_RPI = {HardwareController.IS_RPI}")
    print(f"Debug: config.FORCE_DISPLAY_MOCK = {config.FORCE_DISPLAY_MOCK}")

    driver = EpdDriver()

    if driver.is_mock_mode:
        print("\n--- Running EpdDriver in Mock Mode ---")
    else:
        print("\n--- Running EpdDriver with Real Hardware ---")

    # テスト用の画像を作成
    test_image = Image.new('1', (driver.width, driver.height), 255) # 白背景
    test_draw = ImageDraw.Draw(test_image)
    try: # フォントがロードできない場合のフォールバック
        font_default = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
    except IOError:
        font_default = ImageFont.load_default()

    test_draw.text((10, 10), "EpdDriver Test!", font=font_default, fill=0)
    test_draw.text((10, 30), f"Size: {driver.width}x{driver.height}", font=font_default, fill=0)
    test_draw.rectangle((5,5, driver.width-5, driver.height-5), outline=0)

    try:
        print("\n--- Test 1: Display Image ---")
        driver.display_image(test_image)
        time.sleep(3)

        print("\n--- Test 2: Clear Display ---")
        driver.clear()
        time.sleep(2)

        print("\n--- Test 3: Sleep and Wake Up ---")
        driver.sleep()
        time.sleep(2) 
        driver.wake_up()
        driver.display_image(test_image) 
        time.sleep(3)

    except Exception as e:
        print(f"Error during EpdDriver test: {e}")
    finally:
        driver.close()
    print("--- Test Complete ---")