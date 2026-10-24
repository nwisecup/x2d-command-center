"""Built-in rich notifications (optional — pick notify services in Options).

Actionable buttons are routed back via `mobile_app_notification_action` using
action ids prefixed with this config entry, so several printers never collide.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import Event, HomeAssistant, callback

from .const import OPT_NOTIFY, OPT_NOTIFY_EVENTS

if TYPE_CHECKING:
    from .coordinator import X2DCoordinator

_LOGGER = logging.getLogger(__name__)
PREFIX = "BAMBUX2D"


class Notifier:
    def __init__(self, hass: HomeAssistant, coord: X2DCoordinator) -> None:
        self.hass = hass
        self.coord = coord

    @property
    def _prefix(self) -> str:
        return f"{PREFIX}_{self.coord.config_entry.entry_id}_"

    def wants(self, kind: str) -> bool:
        o = self.coord.opts
        return bool(o.get(OPT_NOTIFY)) and kind in (o.get(OPT_NOTIFY_EVENTS) or []) and self.coord.settings.get("notifications", True)

    async def send(
        self, kind: str, title: str, message: str, *, image: str | None = None,
        video: str | None = None, actions: list[tuple[str, str]] | None = None,
    ) -> None:
        if not self.wants(kind):
            return
        data: dict[str, Any] = {"tag": f"bambu_x2d_{self.coord.serial}_{kind}", "group": "bambu_x2d"}
        if image:
            data["image"] = image
        if video:
            data["video"] = video
        if actions:
            data["actions"] = [
                {"action": f"{self._prefix}{a}", "title": t, **({"destructive": True} if a in ("STOP", "SOAK_CANCEL") else {})}
                for a, t in actions
            ]
        for svc in self.coord.opts.get(OPT_NOTIFY) or []:
            domain, _, name = svc.partition(".") if "." in svc else ("notify", "", svc)
            try:
                await self.hass.services.async_call(domain, name, {"title": title, "message": message, "data": data}, blocking=False)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Notify via %s failed: %s", svc, err)

    @callback
    def handle_action(self, event: Event) -> None:
        action = str(event.data.get("action", ""))
        if not action.startswith(self._prefix):
            return
        verb = action[len(self._prefix):]
        c = self.coord
        handlers = {
            "PAUSE": c.async_pause,
            "RESUME": c.async_resume,
            "STOP": c.async_stop,
            "LIGHT": lambda: c.async_light(c.primary_light, True),
            "SOAK_START_PRINT": c.async_print_selected,
            "SOAK_CANCEL": c.async_soak_cancel,
            "HEATER_ON": c.async_ambient_heater_on,
            "QUEUE_NEXT": c.async_queue_start_next,
        }
        fn = handlers.get(verb)
        if fn:
            self.hass.async_create_task(fn())
