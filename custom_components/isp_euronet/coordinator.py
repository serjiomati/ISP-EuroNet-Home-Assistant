"""Data coordinator for ISP EuroNet."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import logging
from typing import Any

import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_LOGIN, CONF_PASSWORD, DEFAULT_SCAN_INTERVAL, DOMAIN, SESSION_TTL_SECONDS

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://my.euronet.com.ua/cgi-bin/noapi.pl"


class EuroNetApiError(Exception):
    """Base error for EuroNet API."""


@dataclass
class EuroNetData:
    """Structured data used by sensors."""

    user: dict[str, Any]
    services: list[dict[str, Any]]


class EuroNetApiClient:
    """EuroNet API client handling auth session renewal."""

    def __init__(self, hass: HomeAssistant, login: str, password: str) -> None:
        self._hass = hass
        self._session = async_get_clientsession(hass)
        self.login = login
        self._password = password
        self._noses: str | None = None
        self._expires_at: datetime | None = None

    async def _read_json_payload(self, response: Any) -> dict[str, Any]:
        """Decode API payload even when content-type is not JSON."""
        try:
            payload = await response.json(content_type=None)
        except Exception:  # noqa: BLE001
            text_payload = await response.text()
            try:
                payload = json.loads(text_payload)
            except json.JSONDecodeError as err:
                raise EuroNetApiError("EuroNet API returned non-JSON response") from err

        if not isinstance(payload, dict):
            raise EuroNetApiError("EuroNet API returned unexpected payload type")

        return payload

    async def _authenticate(self) -> None:
        params = {"_uu": self.login, "_pp": self._password}
        async with async_timeout.timeout(15):
            response = await self._session.get(BASE_URL, params=params)
            payload = await self._read_json_payload(response)

        if response.status != 200:
            raise EuroNetApiError(f"Authentication failed with HTTP {response.status}")

        noses = payload.get("ses")
        result = str(payload.get("result", "")).strip().lower()

        # API contract is unstable: prefer presence of `ses` over exact `result` text.
        if not isinstance(noses, str) or not noses:
            if "auth" in result and "ok" not in result:
                raise EuroNetApiError("Authentication failed: invalid credentials")
            raise EuroNetApiError("Authentication failed: session token is missing")

        self._noses = noses
        self._expires_at = datetime.utcnow() + timedelta(seconds=SESSION_TTL_SECONDS - 60)

    async def _ensure_session(self) -> None:
        if self._noses and self._expires_at and datetime.utcnow() < self._expires_at:
            return
        await self._authenticate()

    async def _fetch_main_payload(self) -> dict[str, Any]:
        assert self._noses is not None

        cookies = {"noses": self._noses}
        params = {"a": "u_main"}

        async with async_timeout.timeout(15):
            response = await self._session.get(BASE_URL, params=params, cookies=cookies)
            payload = await self._read_json_payload(response)

        if response.status != 200:
            raise EuroNetApiError(f"Failed to fetch main data with HTTP {response.status}")

        return payload

    async def async_get_main(self) -> EuroNetData:
        await self._ensure_session()

        payload = await self._fetch_main_payload()
        result = payload.get("result")

        # If session became invalid between requests, refresh token once and retry.
        if not isinstance(result, dict):
            self._noses = None
            self._expires_at = None
            await self._authenticate()
            payload = await self._fetch_main_payload()
            result = payload.get("result")

        if not isinstance(result, dict):
            raise EuroNetApiError("Unexpected API payload: missing 'result' object")

        user = result.get("usr") or {}
        services = result.get("services") or []
        return EuroNetData(user=user, services=services)


class EuroNetDataUpdateCoordinator(DataUpdateCoordinator[EuroNetData]):
    """Coordinator for EuroNet polling."""

    def __init__(self, hass: HomeAssistant, login: str, password: str) -> None:
        self.api = EuroNetApiClient(hass, login=login, password=password)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> EuroNetData:
        try:
            return await self.api.async_get_main()
        except EuroNetApiError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Unexpected error while updating EuroNet data: {err}") from err


def credentials_from_entry(entry_data: dict[str, Any]) -> tuple[str, str]:
    """Read credentials from config entry data."""
    return entry_data[CONF_LOGIN], entry_data[CONF_PASSWORD]
