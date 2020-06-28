"""The MyQ integration."""
import asyncio
from datetime import timedelta
import logging

import pymyq
from pymyq.errors import InvalidCredentialsError, MyQError
from pymyq.api import MYQ_HEADERS as PYMYQ_HEADERS

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, MYQ_COORDINATOR, MYQ_GATEWAY, CONF_PYMYQ_HEADERS, PLATFORMS, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the MyQ component."""

    hass.data.setdefault(DOMAIN, {})

    # Replace default HTTP headers from pymyq
    for name, value in config.get(DOMAIN, {}).get(CONF_PYMYQ_HEADERS, {}).items():
        if value:
            if name in PYMYQ_HEADERS:
                _LOGGER.debug("Replacing pymyq HTTP header %s: %s (was %s)", name, value, PYMYQ_HEADERS[name])
            else:
                _LOGGER.debug("Adding pymyq HTTP header %s: %s", name, value)
            PYMYQ_HEADERS[name] = value
        elif name in PYMYQ_HEADERS:
            _LOGGER.debug("Removing pymyq HTTP header %s (was %s)", name, PYMYQ_HEADERS[name])
            del PYMYQ_HEADERS[name]

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up MyQ from a config entry."""

    websession = aiohttp_client.async_get_clientsession(hass)
    conf = entry.data

    try:
        myq = await pymyq.login(conf[CONF_USERNAME], conf[CONF_PASSWORD], websession)
    except InvalidCredentialsError as err:
        _LOGGER.error("There was an error while logging in: %s", err)
        return False
    except MyQError:
        raise ConfigEntryNotReady

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="myq devices",
        update_method=myq.update_device_info,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    hass.data[DOMAIN][entry.entry_id] = {MYQ_GATEWAY: myq, MYQ_COORDINATOR: coordinator}

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
