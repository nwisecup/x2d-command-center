"""Implicit FTPS (port 990) to the printer's storage. Blocking — run in an executor."""
from __future__ import annotations

import ftplib
import io
import logging
import re
import ssl
from typing import Any, BinaryIO

from .const import FTP_PORT, MQTT_USER

_LOGGER = logging.getLogger(__name__)


class ImplicitFTPS(ftplib.FTP_TLS):
    """ftplib does explicit TLS only; Bambu printers want implicit TLS with session reuse."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._sock = None

    @property
    def sock(self):  # type: ignore[override]
        return self._sock

    @sock.setter
    def sock(self, value) -> None:
        if value is not None and not isinstance(value, ssl.SSLSocket):
            value = self.context.wrap_socket(value)
        self._sock = value

    def ntransfercmd(self, cmd, rest=None):  # data channel must reuse the TLS session
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(conn, session=self.sock.session)
        return conn, size


_LIST_RE = re.compile(
    r"^(?P<perm>[\-dl][rwx\-]{9})\s+\S+\s+\S+\s+\S+\s+(?P<size>\d+)\s+"
    r"(?P<date>\w{3}\s+\d+\s+[\d:]+)\s+(?P<name>.+)$"
)


class BambuFtp:
    def __init__(self, host: str, access_code: str) -> None:
        self.host = host
        self.access_code = access_code

    def _connect(self) -> ImplicitFTPS:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ftp = ImplicitFTPS(context=ctx, timeout=20)
        ftp.connect(self.host, FTP_PORT)
        ftp.login(MQTT_USER, self.access_code)
        ftp.prot_p()
        return ftp

    def list(self, path: str = "/") -> list[dict[str, Any]]:
        ftp = self._connect()
        try:
            try:
                out = [
                    {"name": n, "size": int(f.get("size", 0)), "modify": f.get("modify", ""),
                     "dir": f.get("type") == "dir"}
                    for n, f in ftp.mlsd(path) if f.get("type") in ("file", "dir")
                ]
            except ftplib.error_perm:
                lines: list[str] = []
                ftp.retrlines(f"LIST {path}", lines.append)
                out = []
                for line in lines:
                    m = _LIST_RE.match(line)
                    if m:
                        out.append({"name": m["name"], "size": int(m["size"]), "modify": m["date"],
                                    "dir": m["perm"].startswith("d")})
            return sorted(out, key=lambda f: f["modify"], reverse=True)
        finally:
            _quit(ftp)

    def download(self, remote: str) -> bytes:
        ftp = self._connect()
        try:
            buf = io.BytesIO()
            ftp.retrbinary(f"RETR {remote}", buf.write)
            return buf.getvalue()
        finally:
            _quit(ftp)

    def download_to(self, remote: str, fh: BinaryIO) -> None:
        ftp = self._connect()
        try:
            ftp.retrbinary(f"RETR {remote}", fh.write)
        finally:
            _quit(ftp)

    def upload(self, fh: BinaryIO, remote: str) -> None:
        ftp = self._connect()
        try:
            ftp.storbinary(f"STOR {remote}", fh)
        finally:
            _quit(ftp)

    def delete(self, remote: str) -> None:
        ftp = self._connect()
        try:
            ftp.delete(remote)
        finally:
            _quit(ftp)

    def find_job_file(self, subtask: str) -> str | None:
        """Locate the .3mf for a running job by its subtask name."""
        if not subtask:
            return None
        want = {f"{subtask}.3mf".lower(), f"{subtask}.gcode.3mf".lower()}
        for folder in ("/cache", "/", "/model"):
            try:
                for f in self.list(folder):
                    if not f["dir"] and f["name"].lower() in want:
                        return f"{folder.rstrip('/')}/{f['name']}"
            except ftplib.all_errors as err:
                _LOGGER.debug("FTP list %s failed: %s", folder, err)
        return None


def _quit(ftp: ftplib.FTP) -> None:
    try:
        ftp.quit()
    except ftplib.all_errors:
        ftp.close()
