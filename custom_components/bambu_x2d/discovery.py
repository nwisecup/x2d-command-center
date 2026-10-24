"""Find Bambu printers on the LAN.

Printers announce themselves with SSDP-style NOTIFY datagrams to UDP 2021 and
answer M-SEARCH sent to UDP 1990. We listen on 2021 for a few seconds.
"""
from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any

from .const import SSDP_LISTEN_PORT, SSDP_SEARCH_PORT

_LOGGER = logging.getLogger(__name__)

MSEARCH = (
    "M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1990\r\n"
    'MAN: "ssdp:discover"\r\nMX: 3\r\nST: urn:bambulab-com:device:3dprinter:1\r\n\r\n'
).encode()


def parse_announcement(data: bytes, addr_ip: str) -> dict[str, Any] | None:
    try:
        text = data.decode(errors="ignore")
    except Exception:  # noqa: BLE001
        return None
    headers: dict[str, str] = {}
    for line in text.split("\r\n")[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    nt = headers.get("nt", "") + headers.get("st", "")
    if "bambulab" not in nt.lower():
        return None
    serial = headers.get("usn")
    if not serial:
        return None
    return {
        "serial": serial,
        "host": headers.get("location") or addr_ip,
        "name": headers.get("devname.bambu.com") or serial,
        "model": headers.get("devmodel.bambu.com") or "unknown",
        "connect": headers.get("devconnect.bambu.com"),   # lan / cloud
        "bind": headers.get("devbind.bambu.com"),
        "version": headers.get("devversion.bambu.com"),
    }


async def async_scan(timeout: float = 6.0) -> list[dict[str, Any]]:
    loop = asyncio.get_running_loop()
    found: dict[str, dict[str, Any]] = {}

    class _Proto(asyncio.DatagramProtocol):
        def datagram_received(self, data: bytes, addr) -> None:
            dev = parse_announcement(data, addr[0])
            if dev:
                found[dev["serial"]] = dev

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except OSError:
            pass
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.bind(("", SSDP_LISTEN_PORT))
    except OSError as err:
        _LOGGER.warning("Cannot listen on UDP %s for discovery: %s", SSDP_LISTEN_PORT, err)
        sock.close()
        return []
    sock.setblocking(False)
    transport, _ = await loop.create_datagram_endpoint(_Proto, sock=sock)
    try:
        for target in ("239.255.255.250", "255.255.255.255"):
            try:
                transport.sendto(MSEARCH, (target, SSDP_SEARCH_PORT))
            except OSError:
                pass
        await asyncio.sleep(timeout)
    finally:
        transport.close()
    return sorted(found.values(), key=lambda d: d["name"])
