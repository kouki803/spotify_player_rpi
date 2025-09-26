from dataclasses import dataclass
from typing import Optional
from PIL import Image


from enum import Enum


@dataclass
class PlaybackInfo:
    """現在再生中のSpotify楽曲情報を表すデータクラス。"""
    track_name: str
    artist_name: str
    track_url: Optional[str] = None  # QRコード用など、オプションな情報
    is_playing: bool = False

class DisplayMode(Enum):
    """ディスプレイの現在の状態や表示内容のカテゴリを示す列挙型。"""
    OFFLINE = "OFFLINE"                 # 初期設定が未完了、またはネットワークエラーなど
    NO_USER_ACCOUNT = "NO_USER_ACCOUNT" # アプリキーはあるがユーザーアカウントがない
    STOPPED = "STOPPED"                 # 音楽が停止中
    PLAY_PAUSE = "PLAY/PAUSE"           # 音楽再生中
    SETTING = "SETTING"                 # Web UI (設定画面) へのアクセスを促す
    ERROR = "ERROR"                     # その他のエラー表示


@dataclass
class DisplayInfos:
    """
    DisplayManagerに渡す統一された表示情報コンテナ。
    modeに基づいて、関連するOptionalフィールドのみが設定される。
    """
    mode: DisplayMode # 必須: 現在の表示モード

    # 各コンテンツタイプはOptionalで、modeに応じて設定される
    playback: Optional[PlaybackInfo] = None
    qr_code: Optional[Image.Image] = None
    profile: Optional[str] = None
    message: Optional[str] = None

    def has_content_changed(self, other: 'DisplayInfos') -> bool:
        """別のDisplayInfosオブジェクトと比較して、主要なコンテンツが変更されたかチェックする。"""
        if self.mode != other.mode:
            return True
        
        # モードが同じ場合、そのモードに関連するコンテンツが変更されたか確認
        if self.mode == DisplayMode.PLAY_PAUSE or self.mode == DisplayMode.STOPPED:
            if self.playback and other.playback:
                return self.playback.track_name != other.playback.track_name or \
                       self.playback.artist_name != other.playback.artist_name
            elif self.playback is not other.playback: # 片方だけNoneになった場合など
                return True
        
        if self.mode == DisplayMode.ERROR:
            if self.message and other.message:
                return self.message.line1 != other.message.line1
            elif self.message is not other.message:
                return True
        
        return False