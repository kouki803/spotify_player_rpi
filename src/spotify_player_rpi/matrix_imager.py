from PIL import Image, ImageDraw, ImageFont
from typing import Union
import time
from dataclasses import dataclass
from pathlib import Path

# config.py, types.songs_info.pyからのインポート
from spotify_player_rpi.config import AppConfig, RowType, DISPLAY_ORDER, RowHeight
from spotify_player_rpi.typings.songs_info import SongInfo
from spotify_player_rpi.typings.tokusyu_moji import TokusyuMoji



@dataclass
class ContentsRowConfig:
    """_summary_
    """
    SPEC: RowType # コンテンツ行の仕様
    font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]
    Y_START: int
    scroll_offset: int = 0 # 現在のスクロールオフセット

class MatrixImager:
    # -------------------------------------------------------------
    # 定数と初期化
    # ------------------------------------------------------------- 
    
    # 表示色の定数定義
    COLOR_SPOTIFY_GREEN = (30, 215, 96)
    COLOR_DEFAULT_TEXT = (255, 255, 255)
    COLOR_PROGRESS_BAR = (0, 128, 255)
    COLOR_BG = (16, 16, 16)
    COLOR_PAUSE_ORANGE = (255, 128, 0)
    
    # マルチアーティスト用の色パレット
    ARTIST_COLORS = [COLOR_SPOTIFY_GREEN, (255, 128, 0), (255, 255, 0)] 
    
    SCROLL_RESET_GAP = 5  # スクロールの終端にセットする余白
    WIDTH = AppConfig.MATRIX_WIDTH
    

    def __init__(self, display_order: list[RowType]):
        
        # レイアウト構築と属性名検証
        self.layout_configs = self._read_layout(display_order)
        
        # SongInfo
        self.current_song_info = SongInfo()
        print("[Imager] MatrixImager initialized.")

    def _read_layout(self, display_order: list[RowType]) -> list[ContentsRowConfig]:
        """RowTypeの静的仕様を読み込みコンテンツ行ごとの管理変数を追加"""
        

        configs: list[ContentsRowConfig] = []
        y0:int = 0 
        for i, row in enumerate(display_order):
            try:    
                font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont] = ImageFont.truetype(row.font_path, row.hight.value)
            except IOError:
                print(f"[ERROR] Could not load font from: {row.font_path}. Using default.")
                font = ImageFont.load_default()            


            configs.append(ContentsRowConfig(SPEC=row, font=font ,Y_START=y0))
            y0 = y0 + row.hight.value

        # 行数確認
        total_height = y0
        if total_height != AppConfig.MATRIX_HEIGHT:
            raise ValueError(f"[ERROR] Total height mismatch. Expected {AppConfig.MATRIX_HEIGHT}, got {total_height}.")

        return configs


    # -------------------------------------------------------------
    # パブリックインターフェース
    # -------------------------------------------------------------

    def set_song_info(self, info: SongInfo):
        """SongInfoを更新し、すべてのオフセットをリセットする"""
        self.current_song_info = info
        self.draw_next_frame()


    def draw_next_frame(self) -> Image.Image:
        """次のフレームを生成するパブリックメソッド"""
        if self.current_song_info.title == 'title':
            return self._render_error_frame("No Song Info", color=self.COLOR_PAUSE_ORANGE)

        frame = Image.new('RGB', (self.WIDTH, AppConfig.MATRIX_HEIGHT), color=(0, 0, 0))
        draw = ImageDraw.Draw(frame)

        for config in self.layout_configs:
            
            # S行の特殊処理
            if config.SPEC.hight == RowHeight.S:
                self._draw_fixed_status_line(draw, config, self.current_song_info)
                self._draw_play_icon(frame, self.current_song_info, config)
            else:
                # スクロール可のコンテンツ行
                self._draw_content_line(draw, config, self.current_song_info)
            
        return frame

    # -------------------------------------------------------------
    # 描画メソッド (コンテンツ取得と振り分け)
    # -------------------------------------------------------------
    
    def _draw_content_line(self, draw: ImageDraw.ImageDraw, config: ContentsRowConfig, info: SongInfo):
        """
        configのcontentsリストに基づき、複数の属性を結合して描画する。
        """
        
        # 描画初期化
        offset = config.scroll_offset
        x_current = 0 - offset
        y_start = config.Y_START 
        combined_text_for_calc = "" 
        
        for i, attr_name in enumerate(config.SPEC.contents): 
            # 1. SongInfoから属性値を安全に取得
            content = getattr(info, attr_name, None)
            
            if content is None:
                continue 
            
            # 2. 型に基づき描画を振り分ける
            if isinstance(content, str):
                x_current = self._draw_string_part(draw, config.font, y_start, x_current, content, self.COLOR_DEFAULT_TEXT)
                combined_text_for_calc += content
                
            elif isinstance(content, list):
                x_current = self._draw_list_part(draw, config.font, y_start, x_current, content)
                combined_text_for_calc += " / ".join([str(c) for c in content])
            
            # 3. 複数の要素がある場合の区切り文字
            if i < len(config.SPEC.contents) - 1 and config.SPEC.scrollable: # 💡 ドット記法
                 separator = " | " 
                 x_current = self._draw_string_part(draw, config.font, y_start, x_current, separator, self.COLOR_DEFAULT_TEXT)
                 combined_text_for_calc += separator
            
            elif i < len(config.SPEC.contents) - 1 and not config.SPEC.scrollable: # 💡 ドット記法
                 # 非スクロール行で複数要素を結合する場合のスペース
                 x_current = self._draw_string_part(draw, config.font, y_start, x_current, " ", self.COLOR_DEFAULT_TEXT)
                 combined_text_for_calc += " "

        # 4. スクロール状態の更新
        if config.SPEC.scrollable:
            config.scroll_offset = self._update_offset(config, combined_text_for_calc, offset)


    def _draw_string_part(self, draw: ImageDraw.ImageDraw, font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont], y_start: int, x_current: int, text: str, color: tuple) -> int:
        """単一の文字列を描画し、新しいX座標を返す"""
        draw.text((x_current, y_start), text, font=font, fill=color)
        x_current += int(draw.textlength(text, font=font))
        return x_current

    def _draw_list_part(self, draw: ImageDraw.ImageDraw, font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont], y_start: int, x_current: int, content_list: list[str]) -> int:
        """リスト化された文字列（アーティストなど）を色分けして描画し、新しいX座標を返す"""
        
        for i, text_part in enumerate(content_list):
            color = self.ARTIST_COLORS[i % len(self.ARTIST_COLORS)] 
            
            # 区切り文字の描画 (アーティスト間)
            if i > 0:
                separator = " / "
                draw.text((x_current, y_start), separator, font=font, fill=self.COLOR_DEFAULT_TEXT)
                x_current += int(draw.textlength(separator, font=font))
            
            # テキスト本体の描画
            draw.text((x_current, y_start), text_part, font=font, fill=color)
            x_current += int(draw.textlength(text_part, font=font))
            
        return x_current

    def _draw_fixed_status_line(self, draw: ImageDraw.ImageDraw, config: ContentsRowConfig, info: SongInfo):
        """固定のステータス行 (S行) を描画する（プログレスバー、アイコンなど）"""

        PLAY_STOP_ICON_WIDTH: int = 8
        
        # 進捗の外挿計算 (info.progress_ms, info.duration_ms, info.retrieved_atを使用)
        def progress_ratio(info: SongInfo, bar_wid: int) -> int: # {bar_wid}段階で返す
            if info.is_playing and info.duration_ms > 0:
                time_since_retrieval = time.time() - info.retrieved_at
                current_progress_ms = info.progress_ms + int(time_since_retrieval * 1000)
                progress_ratio = min(1.0, current_progress_ms / info.duration_ms)
            else:
                progress_ratio = min(1.0, info.progress_ms / info.duration_ms if info.duration_ms > 0 else 0)
            return int(progress_ratio * bar_wid)

        # プログレスバーの描画
        bar_y_top = config.Y_START + (config.SPEC.hight.value // 2) - 1
        bar_y_bottom = config.Y_START + (config.SPEC.hight.value // 2) + 1
        bar_width = progress_ratio(info, self.WIDTH - PLAY_STOP_ICON_WIDTH)

        # [Hint] rectangle [top-left-x, top-left-y, bottom-right-x, bottom-right-y]
        draw.rectangle([8, bar_y_top, self.WIDTH - 1, bar_y_bottom], fill=self.COLOR_BG) # BACK GROUND
        draw.rectangle([8, bar_y_top, bar_width - 1, bar_y_bottom], fill=self.COLOR_PROGRESS_BAR) # PROGRESS BAR
        

    # 再生ステータスアイコンの描画
    def _draw_play_icon(self, frame: Image.Image, info: SongInfo, config: ContentsRowConfig):
        if info.title is None:
            icon = Image.fromarray(TokusyuMoji.STOP_MAP)
        else:
            if info.is_playing:
                icon = Image.fromarray(TokusyuMoji.PLAY_MAP)
            else:
                icon = Image.fromarray(TokusyuMoji.PAUSE_MAP)
        frame.paste(icon, box=(0, config.Y_START))

    def draw_picture_frame(self, path: Path) -> Image.Image:
        """画像をそのまま表示するフレームを生成するパブリックメソッド"""
        try:
            img = Image.open(path).convert("RGB")
            img = img.resize((self.WIDTH, AppConfig.MATRIX_HEIGHT))
            return img
        except Exception as e:
            print(f"[Error] Failed to load picture from {path}: {e}")
            return self._render_error_frame("Image Load Error", color=self.COLOR_PAUSE_ORANGE)
        



    def _render_error_frame(self, message: str, color: tuple) -> Image.Image:
        """エラー時や情報がない場合に表示するフレーム"""
        font =  ImageFont.load_default()
        frame = Image.new('RGB', (AppConfig.MATRIX_WIDTH, AppConfig.MATRIX_HEIGHT), color=self.COLOR_BG)
        draw = ImageDraw.Draw(frame)
        draw.text((8, 40), message, font=font, fill=self.COLOR_DEFAULT_TEXT)
        return frame


    # -------------------------------------------------------------
    # スクロールロジック
    # -------------------------------------------------------------
    
    def _calculate_text_width(self, text: str, config: ContentsRowConfig) -> int:
        """テキストのピクセル幅を計算する"""
        return int(ImageDraw.Draw(Image.new('RGB', (1,1))).textlength(text, font=config.font))

    def _update_offset(self, config: ContentsRowConfig, text: str, current_offset: int) -> int:
        """オフセットを1ピクセル更新し、スクロール終端に達したらリセットする"""
        text_width = self._calculate_text_width(text, config=config)

        if text_width <= self.WIDTH:
            return 0
        
        next_offset = current_offset + 1

        max_offset = text_width + self.SCROLL_RESET_GAP
        
        if next_offset >= max_offset:
            return - self.WIDTH 
        else:
            return next_offset

if __name__ == "__main__":
    # 簡易テストコード
    from spotify_player_rpi.typings.songs_info import SongInfo
    from spotify_player_rpi.config import RowType, AppConfig
    if AppConfig.USE_MOCK_LED:
        from spotify_player_rpi.display.led_controller import LedControllerMock as LedController
    else:
        from spotify_player_rpi.display.led_controller import LedController

    imager = MatrixImager(display_order=DISPLAY_ORDER)
    
    test_info = SongInfo(
        title="Test Song Title That Is Really Long",
        artist=["Artist One", "Artist Two", "Artist Three"],
        album="Test Album Name",
        is_playing=True,
        progress_ms=15000,
        duration_ms=24000,
        retrieved_at=time.time()
    )
    
    imager.set_song_info(test_info)
    led = LedController()
    led.initialize_matrix()

    for _ in range(100):
        frame = imager.draw_next_frame()
        frame.show()
        led.update_display(frame)
        time.sleep(0.1)

    pic_path = Path(input("Enter image path for picture frame test: "))
    frame = imager.draw_picture_frame(pic_path)

    for _ in range(200):
        led.update_display(frame)
        time.sleep(0.1)
