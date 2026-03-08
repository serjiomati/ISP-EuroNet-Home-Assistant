"""Config flow for ISP EuroNet integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_LOGIN, CONF_PASSWORD, DOMAIN
from .coordinator import EuroNetApiClient, EuroNetApiError


class EuroNetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ISP EuroNet."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            login = user_input[CONF_LOGIN]
            password = user_input[CONF_PASSWORD]

            client = EuroNetApiClient(self.hass, login=login, password=password)
            try:
                await client.async_get_main()
            except EuroNetApiError:
                errors["base"] = "auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(login)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"EuroNet {login}", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_LOGIN): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
