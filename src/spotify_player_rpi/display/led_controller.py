from PIL import Image
from spotify_player_rpi.config import AppConfig

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
        # TODO: rpi-rgb-led-matrix.RGBMatrix() のインスタンス化
        # 適切なGPIOピン、行、チェーンの設定が必要
        # 例: self.matrix = RGBMatrix(options=matrix_options)
        print("[Real] Initializing matrix on GPIO...")
        # 接続エラーが発生したら、try-exceptでキャッチし、適切にログを出す

    def update_display(self, image: Image.Image):
        """Pillow ImageをLEDマトリックスに表示する"""
        # TODO: self.matrix.SetImage(image.convert("RGB")) などの処理
        if not self.matrix:
             raise RuntimeError("Matrix not initialized.")
        # self.matrix.SetImage(image) 
        pass

    def terminate(self):
        """ハードウェアリソースを解放する"""
        # TODO: self.matrix.Clear() とリソース解放
        pass