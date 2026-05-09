"""Sensor platform for Folding@home."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FAHDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: FAHDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        FAHStatusSensor(coordinator, entry),
        FAHPPDSensor(coordinator, entry),
        FAHCPUSensor(coordinator, entry),
        FAHGPUSensor(coordinator, entry),
        FAHWorkUnitsSensor(coordinator, entry),
        FAHWUProgressSensor(coordinator, entry),
    ]

    async_add_entities(entities)


class FAHBaseSensor(CoordinatorEntity[FAHDataUpdateCoordinator], SensorEntity):
    """Base class for FAH sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FAHDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._entry = entry

        # Use machine_id from entry data (set during config flow) for stable identification
        # Fall back to entry.unique_id (also the machine_id) or entry_id as last resort
        self._machine_id = entry.data.get("machine_id") or entry.unique_id or entry.entry_id
        self._machine_name = entry.data.get("machine_name", "FAH Client")

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        info = (self.coordinator.data.get("info") or {}) if self.coordinator.data else {}
        return DeviceInfo(
            identifiers={(DOMAIN, self._machine_id)},
            name=self._machine_name,
            manufacturer="Folding@home",
            model=f"FAH Client {info.get('version', 'Unknown')}",
            sw_version=info.get("version"),
        )


class FAHStatusSensor(FAHBaseSensor):
    """Sensor for folding status."""

    _attr_icon = "mdi:protein"
    _attr_translation_key = "status"

    def __init__(
        self,
        coordinator: FAHDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._machine_id}_status"

    @property
    def native_value(self) -> str:
        """Return status."""
        if not self.coordinator.data:
            return "unknown"
        # State is in the default group's config, not top-level config
        groups = self.coordinator.data.get("groups") or {}
        default_group = groups.get("") or {}
        config = default_group.get("config") or {}
        if config.get("finish"):
            return "finishing"
        if config.get("paused"):
            return "paused"
        return "folding"


class FAHPPDSensor(FAHBaseSensor):
    """Sensor for points per day."""

    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "PPD"
    _attr_translation_key = "ppd"

    def __init__(
        self,
        coordinator: FAHDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._machine_id}_ppd"

    @property
    def native_value(self) -> int:
        """Return total PPD."""
        if not self.coordinator.data:
            return 0
        units = self.coordinator.data.get("units") or []
        return sum((unit.get("ppd", 0) if unit else 0) for unit in units)


class FAHCPUSensor(FAHBaseSensor):
    """Sensor for active CPUs."""

    _attr_icon = "mdi:cpu-64-bit"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "active_cpus"

    def __init__(
        self,
        coordinator: FAHDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._machine_id}_cpus"

    @property
    def native_value(self) -> int:
        """Return active CPU count."""
        if not self.coordinator.data:
            return 0
        # CPUs allocated is in the default group's config
        groups = self.coordinator.data.get("groups") or {}
        default_group = groups.get("") or {}
        config = default_group.get("config") or {}
        return config.get("cpus", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}
        info = self.coordinator.data.get("info") or {}
        return {"total_cpus": info.get("cpus", 0)}


class FAHGPUSensor(FAHBaseSensor):
    """Sensor for active GPUs."""

    _attr_icon = "mdi:expansion-card"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "active_gpus"

    def __init__(
        self,
        coordinator: FAHDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._machine_id}_gpus"

    @property
    def native_value(self) -> int:
        """Return active GPU count."""
        if not self.coordinator.data:
            return 0
        # GPUs enabled is in the default group's config
        groups = self.coordinator.data.get("groups") or {}
        default_group = groups.get("") or {}
        config = default_group.get("config") or {}
        gpus = config.get("gpus") or {}
        # Count enabled GPUs
        return sum(1 for gpu in gpus.values() if gpu and gpu.get("enabled", False))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return GPU details."""
        if not self.coordinator.data:
            return {"total_gpus": 0, "gpus": []}

        info = self.coordinator.data.get("info") or {}
        info_gpus = info.get("gpus") or {}

        groups = self.coordinator.data.get("groups") or {}
        default_group = groups.get("") or {}
        config = default_group.get("config") or {}
        config_gpus = config.get("gpus") or {}

        gpu_list = []
        for gpu_id, gpu_info in info_gpus.items():
            if not gpu_info:
                continue
            gpu_config = config_gpus.get(gpu_id) or {}
            enabled = gpu_config.get("enabled", False)
            gpu_list.append({
                "id": gpu_id,
                "description": gpu_info.get("description", "Unknown"),
                "type": gpu_info.get("type", "unknown"),
                "enabled": enabled,
            })

        return {
            "total_gpus": len(info_gpus),
            "gpus": gpu_list,
        }


class FAHWorkUnitsSensor(FAHBaseSensor):
    """Sensor for work unit count."""

    _attr_icon = "mdi:package-variant"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "work_units"

    def __init__(
        self,
        coordinator: FAHDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._machine_id}_work_units"

    @property
    def native_value(self) -> int:
        """Return WU count."""
        if not self.coordinator.data:
            return 0
        return len(self.coordinator.data.get("units") or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return WU details."""
        if not self.coordinator.data:
            return {"units": []}
        units = self.coordinator.data.get("units") or []
        return {
            "units": [
                {
                    "project": (u.get("assignment") or {}).get("project"),
                    "progress": round(u.get("wu_progress", 0) * 100, 1),
                    "state": u.get("state"),
                    "ppd": u.get("ppd", 0),
                    "eta": u.get("eta"),
                    "tpf": u.get("tpf"),
                    "credit": (u.get("assignment") or {}).get("credit"),
                    "deadline": (u.get("assignment") or {}).get("deadline"),
                    "timeout": (u.get("assignment") or {}).get("timeout"),
                }
                for u in units
                if u is not None
            ]
        }


class FAHWUProgressSensor(FAHBaseSensor):
    """Sensor for primary work unit progress."""

    _attr_icon = "mdi:progress-clock"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_translation_key = "wu_progress"

    def __init__(
        self,
        coordinator: FAHDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._machine_id}_wu_progress"

    @property
    def native_value(self) -> float | None:
        """Return progress of the primary active work unit."""
        if not self.coordinator.data:
            return None
        units = [u for u in (self.coordinator.data.get("units") or []) if u is not None]
        if not units:
            return None
        active = [u for u in units if u.get("state") == "RUN"] or units
        primary = max(active, key=lambda u: u.get("ppd", 0))
        return round(primary.get("wu_progress", 0) * 100, 1)
