"""Home-Assistant-side timelapse: one frame per layer → MP4 on finish, plus a library.

Files live under <config>/bambu_x2d/<entry_id>/ and are served only through the
integration's authenticated media view — never through the public /local path.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.components.ffmpeg import async_get_image, get_ffmpeg_manager
from homeassistant.core import HomeAssistant

from .const import DOMAIN, OPT_TL_FPS, OPT_TL_KEEP_FRAMES, OPT_TL_RETENTION, OPT_TL_WIDTH

if TYPE_CHECKING:
    from .coordinator import X2DCoordinator

_LOGGER = logging.getLogger(__name__)
SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def slug(text: str, limit: int = 60) -> str:
    return SAFE.sub("_", text).strip("_")[:limit] or "job"


def safe_name(name: str) -> str:
    """Reject anything that could escape the library folder."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise ValueError("invalid file name")
    return name


class TimelapseManager:
    def __init__(self, hass: HomeAssistant, coord: X2DCoordinator) -> None:
        self.hass = hass
        self.coord = coord
        self.base = Path(hass.config.path(DOMAIN, coord.config_entry.entry_id))
        self.root = self.base / "timelapse"
        self.frames = self.root / "frames"
        self.thumbs = self.root / "thumbs"
        self.snaps = self.base / "snapshots"
        self.job: str | None = None
        self.frame_count = 0
        self.rendering = False
        self.last_clip: str | None = None
        self._capturing = False
        self._library: list[dict[str, Any]] = []

    # ------------------------------------------------------------ setup
    async def async_setup(self) -> None:
        def _mk() -> None:
            for p in (self.root, self.frames, self.thumbs, self.snaps):
                p.mkdir(parents=True, exist_ok=True)
        await self.hass.async_add_executor_job(_mk)
        await self.async_refresh()

    @property
    def library(self) -> list[dict[str, Any]]:
        return self._library

    @property
    def total_mb(self) -> float:
        return round(sum(c["size"] for c in self._library) / 1048576, 1)

    def media_url(self, rel: str) -> str:
        return f"/api/{DOMAIN}/{self.coord.config_entry.entry_id}/media/{rel}"

    # ------------------------------------------------------------ capture
    async def start_job(self, name: str) -> None:
        self.job = f"{time.strftime('%Y%m%d_%H%M')}_{slug(name or 'print', 40)}"
        self.frame_count = 0
        await self.hass.async_add_executor_job(lambda: (self.frames / self.job).mkdir(parents=True, exist_ok=True))

    async def capture_frame(self, layer: int) -> None:
        if not self.job or self._capturing:
            return
        self._capturing = True
        try:
            img = await self.grab()
            if img:
                path = self.frames / self.job / f"layer_{layer:05d}.jpg"
                await self.hass.async_add_executor_job(path.write_bytes, img)
                self.frame_count += 1
        finally:
            self._capturing = False

    async def grab(self, width: int | None = None) -> bytes | None:
        url = self.coord.camera_url
        if not url:
            return None
        try:
            return await asyncio.wait_for(async_get_image(self.hass, url, width=width), 20)
        except (TimeoutError, asyncio.TimeoutError):
            _LOGGER.debug("Camera frame timed out")
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Camera frame failed: %s", err)
        return None

    async def snapshot(self, name: str) -> str | None:
        img = await self.grab()
        if not img:
            return None
        path = self.snaps / f"{safe_name(name)}.jpg"
        await self.hass.async_add_executor_job(path.write_bytes, img)
        return self.media_url(f"snapshots/{path.name}")

    # ------------------------------------------------------------ render
    def _ffmpeg(self) -> str:
        return get_ffmpeg_manager(self.hass).binary

    async def _run(self, args: list[str], timeout: float = 900) -> bool:
        proc = await asyncio.create_subprocess_exec(
            self._ffmpeg(), "-y", "-loglevel", "error", *args,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, err = await asyncio.wait_for(proc.communicate(), timeout)
        except (TimeoutError, asyncio.TimeoutError):
            proc.kill()
            _LOGGER.warning("ffmpeg timed out")
            return False
        if proc.returncode != 0:
            _LOGGER.warning("ffmpeg failed: %s", (err or b"").decode(errors="ignore")[-400:])
            return False
        return True

    async def finish_job(self) -> str | None:
        job, self.job = self.job, None
        if not job:
            return None
        frames = self.frames / job
        count = await self.hass.async_add_executor_job(lambda: len(list(frames.glob("*.jpg"))) if frames.exists() else 0)
        if count < 2:
            await self.hass.async_add_executor_job(shutil.rmtree, frames, True)
            return None
        clip = await self.render(job)
        if clip and not self.coord.opts[OPT_TL_KEEP_FRAMES]:
            await self.hass.async_add_executor_job(shutil.rmtree, frames, True)
        await self.prune()
        return clip

    async def render(self, job: str, fps: int | None = None, width: int | None = None) -> str | None:
        safe_name(job)
        fps = int(fps or self.coord.opts[OPT_TL_FPS])
        width = int(width or self.coord.opts[OPT_TL_WIDTH])
        src = self.frames / job
        out = self.root / f"{job}.mp4"
        self.rendering = True
        self.coord.async_update_listeners()
        try:
            ok = await self._run([
                "-framerate", str(fps), "-pattern_type", "glob", "-i", str(src / "*.jpg"),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                "-vf", f"scale={width}:-2", "-movflags", "+faststart", str(out),
            ])
        finally:
            self.rendering = False
        if not ok:
            self.coord.async_update_listeners()
            return None
        frames = await self.hass.async_add_executor_job(lambda: len(list(src.glob("*.jpg"))))
        await self._write_meta(out, {"job": job, "frames": frames, "fps": fps, "secs": round(frames / fps, 1),
                                     "source": "ha", "task": self.coord.job_name})
        await self._thumb(out)
        self.last_clip = out.name
        await self.async_refresh()
        return out.name

    async def _write_meta(self, clip: Path, meta: dict) -> None:
        meta["created"] = time.time()
        await self.hass.async_add_executor_job(clip.with_suffix(clip.suffix + ".json").write_text, json.dumps(meta))

    async def _thumb(self, clip: Path) -> None:
        await self._run(["-ss", "1", "-i", str(clip), "-frames:v", "1", "-vf", "scale=480:-2",
                         str(self.thumbs / f"{clip.name}.jpg")], timeout=60)

    async def speed_up(self, name: str, factor: int) -> str | None:
        src = self.root / safe_name(name)
        out = self.root / f"{src.stem}_x{int(factor)}.mp4"
        if not await self._run(["-i", str(src), "-filter:v", f"setpts=PTS/{int(factor)}", "-an",
                                "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)]):
            return None
        await self._write_meta(out, {"source": "speed", "from": name, "factor": int(factor)})
        await self._thumb(out)
        await self.async_refresh()
        return out.name

    async def make_gif(self, name: str, width: int = 480, fps: int = 12) -> str | None:
        src = self.root / safe_name(name)
        out = self.root / f"{src.stem}.gif"
        vf = f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse"
        if not await self._run(["-i", str(src), "-vf", vf, str(out)]):
            return None
        await self.async_refresh()
        return out.name

    async def rename(self, name: str, new: str) -> str:
        src = self.root / safe_name(name)
        dst = self.root / f"{slug(new)}{src.suffix}"

        def _mv() -> None:
            if dst.exists():
                raise FileExistsError(dst.name)
            src.rename(dst)
            for side in (src.with_suffix(src.suffix + ".json"),):
                if side.exists():
                    side.rename(dst.with_suffix(dst.suffix + ".json"))
            th = self.thumbs / f"{src.name}.jpg"
            if th.exists():
                th.rename(self.thumbs / f"{dst.name}.jpg")
        await self.hass.async_add_executor_job(_mv)
        await self.async_refresh()
        return dst.name

    async def delete(self, name: str) -> None:
        src = self.root / safe_name(name)

        def _rm() -> None:
            for p in (src, src.with_suffix(src.suffix + ".json"), self.thumbs / f"{src.name}.jpg"):
                p.unlink(missing_ok=True)
        await self.hass.async_add_executor_job(_rm)
        await self.async_refresh()

    async def frame_sets(self) -> list[dict[str, Any]]:
        def _ls() -> list[dict[str, Any]]:
            out = []
            for d in sorted(self.frames.iterdir(), reverse=True) if self.frames.exists() else []:
                if d.is_dir() and d.name != self.job:
                    out.append({"name": d.name, "frames": len(list(d.glob("*.jpg")))})
            return out
        return await self.hass.async_add_executor_job(_ls)

    async def purge_frames(self, name: str | None = None) -> None:
        def _rm() -> None:
            targets = [self.frames / safe_name(name)] if name else [d for d in self.frames.iterdir() if d.is_dir() and d.name != self.job]
            for t in targets:
                shutil.rmtree(t, ignore_errors=True)
        await self.hass.async_add_executor_job(_rm)

    async def prune(self) -> None:
        keep = int(self.coord.opts[OPT_TL_RETENTION] or 0)
        if keep <= 0:
            return
        clips = sorted((c for c in self._library if c["name"].endswith(".mp4")), key=lambda c: c["mtime"], reverse=True)
        for old in clips[keep:]:
            await self.delete(old["name"])

    # ------------------------------------------------------------ printer SD
    async def pull_from_printer(self, newest: int = 5) -> list[str]:
        ftp = self.coord.ftp

        def _pull() -> list[str]:
            pulled = []
            items = [f for f in ftp.list("/timelapse") if not f["dir"] and f["name"].lower().endswith((".mp4", ".avi"))]
            for f in items[:newest]:
                local = self.root / f"printer_{safe_name(f['name'])}"
                if local.exists() and local.stat().st_size == f["size"]:
                    continue
                with open(local, "wb") as fh:
                    ftp.download_to(f"/timelapse/{f['name']}", fh)
                local.with_suffix(local.suffix + ".json").write_text(json.dumps({"source": "printer", "created": time.time()}))
                pulled.append(local.name)
            return pulled
        pulled = await self.hass.async_add_executor_job(_pull)
        for name in pulled:
            await self._thumb(self.root / name)
        await self.async_refresh()
        return pulled

    # ------------------------------------------------------------ index
    async def async_refresh(self) -> None:
        def _scan() -> list[dict[str, Any]]:
            out = []
            if not self.root.exists():
                return out
            for p in self.root.iterdir():
                if not p.is_file() or p.suffix.lower() not in (".mp4", ".gif", ".avi"):
                    continue
                st = p.stat()
                meta: dict[str, Any] = {}
                side = p.with_suffix(p.suffix + ".json")
                if side.exists():
                    try:
                        meta = json.loads(side.read_text())
                    except ValueError:
                        meta = {}
                thumb = self.thumbs / f"{p.name}.jpg"
                out.append({
                    "name": p.name, "size": st.st_size, "mtime": st.st_mtime,
                    "secs": meta.get("secs"), "fps": meta.get("fps"), "frames": meta.get("frames"),
                    "source": meta.get("source", "ha"), "task": meta.get("task"),
                    "url": self.media_url(f"timelapse/{p.name}"),
                    "thumb": self.media_url(f"timelapse/thumbs/{thumb.name}") if thumb.exists() else None,
                })
            out.sort(key=lambda c: c["mtime"], reverse=True)
            return out
        self._library = await self.hass.async_add_executor_job(_scan)
        if self._library and not self.last_clip:
            self.last_clip = self._library[0]["name"]
        self.coord.async_update_listeners()

    def resolve(self, rel: str) -> Path | None:
        """Map a media-view relative path to a file inside our folder, or None."""
        rel = rel.lstrip("/")
        if ".." in rel.split("/"):
            return None
        path = (self.base / rel).resolve()
        try:
            path.relative_to(self.base.resolve())
        except ValueError:
            return None
        return path if path.is_file() else None
