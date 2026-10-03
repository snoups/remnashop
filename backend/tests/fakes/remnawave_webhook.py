import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any


def sign_webhook(payload: dict[str, Any], secret: str) -> tuple[bytes, dict[str, str]]:
    """Builds the exact compact-JSON body bytes and headers a real Remnawave
    webhook delivery would send, signed with the given secret. The returned
    body bytes must be sent as is: re-serializing the dict may change the
    bytes that were signed."""
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    headers = {
        "X-Remnawave-Signature": signature,
        "X-Remnawave-Timestamp": str(int(datetime.now(timezone.utc).timestamp())),
        "Content-Type": "application/json",
    }
    return body, headers


def user_event_payload(*, event: str, remnawave_user_id: int, status: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "event": event,
        "timestamp": now,
        "data": {
            "id": remnawave_user_id,
            "shortUuid": "abcd1234",
            "username": f"rs_test_{remnawave_user_id}",
            "status": status,
            "trafficLimitBytes": 0,
            "trafficLimitStrategy": "NO_RESET",
            "expireAt": now,
            "telegramId": None,
            "email": None,
            "description": None,
            "tag": None,
            "hwidDeviceLimit": 3,
            "externalSquadUuid": None,
            "trojanPassword": "x",
            "vlessUuid": "5f1e1e1e-1e1e-1e1e-1e1e-1e1e1e1e1e1e",
            "ssPassword": "x",
            "lastTriggeredThreshold": 0,
            "subRevokedAt": None,
            "lastTrafficResetAt": None,
            "createdAt": now,
            "updatedAt": now,
            "subscriptionUrl": f"https://fake-panel.test/sub/{remnawave_user_id}",
            "activeInternalSquads": [],
            "userTraffic": {
                "usedTrafficBytes": 0,
                "lifetimeUsedTrafficBytes": 0,
                "onlineAt": None,
                "firstConnectedAt": None,
                "lastConnectedNodeUuid": None,
            },
        },
    }
