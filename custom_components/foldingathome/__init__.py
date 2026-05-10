"""Folding@home integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, ENTRY_TYPE_DONOR, ENTRY_TYPE_MACHINE, CONF_USERNAME
from .coordinator import FAHDataUpdateCoordinator, FAHDonorCoordinator

_LOGGER = logging.getLogger(__name__)

MACHINE_PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.BUTTON]
DONOR_PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry data to new format."""
    if "machine_id" not in entry.data and "entry_type" not in entry.data:
        # Legacy machine entry — backfill fields
        if entry.unique_id:
            new_data = {
                **entry.data,
                "machine_id": entry.unique_id,
                "entry_type": ENTRY_TYPE_MACHINE,
            }
            hass.config_entries.async_update_entry(entry, data=new_data)
            _LOGGER.info("Migrated FAH entry %s with machine_id %s", entry.title, entry.unique_id)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Folding@home from config entry."""
    await async_migrate_entry(hass, entry)

    entry_type = entry.data.get("entry_type", ENTRY_TYPE_MACHINE)

    if entry_type == ENTRY_TYPE_DONOR:
        username = entry.data[CONF_USERNAME]
        _LOGGER.info("Setting up FAH donor stats for %s", username)
        coordinator = FAHDonorCoordinator(hass, username)
        await coordinator.async_config_entry_first_refresh()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, DONOR_PLATFORMS)
        _LOGGER.info("FAH donor stats setup complete for %s", username)
    else:
        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]
        _LOGGER.info("Setting up FAH integration for %s:%s", host, port)
        coordinator = FAHDataUpdateCoordinator(hass, host, port)
        await coordinator.async_initialize()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, MACHINE_PLATFORMS)
        _LOGGER.info("FAH integration setup complete for %s (connected: %s)", host, coordinator._connected)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    entry_type = entry.data.get("entry_type", ENTRY_TYPE_MACHINE)
    platforms = DONOR_PLATFORMS if entry_type == ENTRY_TYPE_DONOR else MACHINE_PLATFORMS

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, platforms):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        if hasattr(coordinator, "async_shutdown"):
            await coordinator.async_shutdown()

    return unload_ok
