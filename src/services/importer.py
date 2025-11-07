import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from src.core.constants import IMPORTED_TAG, REMNASHOP_PREFIX
from src.core.enums import SubscriptionStatus
from src.core.utils.time import datetime_now

from .base import BaseService


class ImporterService(BaseService):
    def get_users_from_xui(self, db_path: Path) -> list[dict[str, Any]]:
        if not self._xui_validate_db(db_path):
            raise ValueError("Invalid or inaccessible 3X-UI database")

        inbound_id = self._xui_get_inbound_with_most_clients(db_path)
        users = self._xui_get_users_from_inbound(db_path, inbound_id)

        logger.info(f"Fetched '{len(users)}' clients from inbound '{inbound_id}'")
        return self.transform_xui_users(users)

    def split_active_and_expired(
        self, users: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        now = datetime_now()
        active, expired = [], []

        for user in users:
            expire_at = user.get("expire_at")
            if isinstance(expire_at, datetime) and expire_at > now:
                active.append(user)
            else:
                expired.append(user)

        logger.info(f"Split users: '{len(active)}' active, '{len(expired)}' expired")
        return active, expired

    def transform_xui_user(self, user: dict[str, Any]) -> Optional[dict[str, Any]]:
        if not user.get("enable"):
            return None

        match = re.search(r"\d+", user.get("email", ""))
        if not match:
            return None

        telegram_id = match.group(0)
        expire_at = (
            datetime.fromtimestamp(user.get("expiryTime", 0) / 1000, tz=timezone.utc)
            if user.get("expiryTime")
            else datetime(2099, 1, 1, tzinfo=timezone.utc)
        )

        return {
            "username": f"{REMNASHOP_PREFIX}{telegram_id}",
            "telegram_id": telegram_id,
            "status": SubscriptionStatus.ACTIVE,
            "expire_at": expire_at,
            "traffic_limit_bytes": user.get("totalGB", 0),
            "hwid_device_limit": user.get("limitIp", 1),
            "tag": IMPORTED_TAG,
        }

    def transform_xui_users(self, users: list[dict[str, Any]]) -> list[dict[str, Any]]:
        transformed = [u for u in (self.transform_xui_user(u) for u in users) if u]
        logger.info(f"Transformed '{len(transformed)}' / '{len(users)}' 3X-UI users")
        return transformed

    #

    def _xui_connect_db(self, db_path: Path) -> sqlite3.Connection:
        return sqlite3.connect(db_path)

    def _xui_fetch_inbounds(self, conn: sqlite3.Connection) -> list[tuple[int, str]]:
        cursor = conn.cursor()
        cursor.execute("SELECT id, settings FROM inbounds")
        return cursor.fetchall()

    def _xui_validate_db(self, db_path: Path) -> bool:
        try:
            with self._xui_connect_db(db_path) as conn:
                return bool(self._xui_fetch_inbounds(conn))
        except sqlite3.Error as exception:
            logger.warning(f"Database validation failed: {exception}")
            return False

    def _xui_get_inbound_with_most_clients(self, db_path: Path) -> int:
        max_clients = -1
        best_inbound_id = 0

        with self._xui_connect_db(db_path) as conn:
            for inbound_id, settings_raw in self._xui_fetch_inbounds(conn):
                try:
                    settings = json.loads(settings_raw)
                except json.JSONDecodeError:
                    logger.debug(f"Skipping inbound '{inbound_id}': invalid JSON")
                    continue

                clients = settings.get("clients")
                if isinstance(clients, list) and len(clients) > max_clients:
                    max_clients, best_inbound_id = len(clients), inbound_id

        if not best_inbound_id:
            raise ValueError("No valid inbounds containing clients found")

        logger.debug(f"Selected inbound '{best_inbound_id}' with '{max_clients}' clients")
        return best_inbound_id

    def _xui_get_users_from_inbound(self, db_path: Path, inbound_id: int) -> list[dict[str, Any]]:
        with self._xui_connect_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT settings FROM inbounds WHERE id = ?", (inbound_id,))
            row = cursor.fetchone()

        if not row:
            raise ValueError(f"Inbound '{inbound_id}' not found in database")

        try:
            settings = json.loads(row[0])
        except json.JSONDecodeError as exception:
            raise ValueError(f"Invalid JSON for inbound '{inbound_id}'") from exception

        clients = settings.get("clients")
        if not isinstance(clients, list):
            raise TypeError(f"Invalid clients format in inbound '{inbound_id}'")

        return clients
