from PIL import Image
from spotify_player_rpi.config import AppConfig
from rgbmatrix import RGBMatrix, RGBMatrixOptions

class LedControllerBase:
    """LEDマトリックスコントローラクラスの基底クラス"""
    def initialize_matrix(self):
        """LEDマトリックスの初期化を行う"""
        raise NotImplementedError

    def update_display(self, image: Image.Image):
        """Pillow ImageをLEDマトリックスに表示する"""
        raise NotImplementedError

    def terminate(self):
        """ハードウェアリソースを解放する"""
        raise NotImplementedError


# --- Mock Implementation ---
class LedControllerMock(LedControllerBase):
    from pathlib import Path
    import datetime as dt
    OUTPUT_PATH = Path(".log")
    
    def __init__(self):
        self.frame_count = 0
        print("[Mock] LedControllerMock initialized.")

    def initialize_matrix(self):
        """初期化処理をスキップ"""
        print("[Mock] Initializing matrix (simulated).")

    def update_display(self, image: Image.Image):
        """描画をシミュレートし、最初のフレームをファイルに保存"""
        
        # 10秒ごとにフレームのみ保存し、MatrixImagerの描画状態を確認
        if self.frame_count % 10 == 0:
            print(f"[Mock] First frame received. Saving to '{self.OUTPUT_PATH}' for visual check.")
            # 実際のサイズ検証
            if image.size != (AppConfig.MATRIX_WIDTH, AppConfig.MATRIX_HEIGHT):
                print(f"[ERROR] Imager output size mismatch: Expected {AppConfig.MATRIX_WIDTH}x{AppConfig.MATRIX_HEIGHT}, got {image.size}")
            image.save(self.OUTPUT_PATH.joinpath(f"led_matrix_{self.dt.datetime.now().strftime('%H%M%S')}.png"))
        
        self.frame_count += 1

    def terminate(self):
        """リソース解放をシミュレート"""
        print(f"[Mock] Terminated. Total frames simulated: {self.frame_count}")


# --- Real Implementation (Placeholder) ---

class LedController(LedControllerBase):
    """HUB75 LEDマトリックスを制御する"""
    def __init__(self):
        # TODO: hzeller/rpi-rgb-led-matrix のインポートと設定
        self.matrix = None 
        print("[Real] LedController initialized.")

    def initialize_matrix(self):
        """マトリックスオブジェクトの初期化とGPIO設定"""

        # オプションの設定 (Zero 2 W と 64x32 に合わせた一般的な設定)
        print("[Real] Initializing matrix on GPIO...")
        
        options = RGBMatrixOptions()
        
        # 物理的なマトリックスの構成
        options.rows = 32         # マトリックスの高さ (行数)
        options.cols = 64         # マトリックスの幅 (列数)
        options.chain_length = 1  # チェーン接続なし (1枚のみ)
        options.parallel = 1      # パラレル接続なし (通常1)
        
        # ハードウェア性能と表示品質の設定
        options.gpio_slowdown = 4 # Zero W/2 W ではGPIOタイミング調整が必要なことが多い
        options.hardware_mapping = 'regular'
        options.disable_hardware_pulsing = True # RPi 2/3/4/5では推奨されることが多い
        
        # その他の表示品質
        options.brightness = 75   # 0-100 (明るさ調整)
        options.led_rgb_sequence = 'RGB' # パネルによって'RBG', 'GRB'などに調整が必要
        options.pwm_bits = 11     # PWM階調 (1-11, 高いほど滑らか)
        
        try:
            # 2. RGBMatrixのインスタンス化 (GPIO制御開始)
            self.matrix = RGBMatrix(options=options)
            print("[Real] Matrix initialized successfully.")
            
        except RuntimeError as e:
            # 権限不足 (sudoなし) やハードウェア競合などで発生
            print(f"[FATAL ERROR] Matrix Initialization Failed: {e}")
            raise RuntimeError(f"LED Matrix initialization failed. Check sudo status or GPIO conflicts. ({e})")
            
        except Exception as e:
            print(f"[FATAL ERROR] Unknown error during matrix initialization: {e}")
            raise

    def update_display(self, image: Image.Image):
        """Pillow ImageをLEDマトリックスに表示する"""
        if self.matrix is None:
            raise RuntimeError("Matrix not initialized. Call initialize_matrix() first.")
        
        # Pillow画像をRGB形式に変換
        # RGBMatrixのSetImageメソッドはPillow Imageを受け取り、マトリックスに表示
        rgb_image = image.convert('RGB')
        
        # MatrixImagerの出力サイズとマトリックスのサイズが一致するかチェック
        if image.size != (self.matrix.width, self.matrix.height):
             raise ValueError(f"Image size mismatch: Expected {self.matrix.width}x{self.matrix.height}, got {rgb_image.size}")

        try:
            self.matrix.SetImage(rgb_image, unsafe=False)
        except Exception as e:
            print(f"[Error] Failed to set image to matrix: {e}")
            # エラー発生時は描画をスキップするが、プロセスは継続させる

    def terminate(self):
        """ハードウェアリソースを解放する"""
        if self.matrix:
            # 画面をクリアし、GPIOリソースを解放
            print("[Real] Clearing matrix and releasing resources.")
            self.matrix.Clear()
            # RGBMatrixはPythonのガベージコレクションによって適切にクリーンアップされることが多いが、
            # Clear()の呼び出しは重要
            self.matrix = None


if __name__ == "__main__":
    from PIL import Image, ImageDraw
    import time
    print("--- LedController REAL Hardware Test ---")
    
    # 💡 Mockの選択を False に設定
    is_mock = False  
    
    MATRIX_W = AppConfig.MATRIX_WIDTH
    MATRIX_H = AppConfig.MATRIX_HEIGHT

    # LedControllerの選択
    ControllerCls = LedControllerMock if is_mock else LedController
    
    # 1. 初期化とインスタンス生成
    try:
        controller = ControllerCls()
        # 💡 initialize_matrix で GPIO へのアクセスとマトリックスの準備を試行
        controller.initialize_matrix() 
    except RuntimeError as e:
        # initialize_matrix 内で捕捉された重要なエラー（権限など）を表示
        print(f"[FATAL ERROR] REAL Initialization failed. Ensure 'sudo' is used and wiring is correct: {e}")
        exit(1)
    except Exception as e:
        print(f"[FAIL] Unexpected initialization error: {e}")
        exit(1)


    # 2. テスト用画像の作成 (緑色の背景と中央にテキスト)
    try:
        # Spotifyカラーである緑色の背景
        test_image = Image.new("RGB", (MATRIX_W, MATRIX_H), color=(30, 215, 96)) 
        draw = ImageDraw.Draw(test_image)
        
        # 中央にテストテキストを描画 (白文字)
        draw.text((5, 10), "REAL TEST OK", fill=(255, 255, 255))
    except Exception as e:
        print(f"[FAIL] Failed to create test image: {e}")
        exit(1)

    # 3. 表示機能の確認
    print("\n[Action] Sending test image to physical matrix...")
    try:
        # 💡 ハードウェアに画像を表示
        controller.update_display(test_image) 
        print("[SUCCESS] Image sent to matrix. Check the display for a GREEN screen with WHITE text.")
        
        # ユーザーが確認できるように数秒待機
        time.sleep(5) 
        
    except Exception as e:
        print(f"[FAIL] update_display failed: {e}")
        
    # 4. 終了処理の確認
    print("\n[Action] Calling terminate to clear screen...")
    try:
        controller.terminate()
        print("[SUCCESS] LedController terminated and matrix cleared.")
    except Exception as e:
        print(f"[FAIL] Terminate failed: {e}")