from dataclasses import dataclass, field
from enum import Enum
from time import time

class SongsInfoType(Enum):
    """Spotify楽曲情報と進捗データを保持する型の型"""
    TITLE = "title"
    ARTIST = "artist"
    ALBUM = "album"
    IS_PLAYING = "is_playing"
    PROGRESS_MS = "progress_ms"
    DURATION_MS = "duration_ms"
    RETRIEVED_AT = "retrieved_at"

@dataclass
class SongInfo:
    """Spotify楽曲情報と進捗データを保持するデータクラス"""
    title: str = 'title'
    artist: list = field(default_factory=list)
    album: str = 'album'
    is_playing: bool = False
    progress_ms: int = 0     # 現在の再生位置 (ミリ秒)
    duration_ms: int = 0     # 楽曲の全長 (ミリ秒)
    retrieved_at: float  = time()  # この情報がAPIから取得された正確な時刻 (UNIXタイムスタンプ)


    def __eq__(self, other):
        """MainAppでの状態変化チェック用に、タイトルと再生状態のみを比較する"""
        if not isinstance(other, SongInfo):
            return NotImplemented
        # 曲名と再生/一時停止状態が変わったかを見る
        return (self.title == other.title and 
                self.artist == other.artist and 
                self.is_playing == other.is_playing)
