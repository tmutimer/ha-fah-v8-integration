"""Config flow for Folding@home integration."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    DEFAULT_PORT,
    WEBSOCKET_PATH,
    WEBSOCKET_TIMEOUT,
    ENTRY_TYPE_MACHINE,
    ENTRY_TYPE_DONOR,
    CONF_USERNAME,
    DONOR_STATS_URL,
)

_LOGGER = logging.getLogger(__name__)

STEP_MACHINE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)

STEP_DONOR_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
    }
)


class FAHConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Folding@home."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show menu to choose machine or donor stats."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["machine", "donor"],
        )

    async def async_step_machine(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle local FAH machine setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)

            try:
                machine_info = await self._test_machine_connection(host, port)

                machine_id = machine_info.get("id")
                if machine_id:
                    await self.async_set_unique_id(machine_id)
                    self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=machine_info.get("mach_name", host),
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        "entry_type": ENTRY_TYPE_MACHINE,
                        "machine_id": machine_id,
                        "machine_name": machine_info.get("mach_name", "FAH Client"),
                    },
                )
            except asyncio.TimeoutError:
                errors["base"] = "timeout"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during machine config flow")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="machine",
            data_schema=STEP_MACHINE_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_donor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle donor stats setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()

            try:
                await self._test_donor_connection(username)
            except ValueError:
                errors["base"] = "donor_not_found"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during donor config flow")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(f"donor_{username.lower()}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{username} (Donor Stats)",
                    data={
                        "entry_type": ENTRY_TYPE_DONOR,
                        CONF_USERNAME: username,
                    },
                )

        return self.async_show_form(
            step_id="donor",
            data_schema=STEP_DONOR_DATA_SCHEMA,
            errors=errors,
        )

    async def _test_machine_connection(self, host: str, port: int) -> dict[str, Any]:
        """Test connection to a local FAH client and return machine info."""
        url = f"ws://{host}:{port}{WEBSOCKET_PATH}"

        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                url,
                timeout=aiohttp.ClientTimeout(total=WEBSOCKET_TIMEOUT),
            ) as ws:
                msg = await ws.receive(timeout=WEBSOCKET_TIMEOUT)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    return data.get("info") or {}

        raise Exception("No data received from FAH client")

    async def _test_donor_connection(self, username: str) -> dict[str, Any]:
        """Verify donor username exists on FAH stats and return their data."""
        url = DONOR_STATS_URL.format(username)
        session = async_get_clientsession(self.hass)
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status == 404:
                raise ValueError(f"Donor '{username}' not found")
            resp.raise_for_status()
            return await resp.json()
