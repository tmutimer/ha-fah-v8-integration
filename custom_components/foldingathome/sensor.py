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

from .const import DOMAIN, ENTRY_TYPE_DONOR, CONF_USERNAME
from .coordinator import FAHDataUpdateCoordinator, FAHDonorCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    if entry.data.get("entry_type") == ENTRY_TYPE_DONOR:
        entities: list[SensorEntity] = [
            FAHDonorWUSensor(coordinator, entry),
            FAHDonorScoreSensor(coordinator, entry),
            FAHDonorRankSensor(coordinator, entry),
        ]
    else:
        entities = [
            FAHStatusSensor(coordinator, entry),
            FAHPPDSensor(coordinator, entry),
            FAHCPUSensor(coordinator, entry),
            FAHGPUSensor(coordinator, entry),
            FAHWorkUnitsSensor(coordinator, entry),
            FAHWUProgressSensor(coordinator, entry),
        ]

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Machine sensors
# ---------------------------------------------------------------------------

class FAHBaseSensor(CoordinatorEntity[FAHDataUpdateCoordinator], SensorEntity):
    """Base class for FAH machine sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FAHDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._entry = entry
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

    def __init__(self, coordinator: FAHDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._machine_id}_status"

    @property
    def native_value(self) -> str:
        if not self.coordinator.data:
            return "unknown"
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

    def __init__(self, coordinator: FAHDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._machine_id}_ppd"

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        units = self.coordinator.data.get("units") or []
        return sum((unit.get("ppd", 0) if unit else 0) for unit in units)


class FAHCPUSensor(FAHBaseSensor):
    """Sensor for active CPUs."""

    _attr_icon = "mdi:cpu-64-bit"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "active_cpus"

    def __init__(self, coordinator: FAHDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._machine_id}_cpus"

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        groups = self.coordinator.data.get("groups") or {}
        default_group = groups.get("") or {}
        config = default_group.get("config") or {}
        return config.get("cpus", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        info = self.coordinator.data.get("info") or {}
        return {"total_cpus": info.get("cpus", 0)}


class FAHGPUSensor(FAHBaseSensor):
    """Sensor for active GPUs."""

    _attr_icon = "mdi:expansion-card"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "active_gpus"

    def __init__(self, coordinator: FAHDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._machine_id}_gpus"

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        groups = self.coordinator.data.get("groups") or {}
        default_group = groups.get("") or {}
        config = default_group.get("config") or {}
        gpus = config.get("gpus") or {}
        return sum(1 for gpu in gpus.values() if gpu and gpu.get("enabled", False))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
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

    def __init__(self, coordinator: FAHDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._machine_id}_work_units"

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        return len(self.coordinator.data.get("units") or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
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

    def __init__(self, coordinator: FAHDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._machine_id}_wu_progress"

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        units = [u for u in (self.coordinator.data.get("units") or []) if u is not None]
        if not units:
            return None
        active = [u for u in units if u.get("state") == "RUN"] or units
        primary = max(active, key=lambda u: u.get("ppd", 0))
        return round(primary.get("wu_progress", 0) * 100, 1)


# ---------------------------------------------------------------------------
# Donor sensors
# ---------------------------------------------------------------------------

class FAHDonorBaseSensor(CoordinatorEntity[FAHDonorCoordinator], SensorEntity):
    """Base class for FAH donor sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FAHDonorCoordinator, entry: ConfigEntry) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._username = entry.data[CONF_USERNAME]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"donor_{self._username.lower()}")},
            name=f"{self._username}",
            manufacturer="Folding@home",
            model="Donor Account",
            configuration_url=f"https://stats.foldingathome.org/donor/{self._username}",
        )


class FAHDonorWUSensor(FAHDonorBaseSensor):
    """Sensor for total work units completed by a donor."""

    _attr_icon = "mdi:check-circle-outline"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_translation_key = "donor_work_units"

    def __init__(self, coordinator: FAHDonorCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"donor_{self._username.lower()}_wus"

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("wus")


class FAHDonorScoreSensor(FAHDonorBaseSensor):
    """Sensor for total score/credit earned by a donor."""

    _attr_icon = "mdi:trophy-outline"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "points"
    _attr_translation_key = "donor_score"

    def __init__(self, coordinator: FAHDonorCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"donor_{self._username.lower()}_score"

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        # API may return either field name
        return self.coordinator.data.get("credit") or self.coordinator.data.get("score")


class FAHDonorRankSensor(FAHDonorBaseSensor):
    """Sensor for global donor rank."""

    _attr_icon = "mdi:podium"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "donor_rank"

    def __init__(self, coordinator: FAHDonorCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"donor_{self._username.lower()}_rank"

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("rank")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        attrs: dict[str, Any] = {}
        # Number of donors active in the last 7 days — useful rank context
        if (active_7 := self.coordinator.data.get("active_7")) is not None:
            attrs["active_donors_7_days"] = active_7
        if teams := self.coordinator.data.get("teams"):
            attrs["teams"] = teams
        return attrs
