#!/usr/bin/env python3
"""Bootstrap predefined Grafana users and organization roles.

Grafana provisions datasources and dashboards from files, but users are managed
through the HTTP API. This script is intentionally idempotent so Compose can run
it every time the stack starts.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value or ""


GRAFANA_URL = env("GRAFANA_URL", "http://grafana:3000/grafana").rstrip("/")
ADMIN_USER = env("GRAFANA_ADMIN_USER", env("GRAFANA_USER"), required=True)
ADMIN_PASSWORD = env("GRAFANA_ADMIN_PASSWORD", env("GRAFANA_PASSWORD"), required=True)
VIEWER_LOGIN = env("GRAFANA_VIEWER_USER", "viewer", required=True)
VIEWER_PASSWORD = env("GRAFANA_VIEWER_PASSWORD", required=True)
VIEWER_EMAIL = env("GRAFANA_VIEWER_EMAIL", f"{VIEWER_LOGIN}@example.local")
VIEWER_NAME = env("GRAFANA_VIEWER_NAME", "Grafana Viewer")
ORG_ID = int(env("GRAFANA_ORG_ID", "1"))
TIMEOUT_SECONDS = int(env("GRAFANA_BOOTSTRAP_TIMEOUT_SECONDS", "120"))


def api_url(path: str) -> str:
    return f"{GRAFANA_URL}/{path.lstrip('/')}"


def basic_auth_header() -> str:
    token = f"{ADMIN_USER}:{ADMIN_PASSWORD}".encode("utf-8")
    encoded = base64.b64encode(token).decode("ascii")
    return f"Basic {encoded}"


def request(method: str, path: str, payload: dict | None = None) -> tuple[int, dict | None]:
    body = None
    headers = {
        "Accept": "application/json",
        "Authorization": basic_auth_header(),
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(api_url(path), data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode("utf-8")
            return response.status, json.loads(data) if data else None
    except urllib.error.HTTPError as exc:
        data = exc.read().decode("utf-8")
        try:
            parsed = json.loads(data) if data else None
        except json.JSONDecodeError:
            parsed = {"message": data}
        return exc.code, parsed


def wait_for_grafana() -> None:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        status, _ = request("GET", "/api/health")
        if status == 200:
            return
        time.sleep(2)
    raise SystemExit(f"Grafana did not become healthy within {TIMEOUT_SECONDS}s")


def lookup_user(login_or_email: str) -> dict | None:
    query = urllib.parse.urlencode({"loginOrEmail": login_or_email})
    status, payload = request("GET", f"/api/users/lookup?{query}")
    if status == 200:
        return payload
    if status == 404:
        return None
    raise SystemExit(f"Failed to look up Grafana user {login_or_email!r}: {status} {payload}")


def create_user() -> int:
    status, payload = request(
        "POST",
        "/api/admin/users",
        {
            "name": VIEWER_NAME,
            "email": VIEWER_EMAIL,
            "login": VIEWER_LOGIN,
            "password": VIEWER_PASSWORD,
            "OrgId": ORG_ID,
        },
    )
    if status in (200, 201) and payload and "id" in payload:
        return int(payload["id"])

    # A concurrent or previous run may have created it after the lookup.
    if status in (400, 409, 412):
        existing = lookup_user(VIEWER_LOGIN) or lookup_user(VIEWER_EMAIL)
        if existing and "id" in existing:
            return int(existing["id"])

    raise SystemExit(f"Failed to create Grafana viewer user: {status} {payload}")


def ensure_user() -> int:
    existing = lookup_user(VIEWER_LOGIN) or lookup_user(VIEWER_EMAIL)
    if existing and "id" in existing:
        return int(existing["id"])
    return create_user()


def update_password(user_id: int) -> None:
    status, payload = request("PUT", f"/api/admin/users/{user_id}/password", {"password": VIEWER_PASSWORD})
    if status not in (200, 204):
        raise SystemExit(f"Failed to update Grafana viewer password: {status} {payload}")


def add_user_to_org() -> int | None:
    status, payload = request(
        "POST",
        f"/api/orgs/{ORG_ID}/users",
        {"loginOrEmail": VIEWER_LOGIN, "role": "Viewer"},
    )
    if status in (200, 201) and payload:
        return payload.get("userId")
    if status in (400, 409, 412):
        return None
    raise SystemExit(f"Failed to add Grafana viewer user to org {ORG_ID}: {status} {payload}")


def set_org_role(user_id: int) -> None:
    status, payload = request("PATCH", f"/api/orgs/{ORG_ID}/users/{user_id}", {"role": "Viewer"})
    if status in (200, 204):
        return
    if status == 404:
        added_user_id = add_user_to_org()
        if added_user_id:
            user_id = int(added_user_id)
        status, payload = request("PATCH", f"/api/orgs/{ORG_ID}/users/{user_id}", {"role": "Viewer"})
        if status in (200, 204):
            return
    raise SystemExit(f"Failed to set Grafana viewer org role: {status} {payload}")


def main() -> int:
    wait_for_grafana()
    user_id = ensure_user()
    update_password(user_id)
    set_org_role(user_id)
    print(f"Grafana viewer user {VIEWER_LOGIN!r} is present with Viewer role in org {ORG_ID}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
