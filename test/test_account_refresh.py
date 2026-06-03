from __future__ import annotations

import os
import unittest
from typing import Any

os.environ.setdefault("CHATGPT2API_AUTH_KEY", "test-auth")

from services.account_service import AccountService
from services.config import config
from services import openai_backend_api


class MemoryStorage:
    def __init__(self, accounts: list[dict[str, Any]] | None = None) -> None:
        self.accounts = list(accounts or [])

    def load_accounts(self) -> list[dict[str, Any]]:
        return list(self.accounts)

    def save_accounts(self, accounts: list[dict[str, Any]]) -> None:
        self.accounts = list(accounts)

    def load_auth_keys(self) -> list[dict[str, Any]]:
        return []

    def save_auth_keys(self, auth_keys: list[dict[str, Any]]) -> None:
        pass

    def health_check(self) -> dict[str, Any]:
        return {"ok": True}

    def get_backend_info(self) -> dict[str, Any]:
        return {"type": "memory"}


class AccountRefreshTests(unittest.TestCase):
    def test_refresh_accounts_marks_401_token_abnormal_on_first_seen(self) -> None:
        service = AccountService(
            MemoryStorage(
                [
                    {
                        "access_token": "token-401",
                        "status": "正常",
                        "quota": 7,
                        "created_at": "2020-01-01 00:00:00",
                    }
                ]
            )
        )

        class UnauthorizedBackend:
            def __init__(self, access_token: str) -> None:
                self.access_token = access_token

            def get_user_info(self) -> dict[str, Any]:
                raise openai_backend_api.InvalidAccessTokenError("token invalidated (/backend-api/me)")

        old_backend = openai_backend_api.OpenAIBackendAPI
        old_auto_remove = config.data.get("auto_remove_invalid_accounts")
        openai_backend_api.OpenAIBackendAPI = UnauthorizedBackend
        config.data["auto_remove_invalid_accounts"] = False
        try:
            result = service.refresh_accounts(["token-401"])
        finally:
            openai_backend_api.OpenAIBackendAPI = old_backend
            if old_auto_remove is None:
                config.data.pop("auto_remove_invalid_accounts", None)
            else:
                config.data["auto_remove_invalid_accounts"] = old_auto_remove

        account = service.get_account("token-401")
        self.assertEqual(result["refreshed"], 0)
        self.assertEqual(len(result["errors"]), 1)
        self.assertIsNotNone(account)
        self.assertEqual(account["status"], "异常")
        self.assertEqual(account["quota"], 0)
        self.assertEqual(account["invalid_count"], 1)
        self.assertIn("token invalidated", account["last_refresh_error"])


if __name__ == "__main__":
    unittest.main()
