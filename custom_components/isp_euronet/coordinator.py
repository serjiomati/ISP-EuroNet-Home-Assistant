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


class EuroNetAuthError(EuroNetApiError):
    """Authentication error for EuroNet API."""


def _short_payload(payload: dict[str, Any]) -> str:
    """Return sanitized payload details for logging."""
    result = payload.get("result")
    result_preview = str(result)[:120] if result is not None else "<missing>"
    return f"keys={list(payload.keys())}, result={result_preview!r}, has_ses={bool(payload.get('ses'))}"


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
        _LOGGER.debug("Authenticating EuroNet login=%s", self.login)
        async with async_timeout.timeout(15):
            response = await self._session.get(BASE_URL, params=params)
            payload = await self._read_json_payload(response)

        if response.status != 200:
            _LOGGER.error("Auth HTTP error for login=%s: status=%s", self.login, response.status)
            raise EuroNetApiError(f"Authentication failed with HTTP {response.status}")

        noses = payload.get("ses")
        result = str(payload.get("result", "")).strip().lower()

        # Must follow API contract: auth succeeds only when `result` is auth ok.
        if result != "auth ok":
            _LOGGER.warning(
                "Auth rejected for login=%s. %s",
                self.login,
                _short_payload(payload),
            )
            raise EuroNetAuthError("Authentication failed: invalid credentials")

        if not isinstance(noses, str) or not noses:
            _LOGGER.error("Auth succeeded without session token for login=%s. %s", self.login, _short_payload(payload))
            raise EuroNetApiError("Authentication failed: session token is missing")

        _LOGGER.debug("Auth OK for login=%s, session token received", self.login)

        self._noses = noses
        self._expires_at = datetime.utcnow() + timedelta(seconds=SESSION_TTL_SECONDS - 60)

    async def async_validate_auth(self) -> None:
        """Validate user credentials using only the auth endpoint."""
        await self._authenticate()

    async def _ensure_session(self) -> None:
        if self._noses and self._expires_at and datetime.utcnow() < self._expires_at:
            return
        await self._authenticate()

    async def _fetch_main_payload(self) -> dict[str, Any]:
        assert self._noses is not None

        cookies = {"noses": self._noses}
        params = {"a": "u_main"}

        _LOGGER.debug("Fetching u_main for login=%s", self.login)
        async with async_timeout.timeout(15):
            response = await self._session.get(BASE_URL, params=params, cookies=cookies)
            payload = await self._read_json_payload(response)

        if response.status != 200:
            _LOGGER.error("u_main HTTP error for login=%s: status=%s", self.login, response.status)
            raise EuroNetApiError(f"Failed to fetch main data with HTTP {response.status}")

        _LOGGER.debug("u_main response for login=%s: %s", self.login, _short_payload(payload))
        return payload

    async def async_get_main(self) -> EuroNetData:
        await self._ensure_session()

        payload = await self._fetch_main_payload()
        result = payload.get("result")

        # If session became invalid between requests, refresh token once and retry.
        if not isinstance(result, dict):
            result_text = str(result).strip().lower()
            if "auth" in result_text or "session" in result_text:
                self._noses = None
                self._expires_at = None
                await self._authenticate()
                payload = await self._fetch_main_payload()
                result = payload.get("result")

        # EuroNet payload may vary; support result/data/root styles.
        if isinstance(result, dict):
            container = result
        elif isinstance(payload.get("data"), dict):
            container = payload["data"]
        else:
            container = payload if isinstance(payload, dict) else {}

        user = container.get("usr") or {}
        services = container.get("services") or []

        if not isinstance(user, dict):
            user = {}
        if not isinstance(services, list):
            services = []

        if not user and not services:
            _LOGGER.error("u_main payload missing data for login=%s. %s", self.login, _short_payload(payload))
            raise EuroNetApiError("Unexpected API payload: missing user/services data")

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
