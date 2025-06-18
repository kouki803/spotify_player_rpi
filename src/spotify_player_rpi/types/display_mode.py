from enum import Enum

class DisplayMode(Enum):
    """ディスプレイの現在の状態や表示内容のカテゴリを示す列挙型。"""
    OFFLINE = "OFFLINE"                 # 初期設定が未完了、またはネットワークエラーなど
    NO_USER_ACCOUNT = "NO_USER_ACCOUNT" # アプリキーはあるがユーザーアカウントがない
    STOPPED = "STOPPED"                 # 音楽が停止中
    PLAY_PAUSE = "PLAY/PAUSE"           # 音楽再生中
    SETTING = "SETTING"                 # Web UI (設定画面) へのアクセスを促す
    ERROR = "ERROR"                     # その他のエラー表示