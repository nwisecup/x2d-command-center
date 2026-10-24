"""Local MQTT client for the printer's own broker (TLS :8883, user bblp / access code).

paho runs its network loop in its own thread; callbacks are handed back to the
caller, which marshals them onto the HA event loop. No HA imports here.
"""
from __future__ import annotations

import json
import logging
import ssl
import threading
from typing import Any, Callable

import paho.mqtt.client as mqtt

from . import commands
from .const import MQTT_PORT, MQTT_USER

_LOGGER = logging.getLogger(__name__)

RC_NOT_AUTHORIZED = {4, 5, 134, 135}


def make_ssl_context(verify: bool = False) -> ssl.SSLContext:
    """Blocking (loads CA store) — call from an executor.

    verify=False for the printer's self-signed cert; verify=True for the cloud broker.
    """
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _rc(value: Any) -> int:
    return int(getattr(value, "value", value) or 0)


class BambuMqttClient:
    def __init__(
        self,
        host: str,
        serial: str,
        access_code: str,
        on_message: Callable[[dict], None],
        on_connection: Callable[[bool, int], None],
        client_id: str | None = None,
        username: str = MQTT_USER,
        port: int = MQTT_PORT,
    ) -> None:
        self.host = host
        self.serial = serial
        self.access_code = access_code
        self.username = username
        self.port = port
        self._on_message_cb = on_message
        self._on_connection_cb = on_connection
        self._client_id = client_id or f"ha-x2d-{serial[-6:]}"
        self._client: mqtt.Client | None = None
        self._lock = threading.Lock()
        self.connected = False

    @property
    def report_topic(self) -> str:
        return f"device/{self.serial}/report"

    @property
    def request_topic(self) -> str:
        return f"device/{self.serial}/request"

    def start(self, ssl_ctx: ssl.SSLContext) -> None:
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self._client_id)
        except AttributeError:  # paho < 2.0
            client = mqtt.Client(client_id=self._client_id)
        client.username_pw_set(self.username, self.access_code)
        client.tls_set_context(ssl_ctx)
        client.reconnect_delay_set(min_delay=2, max_delay=120)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        self._client = client
        client.connect_async(self.host, self.port, keepalive=60)
        client.loop_start()

    def stop(self) -> None:
        client, self._client = self._client, None
        if client is None:
            return
        try:
            client.disconnect()
        finally:
            client.loop_stop()
        self.connected = False

    def publish(self, payload: dict) -> bool:
        with self._lock:
            if not self._client or not self.connected:
                return False
            info = self._client.publish(self.request_topic, json.dumps(payload), qos=1)
            return info.rc == mqtt.MQTT_ERR_SUCCESS

    # ---- paho callbacks (network thread)
    def _on_connect(self, client, userdata, flags, rc, *args) -> None:
        code = _rc(rc)
        if code == 0:
            self.connected = True
            client.subscribe(self.report_topic, qos=1)
            self._on_connection_cb(True, 0)
            client.publish(self.request_topic, json.dumps(commands.get_version()), qos=1)
            client.publish(self.request_topic, json.dumps(commands.pushall()), qos=1)
        else:
            self.connected = False
            self._on_connection_cb(False, code)
            if code in RC_NOT_AUTHORIZED:
                client.disconnect()  # stop hammering with a bad access code

    def _on_disconnect(self, client, userdata, *args) -> None:
        was = self.connected
        self.connected = False
        if was:
            self._on_connection_cb(False, -1)

    def _on_message(self, client, userdata, msg) -> None:
        try:
            data = json.loads(msg.payload)
        except (ValueError, UnicodeDecodeError):
            _LOGGER.debug("Non-JSON payload on %s", msg.topic)
            return
        if isinstance(data, dict):
            self._on_message_cb(data)


def probe(host: str, serial: str, access_code: str, timeout: float = 12.0) -> dict:
    """Blocking connect-and-wait-for-first-report. Used by the config flow.

    Returns the first full report. Raises PermissionError (bad code),
    ConnectionError (unreachable) or TimeoutError (no report — wrong serial?).
    """
    got: dict[str, Any] = {}
    done = threading.Event()

    def on_msg(data: dict) -> None:
        if "print" in data and data["print"].get("command") == "push_status":
            got["report"] = data
            done.set()

    def on_conn(ok: bool, rc: int) -> None:
        if not ok and rc in RC_NOT_AUTHORIZED:
            got["auth"] = True
            done.set()

    c = BambuMqttClient(host, serial, access_code, on_msg, on_conn, client_id=f"ha-x2d-probe-{serial[-4:]}")
    try:
        c.start(make_ssl_context())
    except OSError as err:
        raise ConnectionError(str(err)) from err
    try:
        if not done.wait(timeout):
            if not c.connected:
                raise ConnectionError("Could not reach the printer's MQTT broker")
            raise TimeoutError("Connected, but no status report (check the serial number)")
        if got.get("auth"):
            raise PermissionError("Access code rejected")
        return got["report"]
    finally:
        c.stop()
