import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

import httpx

FakeUserStore = dict[int, dict[str, Any]]
FakeHwidStore = dict[int, list[dict[str, Any]]]


def _user_payload(
    *,
    user_id: int,
    username: str,
    expire_at: datetime,
    traffic_limit_bytes: int = 0,
    traffic_limit_strategy: str = "NO_RESET",
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
        "trafficLimitStrategy": traffic_limit_strategy,
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


def _handle_create_user(
    request: httpx.Request, store: FakeUserStore, next_id: dict[str, int]
) -> httpx.Response:
    body = json.loads(request.content)
    user_id = next_id["value"]
    next_id["value"] += 1
    expire_at = datetime.fromisoformat(body["expireAt"].replace("Z", "+00:00"))
    payload = _user_payload(
        user_id=user_id,
        username=body["username"],
        expire_at=expire_at,
        traffic_limit_bytes=body.get("trafficLimitBytes") or 0,
        traffic_limit_strategy=body.get("trafficLimitStrategy") or "NO_RESET",
        hwid_device_limit=body.get("hwidDeviceLimit") or 0,
        active_internal_squads=body.get("activeInternalSquads"),
        external_squad_uuid=body.get("externalSquadUuid"),
    )
    store[user_id] = payload
    return httpx.Response(201, json={"response": payload})


def _handle_update_user(request: httpx.Request, store: FakeUserStore) -> httpx.Response:
    body = json.loads(request.content)
    payload = store[body["id"]]
    if "trafficLimitBytes" in body:
        payload["trafficLimitBytes"] = body["trafficLimitBytes"]
    if "hwidDeviceLimit" in body:
        payload["hwidDeviceLimit"] = body["hwidDeviceLimit"]
    if body.get("trafficLimitStrategy") is not None:
        payload["trafficLimitStrategy"] = body["trafficLimitStrategy"]
    if body.get("status") is not None:
        payload["status"] = body["status"]
    if body.get("expireAt") is not None:
        payload["expireAt"] = body["expireAt"]
        expire_at = datetime.fromisoformat(body["expireAt"].replace("Z", "+00:00"))
        if payload["status"] in ("ACTIVE", "EXPIRED"):
            payload["status"] = "EXPIRED" if expire_at <= datetime.now(timezone.utc) else "ACTIVE"
    payload["updatedAt"] = datetime.now(timezone.utc).isoformat()
    return httpx.Response(200, json={"response": payload})


def _handle_extend_user(path: str, request: httpx.Request, store: FakeUserStore) -> httpx.Response:
    user_id = int(path.split("/")[-3])
    body = json.loads(request.content)
    payload = store[user_id]
    current_expire = datetime.fromisoformat(payload["expireAt"])
    payload["expireAt"] = (current_expire + timedelta(days=body["days"])).isoformat()
    payload["updatedAt"] = datetime.now(timezone.utc).isoformat()
    return httpx.Response(200, json={"response": payload})


def _handle_get_user(path: str, store: FakeUserStore) -> httpx.Response:
    user_id = int(path.rsplit("/", 1)[-1])
    if user_id not in store:
        return httpx.Response(404, json={"message": f"user {user_id} not found"})
    return httpx.Response(200, json={"response": store[user_id]})


def _handle_delete_user(path: str, store: FakeUserStore) -> httpx.Response:
    user_id = int(path.rsplit("/", 1)[-1])
    payload = store.pop(user_id, None)
    if payload is None:
        return httpx.Response(404, json={"message": f"user {user_id} not found"})
    return httpx.Response(200, json={"response": payload})


def _handle_disable_user(path: str, store: FakeUserStore) -> httpx.Response:
    user_id = int(path.split("/")[-3])
    payload = store.get(user_id)
    if payload is None:
        return httpx.Response(404, json={"message": f"user {user_id} not found"})
    payload["status"] = "DISABLED"
    payload["updatedAt"] = datetime.now(timezone.utc).isoformat()
    return httpx.Response(200, json={"response": payload})


def _handle_enable_user(path: str, store: FakeUserStore) -> httpx.Response:
    user_id = int(path.split("/")[-3])
    payload = store.get(user_id)
    if payload is None:
        return httpx.Response(404, json={"message": f"user {user_id} not found"})
    expire_at = datetime.fromisoformat(payload["expireAt"].replace("Z", "+00:00"))
    payload["status"] = "ACTIVE" if expire_at > datetime.now(timezone.utc) else "EXPIRED"
    payload["updatedAt"] = datetime.now(timezone.utc).isoformat()
    return httpx.Response(200, json={"response": payload})


def _handle_reset_traffic(path: str, store: FakeUserStore) -> httpx.Response:
    user_id = int(path.split("/")[-3])
    payload = store.get(user_id)
    if payload is None:
        return httpx.Response(404, json={"message": f"user {user_id} not found"})
    payload["userTraffic"]["usedTrafficBytes"] = 0
    payload["lastTrafficResetAt"] = datetime.now(timezone.utc).isoformat()
    return httpx.Response(200, json={"response": payload})


def _handle_get_hwid_devices(path: str, devices: FakeHwidStore) -> httpx.Response:
    user_id = int(path.rsplit("/", 1)[-1])
    user_devices = devices.get(user_id, [])
    return httpx.Response(
        200, json={"response": {"total": len(user_devices), "devices": user_devices}}
    )


def _handle_delete_hwid_device(request: httpx.Request, devices: FakeHwidStore) -> httpx.Response:
    body = json.loads(request.content)
    user_id = body["userId"]
    hwid = body["hwid"]
    remaining = [d for d in devices.get(user_id, []) if d["hwid"] != hwid]
    devices[user_id] = remaining
    return httpx.Response(200, json={"response": {"total": len(remaining), "devices": remaining}})


def _handle_delete_all_hwid_devices(
    request: httpx.Request, devices: FakeHwidStore
) -> httpx.Response:
    body = json.loads(request.content)
    user_id = body["userId"]
    devices[user_id] = []
    return httpx.Response(200, json={"response": {"total": 0, "devices": []}})


def _handle_revoke_subscription(path: str, store: FakeUserStore) -> httpx.Response:
    user_id = int(path.split("/")[-3])
    payload = store.get(user_id)
    if payload is None:
        return httpx.Response(404, json={"message": f"user {user_id} not found"})
    payload["shortUuid"] = uuid4().hex[:8]
    payload["subscriptionUrl"] = (
        f"https://fake-panel.test/sub/{payload['username']}-{payload['shortUuid']}"
    )
    payload["updatedAt"] = datetime.now(timezone.utc).isoformat()
    return httpx.Response(200, json={"response": payload})


def _handle_users_stream(store: FakeUserStore) -> httpx.Response:
    # one page: the fake never holds more than a test's handful of users
    users = [store[user_id] for user_id in sorted(store)]
    return httpx.Response(
        200, json={"response": {"users": users, "nextCursor": None, "hasMore": False}}
    )


def _route_users(
    request: httpx.Request, path: str, store: FakeUserStore, next_id: dict[str, int]
) -> Optional[httpx.Response]:
    if path == "/api/users" and request.method == "POST":
        return _handle_create_user(request, store, next_id)
    if path == "/api/users" and request.method == "PATCH":
        return _handle_update_user(request, store)
    if path.endswith("/actions/extend") and request.method == "POST":
        return _handle_extend_user(path, request, store)
    if path.endswith("/actions/disable") and request.method == "POST":
        return _handle_disable_user(path, store)
    if path.endswith("/actions/enable") and request.method == "POST":
        return _handle_enable_user(path, store)
    if path.endswith("/actions/reset-traffic") and request.method == "POST":
        return _handle_reset_traffic(path, store)
    if path.endswith("/actions/revoke") and request.method == "POST":
        return _handle_revoke_subscription(path, store)
    if path.startswith("/api/users/") and request.method == "GET":
        return _handle_get_user(path, store)
    if path.startswith("/api/users/") and request.method == "DELETE":
        return _handle_delete_user(path, store)
    return None


def _route_hwid(
    request: httpx.Request, path: str, hwid_store: FakeHwidStore
) -> Optional[httpx.Response]:
    if path == "/api/hwid/devices/delete" and request.method == "POST":
        return _handle_delete_hwid_device(request, hwid_store)
    if path == "/api/hwid/devices/delete-all" and request.method == "POST":
        return _handle_delete_all_hwid_devices(request, hwid_store)
    if path.startswith("/api/hwid/devices/") and request.method == "GET":
        return _handle_get_hwid_devices(path, hwid_store)
    return None


def make_fake_remnawave_transport(
    store: Optional[FakeUserStore] = None,
    hwid_store: Optional[FakeHwidStore] = None,
) -> tuple[httpx.MockTransport, FakeUserStore, FakeHwidStore]:
    """Fakes the /users and /hwid/devices endpoints. Any other path 404s, so a
    usecase reaching for an unknown endpoint fails loudly."""

    if store is None:
        store = {}
    if hwid_store is None:
        hwid_store = {}
    next_id = {"value": 1000}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/users/stream" and request.method == "GET":
            return _handle_users_stream(store)
        response = _route_users(request, path, store, next_id) or _route_hwid(
            request, path, hwid_store
        )
        if response is not None:
            return response
        return httpx.Response(404, json={"error": f"fake transport: no handler for {path}"})

    return httpx.MockTransport(handler), store, hwid_store
