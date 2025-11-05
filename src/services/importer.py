import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from re import Pattern
from typing import Any, Optional
from uuid import UUID

from loguru import logger

from src.core.utils.time import datetime_now

from .base import BaseService

BOTS: dict[str, Pattern] = {
    "jolymmiles": re.compile(r"^\d+$"),
    "machka_pasla": re.compile(r"^tg_\d+$"),
    "fringg": re.compile(r"^user_\d+$"),
}


class ImporterService(BaseService):
    def get_users_from_xui(self, db_path: Path) -> list[dict[str, Any]]:
        if not self._xui_validate_db(db_path):
            raise ValueError("Invalid 3X-UI database")

        inbound_id = self._xui_get_inbound_with_most_clients(db_path)
        clients = self._xui_get_users_from_inbound(db_path, inbound_id)
        logger.info(f"Fetched '{len(clients)}' clients from inbound '{inbound_id}'")

        return self.transform_users(clients)

    def split_active_and_expired(self, users: list[dict[str, Any]]) -> tuple[list, list]:
        logger.success(users)
        active: list[dict[str, Any]] = []
        expired: list[dict[str, Any]] = []
        now = datetime_now()

        for u in users:
            (active if u["expireAt"] > now else expired).append(u)

        logger.info(f"Split users: '{len(active)}' active, '{len(expired)}' expired")
        return active, expired

    def transform_xui_user(self, user: dict[str, Any]) -> Optional[dict[str, Any]]:
        if not user.get("enable"):
            return None

        email = user.get("email", "")
        match = re.search(r"\d+", email)

        if not match:
            return None

        telegram_id = match.group(0)
        username = f"rs_{telegram_id}"
        expire_at = (
            datetime.fromtimestamp(user.get("expiryTime", 0) / 1000, tz=timezone.utc)
            if user.get("expiryTime")
            else datetime(2099, 1, 1, tzinfo=timezone.utc)
        )

        return {
            "username": username,
            "telegramId": telegram_id,
            "status": "ACTIVE",
            "expireAt": expire_at,
            "trafficLimitBytes": user.get("totalGB", 0),
            "hwidDeviceLimit": user.get("limitIp", 1),
            "tag": "IMPORTED",
        }

    def transform_remna_user(self, raw: dict) -> dict:
        return {
            "uuid": UUID(raw["uuid"]) if raw.get("uuid") else None,
            "shortUuid": raw.get("short_uuid"),
            "username": raw.get("username"),
            "status": raw.get("status"),
            "expireAt": datetime.fromisoformat(raw["expire_at"]) if raw.get("expire_at") else None,
            "createdAt": datetime.fromisoformat(raw["created_at"])
            if raw.get("created_at")
            else None,
            "trojanPassword": raw.get("trojan_password"),
            "vlessUuid": raw.get("vless_uuid"),
            "ssPassword": raw.get("ss_password"),
            "trafficLimitBytes": raw.get("traffic_limit_bytes"),
            "trafficLimitStrategy": raw.get("traffic_limit_strategy"),
            "lastTrafficResetAt": datetime.fromisoformat(raw["last_traffic_reset_at"])
            if raw.get("last_traffic_reset_at")
            else None,
            "description": raw.get("description"),
            "tag": raw.get("tag"),
            "telegramId": raw.get("telegram_id"),
            "email": raw.get("email"),
            "hwidDeviceLimit": raw.get("hwid_device_limit"),
            "activeInternalSquads": [
                UUID(squad["uuid"]) for squad in raw.get("active_internal_squads", [])
            ]
            if raw.get("active_internal_squads")
            else None,
            "externalSquadUuid": UUID(raw["external_squad_uuid"])
            if raw.get("external_squad_uuid")
            else None,
        }

    def transform_users(self, users: list[dict[str, Any]]) -> list[dict[str, Any]]:
        transformed = [u for u in (self.transform_xui_user(u) for u in users) if u]
        logger.info(f"Transformed '{len(transformed)}' of '{len(users)}' users")
        return transformed

    #

    def _xui_connect_db(self, db_path: Path) -> sqlite3.Connection:
        return sqlite3.connect(db_path)

    def _xui_fetch_inbounds(self, conn: sqlite3.Connection) -> list[tuple[int, str]]:
        cursor = conn.cursor()
        cursor.execute("SELECT id, settings FROM inbounds")
        results = cursor.fetchall()
        logger.debug(f"Fetched '{len(results)}' inbounds")
        return results

    def _xui_validate_db(self, db_path: Path) -> bool:
        try:
            with self._xui_connect_db(db_path) as conn:
                valid = bool(self._xui_fetch_inbounds(conn))
                return valid
        except sqlite3.Error as exception:
            logger.error(f"Database validation failed: {exception}")
            return False

    def _xui_get_inbound_with_most_clients(self, db_path: Path) -> int:
        max_clients = -1
        best_inbound_id = 0

        with self._xui_connect_db(db_path) as conn:
            for inbound_id, settings_raw in self._xui_fetch_inbounds(conn):
                try:
                    settings = json.loads(settings_raw)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in inbound '{inbound_id}', skipping")
                    continue

                clients = settings.get("clients")
                if isinstance(clients, list) and len(clients) > max_clients:
                    max_clients = len(clients)
                    best_inbound_id = inbound_id

        if best_inbound_id == 0:
            raise ValueError("No valid inbounds with clients found")

        return best_inbound_id

    def _xui_get_users_from_inbound(self, db_path: Path, inbound_id: int) -> list[dict[str, Any]]:
        with self._xui_connect_db(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT settings FROM inbounds WHERE id = ?", (inbound_id,))
            row = cursor.fetchone()

        if not row:
            raise ValueError(f"Inbound '{inbound_id}' not found")

        try:
            settings = json.loads(row[0])
        except json.JSONDecodeError as exception:
            raise ValueError(f"Invalid JSON for inbound '{inbound_id}'") from exception

        clients = settings.get("clients")
        if not isinstance(clients, list):
            raise TypeError(f"Invalid clients list in inbound '{inbound_id}'")

        logger.debug(f"Extracted '{len(clients)}' users from inbound '{inbound_id}'")
        return clients
