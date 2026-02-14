"""マネーフォワード ME から資産残高を取得するモジュール

マネーフォワードは公式APIを提供していないため、
Webスクレイピングでログイン後に資産情報を取得します。

NOTE: マネーフォワードの仕様変更により動作しなくなる可能性があります。
その場合はセレクタやURLの修正が必要です。
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from app.config import MoneyForwardConfig
from app.models import Account, FinanceSnapshot

logger = logging.getLogger(__name__)

MF_BASE_URL = "https://moneyforward.com"
MF_SIGN_IN_URL = f"{MF_BASE_URL}/sign_in"
MF_SESSION_URL = f"{MF_BASE_URL}/sign_in/email"
MF_ACCOUNTS_URL = f"{MF_BASE_URL}/accounts"
MF_BS_URL = f"{MF_BASE_URL}/bs/portfolio"


class MoneyForwardClient:
    """マネーフォワード ME クライアント"""

    def __init__(self, config: MoneyForwardConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
            )
        return self._client

    async def login(self) -> bool:
        """マネーフォワードにログインする"""
        client = await self._get_client()

        try:
            # サインインページを取得してCSRFトークンを取得
            resp = await client.get(MF_SIGN_IN_URL)
            resp.raise_for_status()

            # CSRFトークンをHTMLから抽出
            csrf_token = self._extract_csrf_token(resp.text)
            if not csrf_token:
                logger.error("CSRFトークンの取得に失敗しました")
                return False

            # メールアドレスでログイン
            login_data = {
                "authenticity_token": csrf_token,
                "sign_in_session_service[email]": self.config.email,
                "sign_in_session_service[password]": self.config.password,
            }
            resp = await client.post(MF_SESSION_URL, data=login_data)
            resp.raise_for_status()

            # ログイン成功確認
            if "sign_in" in str(resp.url):
                logger.error("ログインに失敗しました。認証情報を確認してください。")
                return False

            logger.info("マネーフォワードへのログインに成功しました")
            return True

        except httpx.HTTPError as e:
            logger.error("ログイン中にHTTPエラーが発生: %s", e)
            return False

    def _extract_csrf_token(self, html: str) -> str | None:
        """HTMLからCSRFトークンを抽出する"""
        # meta タグから取得
        marker = 'name="csrf-token" content="'
        idx = html.find(marker)
        if idx == -1:
            # input hidden から取得
            marker = 'name="authenticity_token" value="'
            idx = html.find(marker)
        if idx == -1:
            return None
        start = idx + len(marker)
        end = html.find('"', start)
        return html[start:end]

    async def fetch_accounts(self) -> FinanceSnapshot:
        """資産残高を取得する"""
        client = await self._get_client()

        try:
            # BS (貸借対照表) ページから資産情報を取得
            resp = await client.get(MF_BS_URL)
            resp.raise_for_status()
            accounts = self._parse_accounts_html(resp.text)

            snapshot = FinanceSnapshot(
                accounts=accounts,
                fetched_at=datetime.now(),
            )
            logger.info(
                "資産残高を取得しました: %d口座, 合計 ¥%s",
                len(accounts),
                f"{snapshot.total_assets:,.0f}",
            )
            return snapshot

        except httpx.HTTPError as e:
            logger.error("資産情報の取得中にエラー: %s", e)
            return FinanceSnapshot(fetched_at=datetime.now())

    def _parse_accounts_html(self, html: str) -> list[Account]:
        """資産ページのHTMLから口座情報をパースする

        マネーフォワードのHTMLは table.bs-list 内に口座が並びます。
        HTMLパーサーを使わず、シンプルなテキスト処理で抽出します。
        実際のHTML構造に合わせて調整が必要になる場合があります。
        """
        accounts: list[Account] = []

        # テーブル行を探索
        rows = html.split("<tr")
        for row in rows:
            if 'class="' not in row or "heading" in row:
                continue

            name = self._extract_text_between(row, 'class="account">', "<")
            institution = self._extract_text_between(row, 'class="institution">', "<")
            balance_str = self._extract_text_between(row, 'class="number">', "<")
            account_type = self._extract_text_between(row, 'class="type">', "<")

            if name and balance_str:
                balance = self._parse_amount(balance_str)
                accounts.append(
                    Account(
                        name=name.strip(),
                        institution=institution.strip() if institution else "",
                        balance=balance,
                        account_type=account_type.strip() if account_type else "",
                        last_updated=datetime.now(),
                    )
                )

        return accounts

    @staticmethod
    def _extract_text_between(text: str, start_marker: str, end_marker: str) -> str | None:
        """テキストから指定マーカー間の文字列を抽出する"""
        idx = text.find(start_marker)
        if idx == -1:
            return None
        start = idx + len(start_marker)
        end = text.find(end_marker, start)
        if end == -1:
            return None
        return text[start:end]

    @staticmethod
    def _parse_amount(amount_str: str) -> float:
        """金額文字列をfloatに変換する (例: "¥1,234,567" -> 1234567.0)"""
        cleaned = amount_str.replace("¥", "").replace(",", "").replace(" ", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    async def close(self) -> None:
        """HTTPクライアントをクローズする"""
        if self._client:
            await self._client.aclose()
            self._client = None


async def fetch_finance_data(config: MoneyForwardConfig) -> FinanceSnapshot:
    """マネーフォワードから資産データを取得するヘルパー関数"""
    client = MoneyForwardClient(config)
    try:
        logged_in = await client.login()
        if not logged_in:
            logger.error("マネーフォワードへのログインに失敗しました")
            return FinanceSnapshot(fetched_at=datetime.now())
        return await client.fetch_accounts()
    finally:
        await client.close()
