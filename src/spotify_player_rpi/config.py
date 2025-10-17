import os
from dotenv import load_dotenv
from typing import List, NamedTuple
from enum import Enum
from pathlib import Path
from dataclasses import dataclass

from spotify_player_rpi.typings.songs_info import SongInfo, SongsInfoType

# .envファイルを読み込む
load_dotenv()

# --- 環境設定 ---
class AppConfig:
    """アプリケーションの実行環境設定を管理するクラス"""
    
    # Mock/実クラス切り替え
    USE_MOCK_SPOTIFY: bool = os.getenv("USE_MOCK_SPOTIFY", "False").upper() == "TRUE"
    USE_MOCK_LED: bool = os.getenv("USE_MOCK_LED", "False").upper() == "TRUE"
    
    # ポーリングとフレームレート
    SPOTIFY_POLLING_INTERVAL: int = 10  # Spotify情報更新の間隔 (秒)
    FRAME_RATE: int = 30                # 描画フレームレート (FPS)
    FRAME_DELAY: float = 1 / FRAME_RATE # 1フレームあたりの遅延時間 (秒)

    # LEDマトリックスの物理サイズ
    MATRIX_WIDTH: int = 64
    MATRIX_HEIGHT: int = 32

    # トークン保存先
    TOKEN_FILE: str = ".spotify_token.json"



# --- レイアウト設定カタログ ---
class RowHeight(Enum):
    """行の高さを定義するEnum"""
    S = 8   # Small
    M = 12  # Medium
    L = 16  # Large

@dataclass(frozen=True)
class RowSpec:
    """
    各行タイプの設定仕様を厳密に定義するデータクラス\n
     height: int\n
     scrollable: bool\n
     font_path: Path
    """
    height: RowHeight
    scrollable: bool
    font_path: Path # Pathオブジェクトであることを明示

class RowType(NamedTuple):
    """表示要素のコンテンツ行のタイプを定義し、その仕様を保持するEnum"""  
    hight: RowHeight
    scrollable: bool
    font_path: Path
    contents: list[str] # SongsInfoTypeのvalueを格納するリスト

STATUS_CONTENTS_LIST: list[str] = [SongsInfoType.IS_PLAYING.value, SongsInfoType.PROGRESS_MS.value, SongsInfoType.DURATION_MS.value]
    
S = RowType(RowHeight.S, False, Path(Path.home(), ".fonts", "orange_kid.otf"), STATUS_CONTENTS_LIST)
M_1 = RowType(RowHeight.M, True, Path(Path.home(), ".fonts", "x12y16pxMaruMonica.ttf"), [SongsInfoType.TITLE.value])
M_2 = RowType(RowHeight.M, True, Path(Path.home(), ".fonts", "x12y16pxMaruMonica.ttf"), [SongsInfoType.ARTIST.value, SongsInfoType.ALBUM.value])



DISPLAY_ORDER: List[RowType] = [M_1, M_2, S]

if __name__ == "__main__":
    # 動作確認用
   
    print("\nRow Specifications:")
    for row in DISPLAY_ORDER:
        print(f"  RowType(height={row.hight}, scrollable={row.scrollable}, font_path='{row.font_path}', contents={row.contents})")