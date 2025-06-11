from dataclasses import dataclass, field
from typing import Optional

@dataclass
class PlaybackInfo:
    """現在再生中のSpotify楽曲情報を表すデータクラス。"""
    track_name: str
    artist_name: str
    track_url: Optional[str] = None  # QRコード用など、オプションな情報
    is_playing: bool = False