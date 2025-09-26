# spotify_player_rpi

Raspberry Pi Zero 2 Wとe-inkディスプレイでSpotify音楽情報を表示するシステム
このプロジェクトは、Raspberry Pi Zero 2 WとWaveshare 2.13インチe-inkディスプレイを活用し、Spotify Connectで再生中の音楽情報を表示するシステムです。  
物理ボタンと一時的に起動するWebサーバーを組み合わせることで、直感的かつ省電力な運用を実現します。  

# システムの主な機能と特徴
e-inkディスプレイを取り付けたRasPiを用いてSpotify Web API経由で再生中の楽曲情報を取得し表示します． 
楽曲名、アーティスト名、楽曲共有用QRコードを表示します。

## e-inkディスプレイでの楽曲情報表示
* e-inkディスプレイ表示: Waveshare 2.13インチe-inkディスプレイに、現在の楽曲名とアーティスト名、楽曲共有用QRコードを表示します。
(楽曲の切り替わり時のみ画面を更新します。)
更新から20秒経過するか、音楽が停止するとe-inkディスプレイをスリープモードにし、消費電力を抑えます。



## 複数のspotifyアカウントへの対応
アカウント切り替え機能により，設定済みのSpotifyアカウントを切り替えて再生することができます．


# 操作
ボタン
* 再生・停止ボタン: 楽曲の再生・停止(Spotify Connectで再生中の音楽を制御します。)
* モード切替ボタン: 再生モードと設定モードを切り替える
* アカウント切り替え: 登録されている複数のSpotifyアカウント間を循環して切り替えます。

### 初期設定
設定用のWebサーバーは、Spotifyアカウントの連携と解除を行えます．
モード切り替えボタンを押すと、Webサーバーが起動し、Wi-Fi経由でWebブラウザから各種設定にアクセスできるようになります．  
Webサーバーが起動中に再度このボタンを押すと、手動で停止することもできます。

※ Webサーバーは必要な時だけ起動し、設定終了時や一定時間（デフォルト5分）自動的に停止します。
Webサーバーは設定時のみ起動するため、再生時のリソースを節約します。

Raspberry Piが同一Wi-Fiネットワークに接続されていれば、PCやスマートフォンのWebブラウザからhttp://<Raspberry PiのIPアドレス>:5000にアクセスすることで、直感的な設定が可能です。  
* アカウントの追加: 新しいSpotifyアカウントを簡単に追加できます。初回セットアップ時や、後から別のアカウントを追加したい場合に利用します。
* アカウントの管理: 登録済みのアカウントの一覧表示、有効化、削除ができます。   

# システム構成とファイルの役割
このシステムは、以下の主要なPythonスクリプトと補助ファイルで構成されます。
```
spotify_display_project/
├── config.py           # システム全体の定数（APIキー、GPIOピン設定など）
├── display_manager.py  # Waveshare e-inkディスプレイの制御と描画ロジック
├── spotify_client.py   # Spotify Web APIとの連携、アカウント認証、情報取得、再生制御
├── main_daemon.py      # システムのメインループ。音楽情報ポーリング、e-ink表示、GPIO監視、Webサーバー制御
├── web_server.py       # FlaskベースのWebサーバー。設定GUIを提供
├── accounts.json       # 登録されたSpotifyアカウント情報（ユーザー名、リフレッシュトークンなど）を保存
├── current_account_index.txt # Web GUIからmain_daemonへのアカウント切り替え通知用ファイル
├── lib/                # Waveshare e-PaperディスプレイのPythonライブラリ
│   └── waveshare_epd/
│       └── ...
├── templates/          # Flaskが使用するHTMLテンプレート
│   └── index.html      # メイン設定画面
│   └── add_account.html# アカウント追加画面
└── static/             # Web GUIの静的ファイル（CSS、JavaScriptなど）
    └── style.css
```

# 実装とセットアップのステップ
1. Raspberry Pi OSの準備: Raspberry Pi Zero 2 Wに最新のRaspberry Pi OS Liteをインストールし、SSH、Wi-Fi、I2C/SPIを有効化します。
2. Spotify APIアプリケーション登録: Spotify Developer Dashboardでアプリケーションを登録し、Client IDとClient Secretを取得します。
   Redirect URIにはhttp://localhost:8888/callbackを設定します。
3. Python環境の構築
   1. spotipy, Pillow, qrcode, RPi.GPIO, Flaskなどの必要なPythonライブラリをインストールします。
   2. Waveshare e-PaperのPythonライブラリをダウンロードし、プロジェクトのlib/ディレクトリに配置します。
4. コードの配置と設定
   上記のPythonスクリプトとHTML/CSSファイルをプロジェクトディレクトリ
   （例: /home/pi/spotify_display_project）に配置し、config.pyに取得したSpotify APIキーとGPIOピンの番号を設定します。
6. 物理ボタンの配線: 各機能に対応するGPIOピンとGNDに物理ボタンを接続します。
7. systemdサービスの設定: main_daemon.pyを起動時に自動実行するためのspotify_display_daemon.serviceを作成し、有効化します。web_server.pyはmain_daemon.pyから制御されるため、個別のsystemdサービスは不要です。

# 初回起動と運用フロー
システム起動: Raspberry Piを起動すると、main_daemon.pyが自動的に実行されます。
## 初期設定
- accounts.jsonが存在しない場合、e-inkディスプレイには「No Spotify Account / Press SETTINGS Button」と表示されます。
- ユーザーはSETTINGSボタンを押します。
- Webサーバーが起動し、ディスプレイにIPアドレスとポート番号（例: http://192.168.1.100:5000）が表示されます。
- PC/スマホのブラウザからそのURLにアクセスし、「Add New Account」からSpotify認証フローを進めてアカウントを追加します。
- 認証が完了すると、アカウント情報が保存され、ディスプレイは通常モードに戻ります。
## 通常運用
- Spotify Connectで音楽を再生すると、e-inkディスプレイに楽曲情報とQRコードが表示されます。
- 再生/一時停止ボタンで音楽を制御できます。
- アカウント切り替えボタンで、登録済みの別のアカウントに切り替えることができます。
  - 画面更新は楽曲切り替わり時のみ行われ、20秒後にディスプレイはスリープします。
## アカウント追加/管理:
- SETTINGSボタンを押すと、いつでもWebサーバーを起動し、Web GUIからアカウントの追加、削除、有効化を行えます。
- Webサーバーは、操作がないまま5分経過するか、再度SETTINGSボタンが押されると自動的に停止し、通常モードに戻ります。


# 表示画面
## 1602A(AQM1602A)
AQM1602/AQM0802シリーズ I2C LCDモジュール (ST7032iコントローラー) 用のPythonクラス。
標準のPCF8574/MCP23008ベースのライブラリでは動作しないAQM固有の拡張コマンドによる
初期化シーケンスを実装しています。

参照: https://www.denshi.club/make/2016/10/aqmi2clcd1.html

