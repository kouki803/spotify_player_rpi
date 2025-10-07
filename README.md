# Spotify LED Matrix Display (RasPi Zero 2 W Project)
Raspberry Pi Zero 2 WとHUB75対応LEDマトリックス（32x64）を使用して、現在Spotifyで再生中の楽曲情報（曲名、アーティスト名、再生進度など）を表示する

# 概要
|項目|詳細|備考|
|:--:|:---|:---|
|MCU|Raspberry Pi Zero 2 W||
|LED|SMD2121/2020 LED Matrix (32x64)|HUB75対応|
||||
|言語|Python 3.9|パッケージ管理: uv|	
|LED制御|hzeller/rpi-rgb-led-matrix|Python Wrapper|

# セットアップとインストール
## 1. 環境構築
Raspberry Pi OS Liteをインストールし、SSH接続ができるように設定します。

Python 3.9+環境とパッケージマネージャーuvをセットアップします。

## 2. ライブラリのインストール
プロジェクトディレクトリ内で、必要な依存関係をインストールします。

```Bash
# 必要な依存関係をインストール
uv sync 

# HUB75 LED Matrixの制御ライブラリのインストール
# rpi-rgb-led-matrixライブラリのビルドとインストール手順に従ってください。
# (例: sudo apt install python3-dev libwebp-dev ...)
# (例: git clone https://github.com/hzeller/rpi-rgb-led-matrix.git)
```

## 3. 環境設定ファイル (.env)
プロジェクトのルートに .env ファイルを作成し、API認証情報とデバッグ設定を記述します。

コード スニペット
```
# Spotify API クレデンシャル
SPOTIPY_CLIENT_ID="YOUR_CLIENT_ID"
SPOTIPY_CLIENT_SECRET="YOUR_CLIENT_SECRET"
SPOTIPY_REDIRECT_URI="http://localhost:8888/callback" # 認証フローで使用

# Mock / デバッグ設定
# Trueにすると、APIやLEDハードウェアにアクセスせず、ログ出力とファイル保存で動作します。
USE_MOCK_SPOTIFY=True
USE_MOCK_LED=True
```

# ハードウェアセットアップ
## 配線

## 外装

# 実行方法
デバッグ実行 (Mock使用)
.envで USE_MOCK_SPOTIFY=True および USE_MOCK_LED=True に設定し、  
メインアプリケーションを実行します。LedControllerMockが生成フレームをPNGファイルとして出力します。

```Bash
uv run main.py
```

※ LEDの高頻度な更新にsudoが必要な場合があります
```Bash
sudo uv run main.py
```

[TODO] 恒久的な実行のため、systemdサービスの構築

# プログラム
## カスタマイズ要素
後述の[インターフェースなど](##インターフェースなど)で表示内容をカスタムできる
### DisplayConfig
LEDの解像度を設定し、下記の表に基づく列を配置して表示行や使用フォントをカスタムする
|タイプ|行数|備考|
|:--:|:--:|:--:|
|S|8||
|M|12||
|L|16|未実装|

書き方例
```python
"S": {"height": 8, "scrollable": False, "{font_path}": "{font_8pixel.ttf}",
```

## クラス設計
アプリケーションは、以下の主要クラスで構成する

|クラス|責務|備考|
|:---|:---|:---|
|MainApp|システム制御、ループ管理、mock切り替え||
|SpotifyClient|楽曲情報の取得、プレイヤー操作	APIアクセスを担当||
|SpotifyClientMock|Mock版||
|SpotifyAuth|アカウント認証、トークン管理、自動リフレッシュ||
|MatrixImager|レンダリングエンジン：<br>情報 → ピクセル配列に変換。スクロール制御。|DisplayConfigを参照してレイアウトを動的に構築|
|LedController|LEDドライバ：ピクセル配列 → LEDマトリックスに出力|hzellerライブラリのラッパー|
|LedControllerMock|Mock版|配列データはpng出力|
|HWInterface|物理ボタン（GPIO）の入力処理	||

## インターフェースなど
|クラス|内容|備考|
|:---|:---|:---|
|DisplayConfig|表示要素の仕様カタログ| (S, Mタイプなどの高さ、フォント、スクロール可否)|
|SongInfo|楽曲データのデータ構造||
