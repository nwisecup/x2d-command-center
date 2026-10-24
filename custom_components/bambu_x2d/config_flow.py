"""Enrollment: scan → pick → access code. Plus manual, re-auth, reconfigure and options."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector as sel

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import probe
from .cloud import BambuCloud, CloudError, NeedsTfa, NeedsVerifyCode, uid_from_token
from .const import (
    CONF_ACCESS_CODE,
    CONF_CLOUD,
    CONF_HOST,
    CONF_MODE,
    CONF_MODEL,
    CONF_SERIAL,
    MODE_CLOUD,
    MODE_HYBRID,
    MODE_LAN,
    DEFAULT_OPTIONS,
    DOMAIN,
    NOTIFY_EVENT_CHOICES,
    OPT_AMBIENT_HUM,
    OPT_AMBIENT_TEMP,
    OPT_CAMERA_URL,
    OPT_CURRENCY,
    OPT_DUAL_NOZZLE_T,
    OPT_ENERGY_PRICE,
    OPT_FILAMENT_PRICE,
    OPT_FILAMENT_PRICES,
    OPT_HEATER,
    OPT_HMS_LOOKUP,
    OPT_MIN_START_F,
    OPT_NOTIFY,
    OPT_NOTIFY_EVENTS,
    OPT_POWER,
    OPT_SD_URL_PREFIX,
    OPT_SOAK_BAND,
    OPT_SOAK_COLD_MAX,
    OPT_SOAK_COLD_PER_F,
    OPT_SOAK_COLD_REF_F,
    OPT_SOAK_KEEP_WARM,
    OPT_SOAK_MAX_HEAT,
    OPT_TL_ENABLED,
    OPT_TL_FPS,
    OPT_TL_KEEP_FRAMES,
    OPT_TL_RETENTION,
    OPT_TL_WIDTH,
)
from .discovery import async_scan

_LOGGER = logging.getLogger(__name__)

CODE_SCHEMA = vol.Schema({vol.Required(CONF_ACCESS_CODE): sel.TextSelector(
    sel.TextSelectorConfig(type=sel.TextSelectorType.PASSWORD))})


def _num(lo: float, hi: float, step: float = 1, unit: str | None = None) -> sel.NumberSelector:
    return sel.NumberSelector(sel.NumberSelectorConfig(min=lo, max=hi, step=step, mode=sel.NumberSelectorMode.BOX,
                                                       unit_of_measurement=unit))


class X2DConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._found: list[dict[str, Any]] = []
        self._picked: dict[str, Any] | None = None
        self._cloud: dict[str, Any] = {}        # email, region, token, uid, tfa_key
        self._cloud_devices: list[dict[str, Any]] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return X2DOptionsFlow()

    # ------------------------------------------------------------ helpers
    async def _validate(self, host: str, serial: str, code: str) -> tuple[dict | None, str | None]:
        try:
            report = await self.hass.async_add_executor_job(probe, host, serial, code)
            return report, None
        except PermissionError:
            return None, "invalid_auth"
        except TimeoutError:
            return None, "no_report"
        except ConnectionError:
            return None, "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error probing printer")
            return None, "unknown"

    # ------------------------------------------------------------ user
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["cloud", "scan", "manual"])

    # ------------------------------------------------------------ cloud sign-in
    def _cloud_api(self) -> BambuCloud:
        return BambuCloud(async_get_clientsession(self.hass), self._cloud.get("region", "global"))

    async def async_step_cloud(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._cloud = {"email": user_input["email"].strip(),
                           "region": user_input.get("region", "global")}
            api = self._cloud_api()
            try:
                if user_input.get("password"):
                    token = await api.login(self._cloud["email"], password=user_input["password"])
                    return await self._cloud_token_ok(token)
                await api.request_code(self._cloud["email"])
                return await self.async_step_cloud_code()
            except NeedsVerifyCode:
                try:
                    await api.request_code(self._cloud["email"])
                except CloudError:
                    pass
                return await self.async_step_cloud_code()
            except NeedsTfa as tfa:
                self._cloud["tfa_key"] = tfa.tfa_key
                return await self.async_step_cloud_tfa()
            except CloudError as err:
                _LOGGER.debug("Cloud login failed: %s", err)
                errors["base"] = "cloud_login"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Cloud login error")
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="cloud", errors=errors, data_schema=vol.Schema({
            vol.Required("email", default=self._cloud.get("email", "")): str,
            vol.Optional("password"): sel.TextSelector(sel.TextSelectorConfig(type=sel.TextSelectorType.PASSWORD)),
            vol.Required("region", default="global"): sel.SelectSelector(sel.SelectSelectorConfig(
                options=["global", "china"], mode=sel.SelectSelectorMode.DROPDOWN)),
        }))

    async def async_step_cloud_code(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                token = await self._cloud_api().login(self._cloud["email"], code=user_input["code"].strip())
                return await self._cloud_token_ok(token)
            except (CloudError, NeedsVerifyCode):
                errors["base"] = "cloud_code"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Cloud code login error")
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="cloud_code", errors=errors,
                                    description_placeholders={"email": self._cloud.get("email", "")},
                                    data_schema=vol.Schema({vol.Required("code"): str}))

    async def async_step_cloud_tfa(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                token = await self._cloud_api().login_tfa(self._cloud["tfa_key"], user_input["code"].strip())
                return await self._cloud_token_ok(token)
            except CloudError:
                errors["base"] = "cloud_code"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Cloud TFA error")
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="cloud_tfa", errors=errors,
                                    data_schema=vol.Schema({vol.Required("code"): str}))

    async def _cloud_token_ok(self, token: str) -> ConfigFlowResult:
        self._cloud["token"] = token
        self._cloud["uid"] = uid_from_token(token)
        try:
            devices = await self._cloud_api().get_devices(token)
        except CloudError:
            devices = []
        configured = self._async_current_ids()
        self._cloud_devices = [d for d in devices if d["serial"] not in configured]
        if not self._cloud_devices:
            return self.async_abort(reason="no_cloud_devices")
        return await self.async_step_cloud_pick()

    async def async_step_cloud_pick(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            dev = next(d for d in self._cloud_devices if d["serial"] == user_input["printer"])
            await self.async_set_unique_id(dev["serial"])
            self._abort_if_unique_id_configured()
            # Try to find it on the LAN for instant hybrid mode (best enrollment path).
            host = None
            try:
                for found in await async_scan(4.0):
                    if found["serial"] == dev["serial"]:
                        host = found["host"]
                        break
            except Exception:  # noqa: BLE001
                host = None
            cloud_data = {k: self._cloud.get(k) for k in ("email", "region", "token", "uid")}
            return self.async_create_entry(title=dev["name"], data={
                CONF_HOST: host, CONF_SERIAL: dev["serial"],
                CONF_ACCESS_CODE: dev.get("access_code") or "",
                CONF_MODEL: dev.get("model"), CONF_MODE: MODE_HYBRID if host else MODE_CLOUD,
                CONF_CLOUD: cloud_data,
            }, options=dict(DEFAULT_OPTIONS))
        options = [sel.SelectOptionDict(
            value=d["serial"], label=f"{d['name']} · {d['model']}" + ("" if d["online"] else " (offline)"),
        ) for d in self._cloud_devices]
        return self.async_show_form(step_id="cloud_pick", data_schema=vol.Schema({
            vol.Required("printer"): sel.SelectSelector(sel.SelectSelectorConfig(
                options=options, mode=sel.SelectSelectorMode.LIST)),
        }))

    async def async_step_scan(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            if user_input["printer"] == "__manual__":
                return await self.async_step_manual()
            self._picked = next(d for d in self._found if d["serial"] == user_input["printer"])
            return await self.async_step_code()

        configured = self._async_current_ids()
        self._found = [d for d in await async_scan(6.0) if d["serial"] not in configured]
        if not self._found:
            return self.async_show_form(step_id="manual", data_schema=self._manual_schema(),
                                        errors={"base": "none_found"})
        options = [sel.SelectOptionDict(
            value=d["serial"],
            label=f"{d['name']} · {d['model']} · {d['host']}" + (" (cloud mode)" if d.get("connect") == "cloud" else ""),
        ) for d in self._found] + [sel.SelectOptionDict(value="__manual__", label="Not listed — enter manually")]
        return self.async_show_form(step_id="scan", data_schema=vol.Schema({
            vol.Required("printer"): sel.SelectSelector(sel.SelectSelectorConfig(options=options, mode=sel.SelectSelectorMode.LIST)),
        }))

    async def async_step_code(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._picked
        dev = self._picked
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(dev["serial"])
            self._abort_if_unique_id_configured(updates={CONF_HOST: dev["host"]})
            report, err = await self._validate(dev["host"], dev["serial"], user_input[CONF_ACCESS_CODE].strip())
            if err:
                errors["base"] = err
            else:
                return self.async_create_entry(title=dev["name"], data={
                    CONF_HOST: dev["host"], CONF_SERIAL: dev["serial"],
                    CONF_ACCESS_CODE: user_input[CONF_ACCESS_CODE].strip(), CONF_MODEL: dev.get("model"),
                    CONF_MODE: MODE_LAN,
                }, options=dict(DEFAULT_OPTIONS))
        return self.async_show_form(step_id="code", data_schema=CODE_SCHEMA, errors=errors,
                                    description_placeholders={"name": dev["name"], "host": dev["host"],
                                                              "serial": dev["serial"]})

    def _manual_schema(self, d: dict[str, Any] | None = None) -> vol.Schema:
        d = d or {}
        return vol.Schema({
            vol.Required(CONF_HOST, default=d.get(CONF_HOST, "")): str,
            vol.Required(CONF_SERIAL, default=d.get(CONF_SERIAL, "")): str,
            vol.Required(CONF_ACCESS_CODE): sel.TextSelector(sel.TextSelectorConfig(type=sel.TextSelectorType.PASSWORD)),
            vol.Optional("name", default=d.get("name", "X2D")): str,
        })

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host, serial = user_input[CONF_HOST].strip(), user_input[CONF_SERIAL].strip().upper()
            await self.async_set_unique_id(serial)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})
            report, err = await self._validate(host, serial, user_input[CONF_ACCESS_CODE].strip())
            if err:
                errors["base"] = err
            else:
                return self.async_create_entry(title=user_input.get("name") or "X2D", data={
                    CONF_HOST: host, CONF_SERIAL: serial, CONF_ACCESS_CODE: user_input[CONF_ACCESS_CODE].strip(),
                    CONF_MODEL: "X2D", CONF_MODE: MODE_LAN,
                }, options=dict(DEFAULT_OPTIONS))
        return self.async_show_form(step_id="manual", data_schema=self._manual_schema(user_input), errors=errors)

    # ------------------------------------------------------------ reauth (access code or token)
    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        runtime = getattr(entry, "runtime_data", None)
        if runtime is not None and getattr(runtime, "cloud_auth_failed", False) and not runtime.auth_failed:
            cloud = dict(entry.data.get(CONF_CLOUD) or {})
            self._cloud = {"email": cloud.get("email", ""), "region": cloud.get("region", "global")}
            return await self.async_step_reauth_cloud()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_cloud(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Bambu token expired — email a fresh code and store the new token."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                token = await self._cloud_api().login(self._cloud["email"], code=user_input["code"].strip())
                cloud = {**(entry.data.get(CONF_CLOUD) or {}), "token": token,
                         "uid": uid_from_token(token), "email": self._cloud["email"]}
                return self.async_update_reload_and_abort(entry, data_updates={CONF_CLOUD: cloud})
            except (CloudError, NeedsVerifyCode):
                errors["base"] = "cloud_code"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Cloud reauth failed")
                errors["base"] = "cannot_connect"
        else:
            try:
                await self._cloud_api().request_code(self._cloud["email"])
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="reauth_cloud", errors=errors,
                                    description_placeholders={"email": self._cloud.get("email", "")},
                                    data_schema=vol.Schema({vol.Required("code"): str}))

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            code = user_input[CONF_ACCESS_CODE].strip()
            _report, err = await self._validate(entry.data[CONF_HOST], entry.data[CONF_SERIAL], code)
            if err:
                errors["base"] = err
            else:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_ACCESS_CODE: code})
        return self.async_show_form(step_id="reauth_confirm", data_schema=CODE_SCHEMA, errors=errors,
                                    description_placeholders={"name": entry.title})

    # ------------------------------------------------------------ reconfigure (IP changed)
    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host, code = user_input[CONF_HOST].strip(), user_input[CONF_ACCESS_CODE].strip()
            _report, err = await self._validate(host, entry.data[CONF_SERIAL], code)
            if err:
                errors["base"] = err
            else:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_HOST: host, CONF_ACCESS_CODE: code})
        return self.async_show_form(step_id="reconfigure", errors=errors, data_schema=vol.Schema({
            vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str,
            vol.Required(CONF_ACCESS_CODE, default=entry.data[CONF_ACCESS_CODE]): sel.TextSelector(
                sel.TextSelectorConfig(type=sel.TextSelectorType.PASSWORD)),
        }))


class X2DOptionsFlow(OptionsFlow):
    """Everything personal lives here: sensors, phones, prices, soak and timelapse tuning."""

    @property
    def _o(self) -> dict[str, Any]:
        return {**DEFAULT_OPTIONS, **self.config_entry.options}

    def _save(self, keys: list[str], user_input: dict[str, Any]) -> ConfigFlowResult:
        kept = {k: v for k, v in self.config_entry.options.items() if k not in keys}
        return self.async_create_entry(data={**kept, **user_input})

    def _ent(self, key: str, **cfg: Any) -> tuple[vol.Optional, sel.EntitySelector]:
        return (vol.Optional(key, description={"suggested_value": self._o.get(key)}),
                sel.EntitySelector(sel.EntitySelectorConfig(**cfg)))

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="init", menu_options=[
            "connection", "environment", "notifications", "costs", "soak", "timelapse", "advanced"])

    # ------------------------------------------------------------ connection / cloud link
    async def async_step_connection(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.config_entry
        errors: dict[str, str] = {}
        has_cloud = bool((entry.data.get(CONF_CLOUD) or {}).get("token"))
        if user_input is not None:
            if user_input.get("link_cloud"):
                self._cloud_link: dict[str, Any] = {}
                return await self.async_step_cloud_link()
            mode = user_input[CONF_MODE]
            host = (user_input.get(CONF_HOST) or "").strip() or None
            if mode != MODE_CLOUD and not host:
                errors["base"] = "host_required"
            elif mode != MODE_LAN and not has_cloud:
                errors["base"] = "cloud_required"
            else:
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_MODE: mode, CONF_HOST: host})
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_create_entry(data=dict(entry.options))
        mode_opts = [MODE_LAN] + ([MODE_HYBRID, MODE_CLOUD] if has_cloud else [])
        return self.async_show_form(step_id="connection", errors=errors, data_schema=vol.Schema({
            vol.Required(CONF_MODE, default=entry.data.get(CONF_MODE, MODE_LAN)): sel.SelectSelector(
                sel.SelectSelectorConfig(options=mode_opts, mode=sel.SelectSelectorMode.LIST,
                                         translation_key="connection_mode")),
            vol.Optional(CONF_HOST, description={"suggested_value": entry.data.get(CONF_HOST)}): str,
            vol.Optional("link_cloud", default=False): bool,
        }))

    async def async_step_cloud_link(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        from .cloud import BambuCloud, CloudError, NeedsVerifyCode  # noqa: PLC0415
        from homeassistant.helpers.aiohttp_client import async_get_clientsession  # noqa: PLC0415
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input["email"].strip()
            region = user_input.get("region", "global")
            api = BambuCloud(async_get_clientsession(self.hass), region)
            if not user_input.get("code"):
                try:
                    await api.request_code(email)
                except (CloudError, Exception):  # noqa: BLE001
                    pass
                self._cloud_link = {"email": email, "region": region}
                errors["base"] = "code_sent"
            else:
                try:
                    token = await api.login(email, code=user_input["code"].strip())
                    from .cloud import uid_from_token  # noqa: PLC0415
                    entry = self.config_entry
                    cloud = {"email": email, "region": region, "token": token, "uid": uid_from_token(token)}
                    self.hass.config_entries.async_update_entry(
                        entry, data={**entry.data, CONF_CLOUD: cloud,
                                     CONF_MODE: MODE_HYBRID if entry.data.get(CONF_HOST) else MODE_CLOUD})
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                    return self.async_create_entry(data=dict(entry.options))
                except (CloudError, NeedsVerifyCode):
                    errors["base"] = "cloud_code"
                except Exception:  # noqa: BLE001
                    errors["base"] = "cannot_connect"
        link = getattr(self, "_cloud_link", {}) or {}
        return self.async_show_form(step_id="cloud_link", errors=errors, data_schema=vol.Schema({
            vol.Required("email", default=link.get("email", "")): str,
            vol.Required("region", default=link.get("region", "global")): sel.SelectSelector(
                sel.SelectSelectorConfig(options=["global", "china"], mode=sel.SelectSelectorMode.DROPDOWN)),
            vol.Optional("code"): str,
        }))

    async def async_step_environment(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        keys = [OPT_AMBIENT_TEMP, OPT_AMBIENT_HUM, OPT_HEATER, OPT_POWER, OPT_MIN_START_F]
        if user_input is not None:
            return self._save(keys, user_input)
        o = self._o
        schema = dict([
            self._ent(OPT_AMBIENT_TEMP, domain="sensor", device_class="temperature"),
            self._ent(OPT_AMBIENT_HUM, domain="sensor", device_class="humidity"),
            self._ent(OPT_HEATER, domain=["switch", "climate", "input_boolean", "light"]),
            self._ent(OPT_POWER, domain="sensor", device_class="power"),
        ])
        schema[vol.Required(OPT_MIN_START_F, default=o[OPT_MIN_START_F])] = _num(20, 80, 1, "°F")
        return self.async_show_form(step_id="environment", data_schema=vol.Schema(schema))

    async def async_step_notifications(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        keys = [OPT_NOTIFY, OPT_NOTIFY_EVENTS]
        if user_input is not None:
            return self._save(keys, user_input)
        services = sorted(self.hass.services.async_services().get("notify", {}))
        o = self._o
        return self.async_show_form(step_id="notifications", data_schema=vol.Schema({
            vol.Optional(OPT_NOTIFY, default=[s for s in o[OPT_NOTIFY] if s in services]): sel.SelectSelector(
                sel.SelectSelectorConfig(options=services, multiple=True, mode=sel.SelectSelectorMode.DROPDOWN)),
            vol.Optional(OPT_NOTIFY_EVENTS, default=o[OPT_NOTIFY_EVENTS]): sel.SelectSelector(
                sel.SelectSelectorConfig(options=NOTIFY_EVENT_CHOICES, multiple=True,
                                         mode=sel.SelectSelectorMode.LIST, translation_key="notify_events")),
        }))

    async def async_step_costs(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        keys = [OPT_FILAMENT_PRICE, OPT_FILAMENT_PRICES, OPT_ENERGY_PRICE, OPT_CURRENCY]
        if user_input is not None:
            return self._save(keys, user_input)
        o = self._o
        return self.async_show_form(step_id="costs", data_schema=vol.Schema({
            vol.Required(OPT_FILAMENT_PRICE, default=o[OPT_FILAMENT_PRICE]): _num(0, 500, 0.5),
            vol.Optional(OPT_FILAMENT_PRICES, default=o[OPT_FILAMENT_PRICES]): str,
            vol.Required(OPT_ENERGY_PRICE, default=o[OPT_ENERGY_PRICE]): _num(0, 2, 0.001),
            vol.Required(OPT_CURRENCY, default=o[OPT_CURRENCY]): str,
        }))

    async def async_step_soak(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        keys = [OPT_SOAK_BAND, OPT_SOAK_MAX_HEAT, OPT_SOAK_KEEP_WARM, OPT_SOAK_COLD_REF_F,
                OPT_SOAK_COLD_PER_F, OPT_SOAK_COLD_MAX]
        if user_input is not None:
            return self._save(keys, user_input)
        o = self._o
        return self.async_show_form(step_id="soak", data_schema=vol.Schema({
            vol.Required(OPT_SOAK_BAND, default=o[OPT_SOAK_BAND]): _num(1, 10, 0.5, "°C"),
            vol.Required(OPT_SOAK_MAX_HEAT, default=o[OPT_SOAK_MAX_HEAT]): _num(10, 180, 5, "min"),
            vol.Required(OPT_SOAK_KEEP_WARM, default=o[OPT_SOAK_KEEP_WARM]): _num(0, 240, 5, "min"),
            vol.Required(OPT_SOAK_COLD_REF_F, default=o[OPT_SOAK_COLD_REF_F]): _num(40, 90, 1, "°F"),
            vol.Required(OPT_SOAK_COLD_PER_F, default=o[OPT_SOAK_COLD_PER_F]): _num(0, 3, 0.1, "min/°F"),
            vol.Required(OPT_SOAK_COLD_MAX, default=o[OPT_SOAK_COLD_MAX]): _num(0, 90, 1, "min"),
        }))

    async def async_step_timelapse(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        keys = [OPT_TL_ENABLED, OPT_TL_FPS, OPT_TL_WIDTH, OPT_TL_KEEP_FRAMES, OPT_TL_RETENTION]
        if user_input is not None:
            user_input[OPT_TL_WIDTH] = int(user_input[OPT_TL_WIDTH])
            return self._save(keys, user_input)
        o = self._o
        return self.async_show_form(step_id="timelapse", data_schema=vol.Schema({
            vol.Required(OPT_TL_ENABLED, default=o[OPT_TL_ENABLED]): bool,
            vol.Required(OPT_TL_FPS, default=o[OPT_TL_FPS]): _num(5, 60, 1, "fps"),
            vol.Required(OPT_TL_WIDTH, default=str(o[OPT_TL_WIDTH])): sel.SelectSelector(
                sel.SelectSelectorConfig(options=["960", "1280", "1920"])),
            vol.Required(OPT_TL_KEEP_FRAMES, default=o[OPT_TL_KEEP_FRAMES]): bool,
            vol.Required(OPT_TL_RETENTION, default=o[OPT_TL_RETENTION]): _num(0, 1000, 1, "clips"),
        }))

    async def async_step_advanced(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        keys = [OPT_HMS_LOOKUP, OPT_SD_URL_PREFIX, OPT_CAMERA_URL, OPT_DUAL_NOZZLE_T]
        if user_input is not None:
            return self._save(keys, user_input)
        o = self._o
        return self.async_show_form(step_id="advanced", data_schema=vol.Schema({
            vol.Required(OPT_HMS_LOOKUP, default=o[OPT_HMS_LOOKUP]): bool,
            vol.Required(OPT_SD_URL_PREFIX, default=o[OPT_SD_URL_PREFIX]): str,
            vol.Optional(OPT_CAMERA_URL, default=o[OPT_CAMERA_URL]): str,
            vol.Required(OPT_DUAL_NOZZLE_T, default=o[OPT_DUAL_NOZZLE_T]): bool,
        }))
