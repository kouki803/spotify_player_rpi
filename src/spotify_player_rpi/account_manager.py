# src/spotify_player_rpi/account_manager.py
import json
import os
import dataclasses
from typing import List, Dict, Any, Optional

import spotipy
from spotipy.oauth2 import SpotifyOAuth

# typesパッケージからのインポート
from .data_types import SpotifyAccount, TokenExpiredError
from . import config 

# ファイルパス
ACCOUNTS_FILE: str = os.path.join(config.PROJECT_ROOT, 'accounts.json')
SPOTIPY_CACHE_DIR: str = config.PROJECT_ROOT 

class AccountManager:
    """
    複数のSpotifyアカウント情報のロード、保存、トークンのリフレッシュ、および管理を行うクラス。
    """
    def __init__(self):
        self.accounts: List[SpotifyAccount] = self._load_accounts()
        self.active_index: int = -1
        
        if self.accounts:
            # アクティブなアカウントを初期設定
            for i, account in enumerate(self.accounts):
                if account.is_active:
                    self.active_index = i
                    break
            # アクティブなアカウントが見つからなければ、最初のものをアクティブにする
            if self.active_index == -1:
                self.active_index = 0
                self.accounts[0].is_active = True
                self._save_accounts()

    def _load_accounts(self) -> List[SpotifyAccount]:
        """accounts.jsonからアカウントデータをロードします。"""
        if os.path.exists(ACCOUNTS_FILE):
            try:
                with open(ACCOUNTS_FILE, 'r') as f:
                    data: List[Dict[str, Any]] = json.load(f)
                    return [SpotifyAccount(**item) for item in data]
            except (json.JSONDecodeError, TypeError, FileNotFoundError):
                print(f"Warning: {ACCOUNTS_FILE} is corrupted or cannot be read. Starting with empty list.")
                return []
        return []

    def _save_accounts(self) -> None:
        """アカウントデータをaccounts.jsonに保存します。"""
        data = [dataclasses.asdict(account) for account in self.accounts]
        with open(ACCOUNTS_FILE, 'w') as f:
            json.dump(data, f, indent=4)

    def get_oauth_instance(self, account_name: str) -> SpotifyOAuth:
        """
        特定のユーザー名に対応するSpotifyOAuthインスタンスを生成します。
        """
        client_id: Optional[str] = config.SPOTIPY_CLIENT_ID
        client_secret: Optional[str] = config.SPOTIPY_CLIENT_SECRET
        if client_id is None or client_secret is None:
            raise ValueError("Spotify Client ID/Secret are not configured.")

        # リフレッシュ時、OAuthインスタンスがトークンを一時的にキャッシュファイルに保存・読み込みする
        cache_path: str = os.path.join(SPOTIPY_CACHE_DIR, f'.spotify_cache_{account_name.replace(" ", "_")}')
        
        return SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=config.SPOTIPY_REDIRECT_URI,
            scope=config.SCOPE,
            cache_path=cache_path,
            show_dialog=False 
        )

    def get_active_account(self) -> Optional[SpotifyAccount]:
        """現在アクティブなアカウントデータを返します。"""
        if 0 <= self.active_index < len(self.accounts):
            return self.accounts[self.active_index]
        return None

    def refresh_token(self, account_index: int) -> bool:
        """
        指定されたインデックスのアカウントのアクセストークンをリフレッシュします。
        成功した場合 True、失敗した場合 False を返します。
        """
        if not (0 <= account_index < len(self.accounts)):
            return False

        account = self.accounts[account_index]
        print(f"Attempting to refresh token for user: {account.name}")
        
        oauth = self.get_oauth_instance(account.name)
        
        try:
            # トークンをリフレッシュして新しいトークンを取得
            token_info = oauth.refresh_access_token(account.refresh_token)
            
            # アカウントデータを更新
            account.access_token = token_info['access_token']
            account.refresh_token = token_info.get('refresh_token', account.refresh_token) 
            account.expires_at = token_info['expires_at']
            account.is_valid = True
            
            self._save_accounts()
            print(f"Token refresh successful for {account.name}.")
            return True
            
        except Exception as e:
            print(f"Token refresh FAILED for {account.name}: {e}")
            account.is_valid = False # このトークンは使用できないとマーク
            self._save_accounts()
            return False
            
    def mark_token_invalid(self, account_index: int) -> None:
        """
        APIコールでトークンが無効であると判明した場合、アカウントにフラグを立てます。
        """
        if 0 <= account_index < len(self.accounts):
            self.accounts[account_index].is_valid = False
            self._save_accounts()
            print(f"Account {self.accounts[account_index].name} marked as invalid.")

    def set_active_index(self, index: int) -> None:
        """
        アクティブなアカウントのインデックスを設定し、ファイルを更新します。
        Web通知ファイル (current_account_index.txt) も更新されます。
        """
        if not (0 <= index < len(self.accounts)):
            print(f"Error: Invalid index {index} provided for activation.")
            return

        # 既存のアクティブフラグを解除
        for i, account in enumerate(self.accounts):
            account.is_active = (i == index)
        
        self.active_index = index
        self._save_accounts()

        # Web通知ファイル (current_account_index.txt) を更新
        current_index_file = os.path.join(config.PROJECT_ROOT, 'current_account_index.txt')
        try:
            with open(current_index_file, 'w') as f:
                f.write(str(index))
            print(f"Web notification file updated to index: {index}")
        except Exception as e:
            print(f"Error writing to web notification file: {e}")

# --- 単体テストは省略 (前回のやり取りで詳細なテスト案を提供済み) ---