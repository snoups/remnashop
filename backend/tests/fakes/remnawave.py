import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

import httpx

FakeUserStore = dict[int, dict[str, Any]]


def _user_payload(
    *,
    user_id: int,
    username: str,
    expire_at: datetime,
    traffic_limit_bytes: int = 0,
    hwid_device_limit: int = 0,
    active_internal_squads: Optional[list[str]] = None,
    external_squad_uuid: Optional[str] = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "id": user_id,
        "shortUuid": uuid4().hex[:8],
        "username": username,
        "status": "ACTIVE",
        "trafficLimitBytes": traffic_limit_bytes,
        "trafficLimitStrategy": "NO_RESET",
        "expireAt": expire_at.isoformat(),
        "telegramId": None,
        "email": None,
        "description": None,
        "tag": None,
        "hwidDeviceLimit": hwid_device_limit,
        "externalSquadUuid": external_squad_uuid,
        "trojanPassword": uuid4().hex,
        "vlessUuid": str(uuid4()),
        "ssPassword": uuid4().hex,
        "lastTriggeredThreshold": 0,
        "subRevokedAt": None,
        "lastTrafficResetAt": None,
        "createdAt": now.isoformat(),
        "updatedAt": now.isoformat(),
        "subscriptionUrl": f"https://fake-panel.test/sub/{username}",
        "activeInternalSquads": [
            {"uuid": squad, "name": "fake-squad"} for squad in (active_internal_squads or [])
        ],
        "userTraffic": {
            "usedTrafficBytes": 0,
            "lifetimeUsedTrafficBytes": 0,
            "onlineAt": None,
            "firstConnectedAt": None,
            "lastConnectedNodeUuid": None,
        },
    }


def make_fake_remnawave_transport(
    store: Optional[FakeUserStore] = None,
) -> tuple[httpx.MockTransport, FakeUserStore]:
    """Fakes only the /users endpoints this plan's usecases actually call --
    create/update/extend. Any other path 404s, on purpose: a usecase reaching
    for an endpoint this fake doesn't know about should fail loudly in tests,
    not silently succeed against an accidental default response."""

    if store is None:
        store = {}
    next_id = {"value": 1000}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path == "/api/users" and request.method == "POST":
            body = json.loads(request.content)
            user_id = next_id["value"]
            next_id["value"] += 1
            expire_at = datetime.fromisoformat(body["expireAt"].replace("Z", "+00:00"))
            payload = _user_payload(
                user_id=user_id,
                username=body["username"],
                expire_at=expire_at,
                traffic_limit_bytes=body.get("trafficLimitBytes") or 0,
                hwid_device_limit=body.get("hwidDeviceLimit") or 0,
                active_internal_squads=body.get("activeInternalSquads"),
                external_squad_uuid=body.get("externalSquadUuid"),
            )
            store[user_id] = payload
            return httpx.Response(201, json={"response": payload})

        if path == "/api/users" and request.method == "PATCH":
            body = json.loads(request.content)
            user_id = body["id"]
            payload = store[user_id]
            if "trafficLimitBytes" in body:
                payload["trafficLimitBytes"] = body["trafficLimitBytes"]
            if "hwidDeviceLimit" in body:
                payload["hwidDeviceLimit"] = body["hwidDeviceLimit"]
            if body.get("expireAt") is not None:
                payload["expireAt"] = body["expireAt"]
            payload["updatedAt"] = datetime.now(timezone.utc).isoformat()
            return httpx.Response(200, json={"response": payload})

        if path.endswith("/actions/extend") and request.method == "POST":
            user_id = int(path.split("/")[-3])
            body = json.loads(request.content)
            payload = store[user_id]
            current_expire = datetime.fromisoformat(payload["expireAt"])
            payload["expireAt"] = (current_expire + timedelta(days=body["days"])).isoformat()
            payload["updatedAt"] = datetime.now(timezone.utc).isoformat()
            return httpx.Response(200, json={"response": payload})

        if path.startswith("/api/users/") and request.method == "GET":
            return _handle_get_user(path, store)

        return httpx.Response(404, json={"error": f"fake transport: no handler for {path}"})

    return httpx.MockTransport(handler), store


def _handle_get_user(path: str, store: FakeUserStore) -> httpx.Response:
    user_id = int(path.rsplit("/", 1)[-1])
    if user_id not in store:
        return httpx.Response(404, json={"message": f"user {user_id} not found"})
    return httpx.Response(200, json={"response": store[user_id]})
