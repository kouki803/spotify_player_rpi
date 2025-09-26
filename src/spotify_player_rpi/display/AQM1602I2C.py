import smbus2 as smbus
import time

# I2C制御データ（アドレスの後の2バイト目）
CONTROL_CMD = 0x00 # 0x00: 次のバイトはコマンド (RS=0, Co=0)
CONTROL_DATA = 0x40 # 0x40: 次のバイトは表示データ (RS=1, Co=0)

# --- ST7032i/HD44780 コマンド定数 ---
CMD_CLEAR = 0x01
CMD_HOME = 0x02
CMD_DISPLAY_ON = 0x0C      # 表示ON, カーソルOFF, 点滅OFF
CMD_FUNCTION_SET_BASIC = 0x38  # 8bitバス, 2行, 5x7フォント (IS=0)
CMD_FUNCTION_SET_EXT = 0x39    # 8bitバス, 2行, 5x7フォント (IS=1: 拡張コマンド有効)

# 拡張コマンド (IS=1時)
CMD_INTERNAL_FREQ = 0x14   # 内部周波数設定
CMD_CONTRAST_LOW = 0x73    # コントラスト下位4ビット設定（記事のサンプル値）
CMD_POWER_CONTRAST_HIGH_5V = 0x51 # 電源(Bon=0)とコントラスト上位設定 (5V時サンプル値)
CMD_POWER_CONTRAST_HIGH_3V3 = 0x56 # 電源(Bon=1)とコントラスト上位設定 (3.3V時サンプル値)
CMD_FOLLOWER_ON = 0x6C     # フォロワー回路ON

# DDRAMアドレス設定 (表示位置の指定)
CMD_DDRAM_SET = 0x80

class AQM1602I2C:
    """
    AQMシリーズI2C LCDモジュール制御クラス
    """
    def __init__(self, bus_num: int, address: int, cols: int = 16, rows: int = 2, power_5v: bool = True):
        """
        :param bus_num: I2Cバス番号
        :param address: I2Cデバイスアドレス (AQMは 0x3E)
        :param cols: 桁数 (16 or 8)
        :param rows: 行数 (2)
        :param power_5v: Trueなら5V電源用設定 (0x51), Falseなら3.3V用設定 (0x56)
        """
        self.bus_num = bus_num
        self.address = address
        self.cols = cols
        self.rows = rows
        self.power_5v = power_5v
        
        try:
            self.bus = smbus.SMBus(self.bus_num)
        except Exception as e:
            print(f"I2Cバスの初期化に失敗: {e}")
            raise

        self._init_lcd()

    def _write_cmd(self, cmd: int):
        """I2Cを通じてコマンドをLCDに書き込み (RS=0)"""
        # [アドレス], [制御バイト=0x00], [コマンドバイト]
        self.bus.write_i2c_block_data(self.address, CONTROL_CMD, [cmd])
        time.sleep(0.00005) # 短いディレイ

    def _write_data(self, data: int):
        """I2Cを通じて表示データをLCDに書き込み(RS=1)"""
        # [アドレス], [制御バイト=0x40], [データバイト]
        self.bus.write_i2c_block_data(self.address, CONTROL_DATA, [data])
        time.sleep(0.00005) # 短いディレイ

    def _init_lcd(self):
        """AQM独自の初期化シーケンスを実行"""
        print("Initializing AQM LCD with extended commands...")

        # (0) 電源投入直後の待機 (145ms以上)
        time.sleep(0.145)

        # (1) 基本設定 (IS=0): 8bit, 2行, 5x7フォント
        self._write_cmd(CMD_FUNCTION_SET_BASIC)
        time.sleep(0.001)

        # (2) 拡張モード有効 (IS=1)
        self._write_cmd(CMD_FUNCTION_SET_EXT)
        time.sleep(0.001)

        # --- 拡張コマンドによる設定 ---
        
        # (3) 内部周波数の設定 (0x14)
        self._write_cmd(CMD_INTERNAL_FREQ)
        time.sleep(0.001)

        # (4) コントラスト下位4ビット設定 (0x73)
        self._write_cmd(CMD_CONTRAST_LOW)
        time.sleep(0.001)

        # (5) 電源とコントラスト上位設定 (5V: 0x51, 3.3V: 0x56)
        power_cmd = CMD_POWER_CONTRAST_HIGH_5V if self.power_5v else CMD_POWER_CONTRAST_HIGH_3V3
        self._write_cmd(power_cmd)
        time.sleep(0.002)

        # (6) フォロワー回路ON (0x6C)
        self._write_cmd(CMD_FOLLOWER_ON)
        time.sleep(0.3) # 300ms以上の長い待機

        # (7) 拡張モード終了 (IS=0)
        self._write_cmd(CMD_FUNCTION_SET_BASIC)
        time.sleep(0.001)

        # --- 基本コマンドによる設定 ---

        # (8) 表示クリア
        self.clear()
        time.sleep(0.002)

        # (9) ディスプレイON, カーソルOFF
        self._write_cmd(CMD_DISPLAY_ON)
        time.sleep(0.002)
        
        print("Initialization complete.")

    def clear(self):
        """ディスプレイの内容をクリアし、カーソルをホームに戻します。"""
        self._write_cmd(CMD_CLEAR)
        time.sleep(0.002)

    def home(self):
        """カーソルをホーム位置(0, 0)に戻します。"""
        self._write_cmd(CMD_HOME)
        time.sleep(0.002)

    def set_cursor(self, col: int, row: int):
        """
        カーソル位置を設定します。
        :param col: 桁 (0から開始)
        :param row: 行 (0から開始)
        """
        # AQM1602: 1行目アドレス 0x00-0x0F, 2行目アドレス 0x40-0x4F
        addr = col
        if row == 1:
            addr += 0x40
        
        # DDRAMアドレス設定コマンド 0x80 とアドレスをOR演算
        self._write_cmd(CMD_DDRAM_SET | addr)

    def message(self, text: str):
        """
        LCDにテキストを表示します。'\n'は改行として扱います。
        """
        self.clear()
        row = 0
        col = 0
        
        for char in text:
            if char == '\n':
                row += 1
                col = 0
                self.set_cursor(col, row)
            else:
                if row < self.rows:
                    self._write_data(ord(char))
                    col += 1


if __name__ == "__main__":
    I2C_BUS = 1 
    DEVICE_ADDRESS = 0x3E 

    try:
        lcd = AQM1602I2C(I2C_BUS, DEVICE_ADDRESS, cols=16, rows=2, power_5v=True)

        lcd.message("AQM1602 OK!\nReady to Use!")
        time.sleep(3)
        
        lcd.clear()
        lcd.set_cursor(0, 0)
        lcd.message("Address: 0x3E")
        
        lcd.set_cursor(0, 1)
        lcd.message("Python Test...") 
        
        time.sleep(3)
        
        # スクロールテスト
        scroll_text = " Scrolling demo for AQM LCD! " * 2
        for i in range(len(scroll_text) - 16):
            lcd.set_cursor(0, 0)
            lcd.message(scroll_text[i:i+16])
            time.sleep(0.2)
            
        lcd.clear()
        lcd.message("Finished.")
        
    except FileNotFoundError:
        print("\n[エラー] I2Cバスが見つかりません。I2Cが有効化されているか確認してください。")
    except Exception as e:
        print(f"\n[致命的なエラー] 処理中に問題が発生しました: {e}")
