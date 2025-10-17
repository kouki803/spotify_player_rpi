import time

from spotify_player_rpi.typings.songs_info import SongInfo
from spotify_player_rpi.spotify.spotify_auth import SpotifyAuth
from dataclasses import replace

# --- Mock Implementation ---

class SpotifyClientMock:
    def __init__(self):
        self.scenarios = self._load_scenarios()
        self.current_index = 0
        print("[Mock] SpotifyClientMock initialized.")

    def _load_scenarios(self) -> list[SongInfo]:
        """テストケース用のSongInfoの生データ準備"""
        
        MOCK_DURATION = 25000
        current_time = time.time()
       
        return [
            SongInfo(
                title="短い曲名",
                artist=["アーティスト A"], 
                album="アルバム X",
                is_playing=True, 
                progress_ms=5000, 
                duration_ms=MOCK_DURATION,
                retrieved_at=current_time, 
            ),
            SongInfo(
                title="スクロールテスト用の長～ー～ー～い曲名", 
                artist=["長～～いアーティスト名 1", "長～～～～いアーティスト名 2"], 
                album="アルバム loooong",
                is_playing=True, 
                progress_ms=5000, 
                duration_ms=MOCK_DURATION,
                retrieved_at=current_time
            ),
            SongInfo(
                title="停止中テスト", 
                artist=["アーティスト Stopper"], 
                album="アルバム Stop",
                is_playing=False, 
                progress_ms=5000, 
                duration_ms=MOCK_DURATION,
                retrieved_at=current_time
            ),
            SongInfo(
                title="HAPPY♪STEPPING!!DREAMING☆",
                artist=["天海春香 (CV：中村繪里子)"],
                album="THE IDOLM@STER MILLION LIVE! M@STER SPARKLE2 01",
                is_playing=True, 
                progress_ms=10000,
                duration_ms=MOCK_DURATION,
                retrieved_at=current_time
            ),
        ]


    def get_current_track(self) -> SongInfo:
        """次のテストシナリオを返し、情報取得時刻を付与する"""
        info =  self.scenarios[self.current_index]
        new_info = replace(info, retrieved_at=time.time()) 
        self.current_index = (self.current_index + 1) % len(self.scenarios)
        return new_info

    def play_pause(self):
        print("[Mock] Action: Toggled Play/Pause.")

    def next_track(self):
        self.current_index = (self.current_index + 1) % len(self.scenarios)
        print("[Mock] Action: Skipped to next track.")



class SpotifyClient:
    """実際のSpotify Web APIと通信する"""
    def __init__(self, auth: SpotifyAuth):
        self.auth = auth
        # TODO: Spotipyまたはrequestsクライアントの初期化
        print("[Real] SpotifyClient initialized.")

    def get_current_track(self) -> SongInfo:
        """APIから現在再生中の楽曲情報を取得する"""
        # TODO: APIリクエストを実行し、SongInfoを返す
        # HINT: リアルタイム性を高めるため、取得直後に retrieved_at=time.time() を付与すること
        raise NotImplementedError("Real API implementation is pending.")

    def play_pause(self):
        # TODO: 再生/一時停止コマンドをAPIに送信
        pass

    def next_track(self):
        # TODO: 次の曲へスキップコマンドをAPIに送信
        pass


if __name__ == "__main__":
    from typing import Union
    from spotify_player_rpi.config import AppConfig
    
    if AppConfig.USE_MOCK_SPOTIFY:
        client: Union[SpotifyClient, SpotifyClientMock] = SpotifyClientMock()
    else:
        auth = SpotifyAuth()
        client = SpotifyClient(auth)

    for _ in range(5):
        print(client.get_current_track())
        time.sleep(1)