"""Bambu Cloud account client — used for hybrid/cloud modes and slick enrollment.

Endpoints follow the community-documented API (same one Bambu Handy/Studio use).
Pure parsing functions are separated so they're unit-testable; network calls take
an aiohttp session from the caller.

Flow: login(email, password?) → may require an emailed verification code →
accessToken (a JWT whose payload carries the MQTT username "u_<uid>") →
device list including each printer's dev_access_code (which also unlocks
local FTPS/camera — that's why cloud enrollment can auto-fill everything).
"""
from __future__ import annotations

import base64
import binascii
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aiohttp import ClientSession

HOSTS = {
    "global": {"api": "https://api.bambulab.com", "mqtt": "us.mqtt.bambulab.com"},
    "china": {"api": "https://api.bambulab.cn", "mqtt": "cn.mqtt.bambulab.com"},
}
UA = {"User-Agent": "bambu_network_agent/01.09.05.01", "X-BBL-Client-Name": "OrcaSlicer",
      "X-BBL-Client-Type": "slicer", "X-BBL-Client-Version": "01.09.05.51"}


class CloudError(Exception):
    """API-level failure."""


class NeedsVerifyCode(Exception):
    """Login requires the emailed verification code."""


class NeedsTfa(Exception):
    """Account uses app-based two-factor; carries the tfaKey."""

    def __init__(self, tfa_key: str) -> None:
        super().__init__("tfa required")
        self.tfa_key = tfa_key


# ------------------------------------------------------------------ pure parsing
def parse_login(payload: dict[str, Any]) -> str:
    """Return accessToken or raise NeedsVerifyCode / NeedsTfa / CloudError."""
    token = payload.get("accessToken")
    if token:
        return str(token)
    login_type = str(payload.get("loginType") or "")
    if login_type == "verifyCode":
        raise NeedsVerifyCode
    if login_type == "tfa":
        raise NeedsTfa(str(payload.get("tfaKey") or ""))
    raise CloudError(payload.get("error") or payload.get("message") or "Login failed")


def uid_from_token(token: str) -> str | None:
    """MQTT username lives in the JWT payload: {"username": "u_123456789"}."""
    try:
        seg = token.split(".")[1]
        seg += "=" * (-len(seg) % 4)
        payload = json.loads(base64.urlsafe_b64decode(seg))
    except (IndexError, ValueError, binascii.Error):
        return None
    user = payload.get("username") or payload.get("preferred_username")
    return str(user) if user else None


def parse_devices(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for d in payload.get("devices", []) or []:
        out.append({
            "serial": d.get("dev_id"),
            "name": d.get("name") or d.get("dev_id"),
            "model": d.get("dev_product_name") or d.get("dev_model_name") or "unknown",
            "access_code": d.get("dev_access_code"),
            "online": bool(d.get("dev_online")),
        })
    return [d for d in out if d["serial"]]


# ------------------------------------------------------------------ API calls
class BambuCloud:
    def __init__(self, session: "ClientSession", region: str = "global") -> None:
        self.session = session
        self.region = region if region in HOSTS else "global"

    @property
    def api(self) -> str:
        return HOSTS[self.region]["api"]

    @property
    def mqtt_host(self) -> str:
        return HOSTS[self.region]["mqtt"]

    async def _post(self, path: str, body: dict) -> dict:
        async with self.session.post(f"{self.api}{path}", json=body, headers=UA, timeout=20) as resp:
            try:
                data = await resp.json(content_type=None)
            except ValueError:
                data = {}
            if resp.status in (401, 403):
                raise CloudError(data.get("message") or f"Rejected ({resp.status})")
            if resp.status >= 500:
                raise CloudError(f"Bambu cloud error {resp.status}")
            return data if isinstance(data, dict) else {}

    async def login(self, email: str, password: str = "", code: str = "") -> str:
        body: dict[str, Any] = {"account": email, "apiError": ""}
        if code:
            body["code"] = code
        else:
            body["password"] = password
        return parse_login(await self._post("/v1/user-service/user/login", body))

    async def request_code(self, email: str) -> None:
        await self._post("/v1/user-service/user/sendemail/code", {"email": email, "type": "codeLogin"})

    async def login_tfa(self, tfa_key: str, tfa_code: str) -> str:
        """App-based 2FA finishes on the website endpoint; the token comes back as a cookie."""
        url = ("https://bambulab.com" if self.region == "global" else "https://bambulab.cn") + "/api/sign-in/tfa"
        async with self.session.post(url, json={"tfaKey": tfa_key, "tfaCode": tfa_code},
                                     headers=UA, timeout=20) as resp:
            for cookie in resp.cookies.values():
                if cookie.key == "token" and cookie.value:
                    return cookie.value
            try:
                data = await resp.json(content_type=None)
            except ValueError:
                data = {}
            token = (data or {}).get("accessToken") or (data or {}).get("token")
            if token:
                return str(token)
            raise CloudError("Two-factor sign-in failed")

    async def get_devices(self, token: str) -> list[dict[str, Any]]:
        async with self.session.get(f"{self.api}/v1/iot-service/api/user/bind",
                                    headers={**UA, "Authorization": f"Bearer {token}"}, timeout=20) as resp:
            if resp.status in (401, 403):
                raise CloudError("Token expired")
            data = await resp.json(content_type=None)
        return parse_devices(data if isinstance(data, dict) else {})
