"""Sensors for ISP EuroNet."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_ACCOUNT_NAME,
    ATTR_SERVICE_DESCRIPTION,
    ATTR_SERVICES,
    ATTR_SERVICE_TITLE,
)
from .coordinator import EuroNetDataUpdateCoordinator


def _to_float(value: Any) -> float | None:
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _parse_human_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        naive_dt = datetime.strptime(value, "%d.%m.%Y %H:%M")
    except ValueError:
        return None

    local_tz = dt_util.DEFAULT_TIME_ZONE
    if local_tz is None:
        return naive_dt.replace(tzinfo=dt_util.UTC)

    return naive_dt.replace(tzinfo=local_tz)


def _time_left_to_datetime(value: Any) -> datetime | None:
    seconds = _to_int(value)
    if seconds is None or seconds < 0:
        return None

    return dt_util.as_local(dt_util.utcnow() + timedelta(seconds=seconds))


def _service_due_datetime(service: dict[str, Any]) -> datetime | None:
    # `time_left` is a more accurate source for next write-off than `human_time`.
    due_from_time_left = _time_left_to_datetime(service.get("time_left"))
    if due_from_time_left is not None:
        return due_from_time_left

    return _parse_human_time(service.get("human_time"))


def _pick_primary_service(services: list[dict[str, Any]]) -> dict[str, Any]:
    if not services:
        return {}

    paid_services = [s for s in services if (_to_float(s.get("next_service_price")) or 0) > 0]
    candidates = paid_services or services

    def sort_key(service: dict[str, Any]) -> tuple[int, float]:
        service_dt = _service_due_datetime(service)
        service_ts = service_dt.timestamp() if service_dt else float("inf")
        return (0 if service_dt else 1, service_ts)

    return sorted(candidates, key=sort_key)[0]


def _services_attribute(services: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for service in services:
        due_dt = _service_due_datetime(service)
        normalized.append(
            {
                "title": service.get("title"),
                "description": service.get("description"),
                "next_service_price": _to_float(service.get("next_service_price")),
                "time_left": _to_int(service.get("time_left")),
                "human_time": service.get("human_time"),
                "billing_at": due_dt.isoformat() if due_dt else None,
            }
        )
    return normalized


SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="balance",
        name="EuroNet Balance",
        native_unit_of_measurement="UAH",
        icon="mdi:cash",
    ),
    SensorEntityDescription(
        key="next_write_off_amount",
        name="EuroNet Next Write-off Amount",
        native_unit_of_measurement="UAH",
        icon="mdi:currency-uah",
    ),
    SensorEntityDescription(
        key="next_write_off_date",
        name="EuroNet Next Write-off Date",
        device_class="timestamp",
        icon="mdi:calendar-clock",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EuroNet sensors from config entry."""
    coordinator: EuroNetDataUpdateCoordinator = hass.data[entry.domain][entry.entry_id]
    entities = [EuroNetSensor(coordinator, entry, description) for description in SENSORS]
    async_add_entities(entities)


class EuroNetSensor(CoordinatorEntity[EuroNetDataUpdateCoordinator], SensorEntity):
    """EuroNet Sensor entity."""

    def __init__(
        self,
        coordinator: EuroNetDataUpdateCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> dict[str, Any]:
        login = self.coordinator.api.login
        return {
            "identifiers": {("isp_euronet", login)},
            "name": f"ISP EuroNet {login}",
            "manufacturer": "ISP EuroNet",
        }

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data
        user = data.user
        service = _pick_primary_service(data.services)

        if self.entity_description.key == "balance":
            return _to_float(user.get("balance"))
        if self.entity_description.key == "next_write_off_amount":
            return _to_float(service.get("next_service_price"))
        if self.entity_description.key == "next_write_off_date":
            return _service_due_datetime(service)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        user = data.user
        service = _pick_primary_service(data.services)

        return {
            ATTR_ACCOUNT_NAME: user.get("name"),
            ATTR_SERVICE_TITLE: service.get("title"),
            ATTR_SERVICE_DESCRIPTION: service.get("description"),
            ATTR_SERVICES: _services_attribute(data.services),
        }
