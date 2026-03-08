"""Sensors for ISP EuroNet."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfCurrency
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_ACCOUNT_NAME, ATTR_SERVICE_DESCRIPTION, ATTR_SERVICE_TITLE
from .coordinator import EuroNetDataUpdateCoordinator


def _to_float(value: Any) -> float | None:
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _parse_human_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d.%m.%Y %H:%M")
    except ValueError:
        return None


SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="balance",
        name="EuroNet Balance",
        native_unit_of_measurement=UnitOfCurrency.HRYVNIA,
        icon="mdi:cash",
    ),
    SensorEntityDescription(
        key="next_write_off_amount",
        name="EuroNet Next Write-off Amount",
        native_unit_of_measurement=UnitOfCurrency.HRYVNIA,
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
        service = data.services[0] if data.services else {}

        if self.entity_description.key == "balance":
            return _to_float(user.get("balance"))
        if self.entity_description.key == "next_write_off_amount":
            return _to_float(service.get("next_service_price"))
        if self.entity_description.key == "next_write_off_date":
            return _parse_human_time(service.get("human_time"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        user = data.user
        service = data.services[0] if data.services else {}

        return {
            ATTR_ACCOUNT_NAME: user.get("name"),
            ATTR_SERVICE_TITLE: service.get("title"),
            ATTR_SERVICE_DESCRIPTION: service.get("description"),
        }
