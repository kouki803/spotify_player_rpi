import time
from spotify_player_rpi.config import AppConfig, DISPLAY_ORDER
from spotify_player_rpi.spotify import SpotifyAuth, SpotifyClient, SpotifyClientMock
from spotify_player_rpi.display.led_controller import LedController, LedControllerMock, LedControllerBase
from spotify_player_rpi.matrix_imager import MatrixImager # TODO 
from spotify_player_rpi.typings import SongInfo

class MainApp:
    def __init__(self):
        self.auth = SpotifyAuth()

        # クラスの動的選択
        self.spotifyclient = SpotifyClientMock() if AppConfig.USE_MOCK_SPOTIFY else SpotifyClient(auth=self.auth)
        self.led_controller: LedControllerBase = LedControllerMock() if AppConfig.USE_MOCK_LED else LedController()


        # MatrixImagerの初期化 ()
        self.imager = MatrixImager(display_order=DISPLAY_ORDER)

        # 状態管理
        self.last_spotify_update_time = 0
        self.current_song_info: SongInfo = self.spotifyclient.get_current_track() 

    def _check_and_update_spotify_info(self):
        """Spotifyから情報を取得し、MatrixImagerを更新する"""
        current_time = time.time()

        if current_time - self.last_spotify_update_time >= AppConfig.SPOTIFY_POLLING_INTERVAL:
            try:
                new_info = self.spotifyclient.get_current_track() 
            except NotImplementedError:
                 # Real実装がまだの場合
                 print("[Error] SpotifyClient not fully implemented.")
                 return
            except Exception as e:
                 print(f"[Error] Spotify API communication failed: {e}")
                 # TODO: MatrixImagerにエラーメッセージ表示を指示
                 return

            # 楽曲や再生状態の変更があった場合、Imagerをリセット
            if self.current_song_info is None or new_info != self.current_song_info:
                print(f"[Update] New Content: {new_info.title} by {new_info.artist}")
                self.imager.set_song_info(new_info)
                self.current_song_info = new_info

            self.last_spotify_update_time = current_time

    def run(self):
        """アプリケーションのメインループ"""
        print("--- MainApp Starting ---")
        self.led_controller.initialize_matrix()
        # self.hw_interface.setup_buttons() # HWInterfaceの初期化 (未実装)

        # 初期情報の取得
        self._check_and_update_spotify_info()

        # 描画ループを開始
        self.drawing_loop()

    def drawing_loop(self):
        """LEDマトリックスの更新を継続的に行う (高頻度)"""
        try:
            while True:
                # 1. 情報更新チェック (低頻度)
                self._check_and_update_spotify_info()
                
                # 2. 次のスクロールフレームを取得 (MatrixImager内部で進捗とオフセットが更新される)
                next_frame_image = self.imager.draw_next_frame()

                # 3. LEDコントローラに表示を依頼
                self.led_controller.update_display(next_frame_image) 
                
                # 4. フレームレート調整
                time.sleep(AppConfig.FRAME_DELAY)
                
        except KeyboardInterrupt:
            print("Shutdown requested by user.")
        finally:
            self.led_controller.terminate()
            print("--- MainApp Terminated ---")


if __name__ == "__main__":
    # 実行前に、MatrixImagerとHWInterfaceのファイルを作成する必要があります
    # (ここでは一旦、MatrixImagerのファイルがある前提で実行)
    try:
        app = MainApp()
        app.run()
    except Exception as e:
        print(f"\n[FATAL ERROR] An unhandled error occurred: {e}")