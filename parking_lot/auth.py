from __future__ import annotations
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from database import (
    count_admins,
    create_admin_record,
    create_user_record,
    get_admin_by_username,
    get_user_by_username,
    initialize_database,
)


class AuthManager:
    """Persistent credential manager for users and admins backed by SQLite."""

    def __init__(self, path: Path | None = None):
        storage_root = Path(__file__).resolve().parent.parent
        self.storage_path = path or storage_root / "parking_credentials.json"
        self.data: dict[str, list[dict[str, str]]] = {
            "admins": [],
            "users": [],
        }
        initialize_database()
        self._load_legacy_json()
        self._migrate_legacy_accounts()

    def _load_legacy_json(self) -> None:
        if not self.storage_path.exists():
            return

        try:
            with self.storage_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                self.data["admins"] = data.get("admins", []) or []
                self.data["users"] = data.get("users", []) or []
        except (json.JSONDecodeError, OSError):
            self.data = {"admins": [], "users": []}

    def _migrate_legacy_accounts(self) -> None:
        for admin in self.data["admins"]:
            username = admin.get("username")
            password = admin.get("password")
            salt = admin.get("salt")
            if username and password and salt:
                create_admin_record(username, password, salt)

        for user in self.data["users"]:
            username = user.get("username")
            password = user.get("password")
            salt = user.get("salt")
            if username and password and salt:
                create_user_record(username, password, salt)

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self.storage_path.open("w", encoding="utf-8") as handle:
            json.dump(self.data, handle, indent=2)

    def _hash_password(self, password: str, salt: str | None = None) -> tuple[str, str]:
        salt = salt or uuid.uuid4().hex
        raw = f"{salt}{password}".encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        return digest, salt

    def _find_account(self, accounts: list[dict[str, str]], username: str) -> dict[str, str] | None:
        normalized = username.strip().lower()
        for account in accounts:
            if account.get("username") == normalized:
                return account
        return None

    def _verify_password(self, account: dict[str, str], password: str) -> bool:
        expected_hash = account.get("password")
        salt = account.get("salt")
        if not expected_hash or not salt:
            return False
        digest, _ = self._hash_password(password, salt)
        return digest == expected_hash

    def admin_exists(self) -> bool:
        return count_admins() > 0

    def user_exists(self, username: str) -> bool:
        return get_user_by_username(username) is not None

    def username_taken(self, username: str) -> bool:
        return (
            get_admin_by_username(username) is not None
            or get_user_by_username(username) is not None
        )

    def create_admin(self, username: str, password: str) -> bool:
        if self.username_taken(username):
            return False
        digest, salt = self._hash_password(password)
        if not create_admin_record(username, digest, salt):
            return False
        self.data["admins"].append(
            {"username": username.strip().lower(), "password": digest, "salt": salt}
        )
        self._save()
        return True

    def create_user(self, username: str, password: str) -> bool:
        if self.username_taken(username):
            return False
        digest, salt = self._hash_password(password)
        if not create_user_record(username, digest, salt):
            return False
        self.data["users"].append(
            {"username": username.strip().lower(), "password": digest, "salt": salt}
        )
        self._save()
        return True

    def authenticate_admin(self, username: str, password: str) -> bool:
        account = get_admin_by_username(username)
        if not account:
            return False
        return self._verify_password(dict(account), password)

    def authenticate_user(self, username: str, password: str) -> bool:
        account = get_user_by_username(username)
        if not account:
            return False
        return self._verify_password(dict(account), password)

