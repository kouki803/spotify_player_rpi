import spotify_player_rpi.config as config

# --- GPIO Mocking Setup (変更なし) ---
try:
    import RPi.GPIO as GPIO
    print("RPi.GPIO detected. Running on Raspberry Pi.")
    IS_RPI = True # Raspberry Pi 環境であることを示すフラグ
except RuntimeError:
    print("RPi.GPIO not found. Running with GPIO mock.")
    IS_RPI = False # Raspberry Pi 以外の環境であることを示すフラグ

    # GPIO操作を模擬するためのモッククラス
    class MockGPIO:
        BCM = 11; BOARD = 10; IN = 1; OUT = 0
        PUD_OFF = 0; PUD_DOWN = 1; PUD_UP = 2
        RISING = 10; FALLING = 11; BOTH = 12

        def setmode(self, mode): print(f"MockGPIO: setmode({mode}) called.")
        def setup(self, pin, mode, pull_up_down=None): print(f"MockGPIO: setup(pin={pin}, mode={mode}, pull_up_down={pull_up_down}) called.")
        def add_event_detect(self, pin, edge, callback=None, bouncetime=None):
            cb_name = callback.__name__ if callback else 'None'
            print(f"MockGPIO: add_event_detect(pin={pin}, edge={edge}, callback={cb_name}, bouncetime={bouncetime}) called.")
        def remove_event_detect(self, pin): print(f"MockGPIO: remove_event_detect(pin={pin}) called.")
        def cleanup(self): print("MockGPIO: cleanup() called.")
        def input(self, pin): print(f"MockGPIO: input(pin={pin}) called. Returning mock value (False/LOW)."); return 0
        def output(self, pin, value): print(f"MockGPIO: output(pin={pin}, value={value}) called.")

    # グローバルなGPIOオブジェクトとしてモックを使用
    GPIO = MockGPIO() 


class HardwareController:
    GPIO = GPIO 
    IS_RPI = IS_RPI

    def __init__(self):
        # GPIOモードの設定はここで行う (DisplayManagerより先に呼び出されることを想定)
        self.GPIO.setmode(self.GPIO.BCM)
        print("HardwareController: GPIO mode set to BCM.")

    def setup_button(self, pin, callback_func, bouncetime=config.BUTTON_DEBOUNCE_TIME):
        """
        指定されたピンをボタンとして設定し、イベント検出を登録します。
        :param pin: GPIOピン番号 (BCM)
        :param callback_func: ボタンが押されたときに呼び出される関数
        :param bouncetime: チャタリング防止時間 (ms)
        """
        if self.IS_RPI: # Raspberry Pi環境の場合のみ物理ボタンを設定
            self.GPIO.setup(pin, self.GPIO.IN, pull_up_down=self.GPIO.PUD_UP)
            self.GPIO.add_event_detect(pin, self.GPIO.FALLING, callback=callback_func, bouncetime=bouncetime)
            print(f"HardwareController: Button {pin} setup with real GPIO event detection.")
        else:
            print(f"HardwareController: Button {pin} setup with mock GPIO event detection.")
            self.GPIO.setup(pin, self.GPIO.IN, pull_up_down=self.GPIO.PUD_UP)
            self.GPIO.add_event_detect(pin, self.GPIO.FALLING, callback=callback_func, bouncetime=bouncetime)

    def cleanup_gpio(self):
        """GPIOピンをクリーンアップします。"""
        self.GPIO.cleanup()
        print("HardwareController: GPIO cleanup called.")

# Debug test for HardwareController (変更なし)
if __name__ == '__main__':
    import time
    print("--- hardware_controller.py Debug Test ---")

    hc = HardwareController()

    def test_callback_play_pause(channel):
        print(f"Test Callback: Play/Pause button {channel} pressed!")
    
    def test_callback_switch_account(channel):
        print(f"Test Callback: Switch Account button {channel} pressed!")

    hc.setup_button(config.BUTTON_PLAY_PAUSE_PIN, test_callback_play_pause, 200)
    hc.setup_button(config.BUTTON_SWITCH_ACCOUNT_PIN, test_callback_switch_account, 200)

    print("HardwareController initialized and buttons setup.")
    if not hc.IS_RPI:
        print("Running in mock mode. Physical button presses will not trigger callbacks.")
        print("Mocked GPIO calls are logged above.")
    else:
        print("Running on Raspberry Pi. Try pressing configured buttons.")

    print("Keeping script alive for 10 seconds. Press Ctrl+C to exit.")
    try:
        time.sleep(10)
    except KeyboardInterrupt:
        print("\nExiting test.")
    finally:
        hc.cleanup_gpio()
    print("--- Test Complete ---")