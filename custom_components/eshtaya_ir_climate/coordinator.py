"""Data coordinator for Eshtaya IR Climate."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TuyaApiError, TuyaAuthError, TuyaOpenApi
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    IR_BOOTSTRAP_HOURS,
    IR_LEARNING_CODE,
    IR_LEARNING_POLL_SECONDS,
    IR_LOG_WINDOW_SECONDS,
    REPORT_LOG_WINDOW_SECONDS,
)
from .ir_library import IrCommandLibrary
from .model import DeviceCapabilities

_LOGGER = logging.getLogger(__name__)


def _now_ms() -> int:
    return int(time.time() * 1000)


class EshtayaIrClimateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate one Tuya IR thermostat and its learned IR command library."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: TuyaOpenApi,
        device_id: str,
        device: dict[str, Any],
        capabilities: DeviceCapabilities,
        initial_status: dict[str, Any],
        probe_trace: list[str],
        ir_library: IrCommandLibrary,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_id}",
            config_entry=entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            always_update=True,
        )
        self.api = api
        self.device_id = device_id
        self.device = device
        self.capabilities = capabilities
        self.probe_trace = probe_trace
        self.ir_library = ir_library

        self.last_command_route: str | None = None
        self.last_ir_key: str | None = None
        self.last_ir_result: str | None = None
        self.last_ir_error: str | None = None
        self.last_report_event_time = 0
        self.last_local_command_ms = 0
        self._last_learning_poll_monotonic = 0.0
        self._last_status_poll_monotonic = 0.0

        self.data = dict(initial_status)
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        caps = self.capabilities
        if caps.power and caps.power.code not in self.data:
            self.data[caps.power.code] = False
        if caps.target_temp and caps.target_temp.code not in self.data:
            minimum = caps.target_temp.minimum or 16
            maximum = caps.target_temp.maximum or 30
            self.data[caps.target_temp.code] = caps.target_temp.encode_number(
                min(max(24, minimum), maximum)
            )
        if caps.mode and caps.mode.code not in self.data:
            values = caps.mode.enum_values
            self.data[caps.mode.code] = (
                "auto" if "auto" in values else values[0] if values else "auto"
            )
        if caps.fan and caps.fan.code not in self.data:
            values = caps.fan.enum_values
            self.data[caps.fan.code] = (
                "auto" if "auto" in values else values[0] if values else "auto"
            )

    def _report_codes(self) -> list[str]:
        result: list[str] = []
        for dp in (
            self.capabilities.power,
            self.capabilities.target_temp,
            self.capabilities.current_temp,
            self.capabilities.mode,
            self.capabilities.fan,
            self.capabilities.humidity,
            self.capabilities.status,
            self.capabilities.fault,
        ):
            if dp and dp.code not in result:
                result.append(dp.code)
        return result

    def _control_codes(self) -> set[str]:
        """DPs that can be optimistically changed by Home Assistant."""
        result: set[str] = set()
        for dp in (
            self.capabilities.power,
            self.capabilities.target_temp,
            self.capabilities.mode,
            self.capabilities.fan,
        ):
            if dp:
                result.add(dp.code)
        return result

    def _coerce_report_value(self, code: str, value: Any) -> Any:
        """Convert report-log strings back to the DP's native raw type."""
        dp = self.capabilities.dps.get(code)
        if dp is None:
            return value

        dp_type = str(dp.type or "").lower()
        if dp_type == "boolean":
            if isinstance(value, bool):
                return value
            text = str(value).strip().lower()
            if text in {"true", "1", "on", "open", "opened"}:
                return True
            if text in {
                "false", "0", "off", "close", "closed", "switch",
            }:
                return False
            return value

        if dp_type in {"integer", "value"}:
            if isinstance(value, (int, float)):
                return value
            text = str(value).strip()
            try:
                number = float(text)
            except (TypeError, ValueError):
                return value
            return int(number) if number.is_integer() else number

        return value

    def _latest_reports(
        self,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        latest: dict[str, tuple[int, Any]] = {}
        control_codes = self._control_codes()

        for row in rows:
            code = str(row.get("code") or "")
            if not code:
                continue
            try:
                event_time = int(row.get("event_time") or 0)
            except (TypeError, ValueError):
                continue

            self.last_report_event_time = max(
                self.last_report_event_time,
                event_time,
            )

            # Immediately after an HA command the report-log query can still
            # contain only the previous physical state. Do not let that stale
            # event overwrite the optimistic state.
            if (
                code in control_codes
                and self.last_local_command_ms
                and event_time < self.last_local_command_ms
            ):
                continue

            value = self._coerce_report_value(
                code,
                row.get("value"),
            )
            old = latest.get(code)
            if old is None or event_time >= old[0]:
                latest[code] = (event_time, value)

        return {
            code: value
            for code, (_, value) in latest.items()
        }

    async def async_bootstrap_ir_learning(self) -> None:
        """Import recent Smart Life ir_send commands without blocking setup."""
        end_time = _now_ms()
        start_time = end_time - IR_BOOTSTRAP_HOURS * 3600 * 1000

        try:
            operation_logs = await self.api.get_operation_logs(
                self.device_id,
                codes=[IR_LEARNING_CODE],
                event_types="5",
                start_time=start_time,
                end_time=end_time,
                size=100,
            )
        except TuyaAuthError:
            raise
        except TuyaApiError as err:
            self.last_ir_error = f"IR learning logs: {err}"
            _LOGGER.warning(
                "IR auto-learning bootstrap unavailable for ...%s: %s",
                self.device_id[-6:],
                err,
            )
            return

        report_logs: list[dict[str, Any]] = []
        try:
            report_logs = await self.api.get_report_logs(
                self.device_id,
                codes=self._report_codes(),
                start_time=start_time,
                end_time=end_time,
                size=100,
            )
        except TuyaAuthError:
            raise
        except TuyaApiError as err:
            # Correlation is optional. The exact ir_send payload and M/T/S key
            # can still be learned from operation logs alone.
            _LOGGER.debug(
                "Report-log correlation unavailable during bootstrap for ...%s: %s",
                self.device_id[-6:],
                err,
            )

        learned = await self._learn(operation_logs, report_logs)
        if learned or operation_logs:
            self.last_ir_error = None

    async def _learn(
        self,
        operation_logs: list[dict[str, Any]],
        report_logs: list[dict[str, Any]],
    ) -> int:
        caps = self.capabilities
        return await self.ir_library.async_learn(
            operation_logs,
            report_logs,
            mode_code=caps.mode.code if caps.mode else None,
            fan_code=caps.fan.code if caps.fan else None,
            target_code=caps.target_temp.code if caps.target_temp else None,
            power_code=caps.power.code if caps.power else None,
            current_state=self.data,
        )

    async def async_sync_ir_library(
        self,
        *,
        hours: int = IR_BOOTSTRAP_HOURS,
    ) -> int:
        """Manual full library sync; never fail the HA button action."""
        end_time = _now_ms()
        start_time = end_time - max(1, hours) * 3600 * 1000

        try:
            operation_logs = await self.api.get_operation_logs(
                self.device_id,
                codes=[IR_LEARNING_CODE],
                event_types="5",
                start_time=start_time,
                end_time=end_time,
                size=100,
            )
        except TuyaApiError as err:
            self.last_ir_error = f"IR library sync: {err}"
            self.last_ir_result = "sync_failed"
            _LOGGER.warning(
                "Manual IR library sync failed for ...%s: %s",
                self.device_id[-6:],
                err,
            )
            self.async_update_listeners()
            return 0

        report_logs: list[dict[str, Any]] = []
        try:
            report_logs = await self.api.get_report_logs(
                self.device_id,
                codes=self._report_codes(),
                start_time=start_time,
                end_time=end_time,
                size=100,
            )
        except TuyaApiError as err:
            _LOGGER.debug(
                "Manual IR sync will continue without report correlation "
                "for ...%s: %s",
                self.device_id[-6:],
                err,
            )

        learned = await self._learn(operation_logs, report_logs)
        self.last_ir_error = None
        self.last_ir_result = (
            "sync_learned" if learned else "sync_no_new_commands"
        )
        self.async_update_listeners()
        return learned

    async def _async_update_data(self) -> dict[str, Any]:
        merged = dict(self.data)
        now_ms = _now_ms()

        # Normal state endpoint is useful, but it fans out to several Tuya
        # surfaces. Poll it once per minute; report logs handle fast reverse sync.
        monotonic_now = time.monotonic()
        if monotonic_now - self._last_status_poll_monotonic >= 60:
            self._last_status_poll_monotonic = monotonic_now
            try:
                remote = await self.api.get_status(self.device_id)
                merged.update(remote)
            except TuyaAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except TuyaApiError as err:
                _LOGGER.debug(
                    "Normal status refresh failed for ...%s: %s",
                    self.device_id[-6:],
                    err,
                )

        # Reverse synchronization: report logs catch changes made from the
        # thermostat/remote even when Tuya's current-state endpoint lags.
        report_codes = self._report_codes()
        report_start = (
            max(
                self.last_report_event_time - 2000,
                now_ms - REPORT_LOG_WINDOW_SECONDS * 1000,
            )
            if self.last_report_event_time
            else now_ms - REPORT_LOG_WINDOW_SECONDS * 1000
        )
        recent_reports: list[dict[str, Any]] = []
        try:
            recent_reports = await self.api.get_report_logs(
                self.device_id,
                codes=report_codes,
                start_time=report_start,
                end_time=now_ms,
                size=100,
            )
            merged.update(self._latest_reports(recent_reports))
        except TuyaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TuyaApiError as err:
            _LOGGER.debug(
                "Report-log reverse sync unavailable for ...%s: %s",
                self.device_id[-6:],
                err,
            )

        # Background auto-learning: use only IoT Core operation logs.
        if (
            monotonic_now - self._last_learning_poll_monotonic
            >= IR_LEARNING_POLL_SECONDS
        ):
            self._last_learning_poll_monotonic = monotonic_now
            learning_start = (
                max(
                    self.ir_library.last_operation_event_time - 2000,
                    now_ms - IR_LOG_WINDOW_SECONDS * 1000,
                )
                if self.ir_library.last_operation_event_time
                else now_ms - IR_LOG_WINDOW_SECONDS * 1000
            )
            try:
                commands = await self.api.get_operation_logs(
                    self.device_id,
                    codes=[IR_LEARNING_CODE],
                    event_types="5",
                    start_time=learning_start,
                    end_time=now_ms,
                    size=100,
                )
                # Reuse recent report logs where possible. Correlation data is
                # optional; never discard a valid ir_send command just because
                # report-log access is unavailable.
                learning_reports = recent_reports
                if learning_start < report_start:
                    try:
                        learning_reports = await self.api.get_report_logs(
                            self.device_id,
                            codes=report_codes,
                            start_time=learning_start,
                            end_time=now_ms,
                            size=100,
                        )
                    except TuyaApiError:
                        learning_reports = recent_reports
                await self._learn(commands, learning_reports)
            except TuyaAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except TuyaApiError as err:
                self.last_ir_error = f"Background IR learning: {err}"
                _LOGGER.debug(
                    "Background IR learning unavailable for ...%s: %s",
                    self.device_id[-6:],
                    err,
                )

        return merged

    def _raw_state(self) -> tuple[bool, str | None, float | None, str | None]:
        caps = self.capabilities
        power = (
            bool(self.data.get(caps.power.code, False))
            if caps.power else True
        )
        mode_raw = (
            str(self.data.get(caps.mode.code))
            if caps.mode and self.data.get(caps.mode.code) is not None
            else None
        )
        temperature = (
            caps.target_temp.decode_number(
                self.data.get(caps.target_temp.code)
            )
            if caps.target_temp else None
        )
        fan_raw = (
            str(self.data.get(caps.fan.code))
            if caps.fan and self.data.get(caps.fan.code) is not None
            else None
        )
        return power, mode_raw, temperature, fan_raw

    async def _async_send_learned_ir(
        self,
        *,
        power: bool,
        mode_raw: str | None,
        temperature: float | None,
        fan_raw: str | None,
        optimistic: dict[str, Any],
    ) -> bool:
        ir_dp = self.capabilities.dps.get(IR_LEARNING_CODE)
        if ir_dp is None:
            self.last_ir_result = "ir_send_dp_not_exposed"
            return False

        command = self.ir_library.find(
            power=power,
            mode_raw=mode_raw,
            temperature=temperature,
            fan_raw=fan_raw,
        )
        if command is None:
            self.last_ir_result = "missing_learned_command"
            self.last_ir_key = self.ir_library.last_missing_request
            return False

        try:
            route = await self.api.send_command(
                self.device_id,
                IR_LEARNING_CODE,
                command.value,
            )
        except TuyaAuthError:
            raise
        except TuyaApiError as err:
            self.last_ir_error = str(err)
            self.last_ir_result = "ir_send_failed"
            _LOGGER.warning(
                "Learned IR command %s failed for ...%s: %s",
                command.key,
                self.device_id[-6:],
                err,
            )
            return False

        self.last_command_route = f"ir_send:{route}"
        self.last_local_command_ms = _now_ms()
        self.last_ir_key = command.key
        self.last_ir_result = "sent"
        self.last_ir_error = None

        updated = dict(self.data)
        updated.update(optimistic)
        self.async_set_updated_data(updated)
        await self.async_request_refresh()
        return True

    async def async_send(self, code: str, value: Any) -> None:
        """Generic DP control for non-climate helper entities."""
        try:
            route = await self.api.send_command(
                self.device_id,
                code,
                value,
            )
        except TuyaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TuyaApiError as err:
            raise UpdateFailed(str(err)) from err

        self.last_command_route = f"dp:{route}"
        self.last_local_command_ms = _now_ms()
        optimistic = dict(self.data)
        optimistic[code] = value
        self.async_set_updated_data(optimistic)
        await self.async_request_refresh()

    async def async_set_power(self, on: bool) -> None:
        caps = self.capabilities
        _, mode_raw, temperature, fan_raw = self._raw_state()
        optimistic = {}
        if caps.power:
            optimistic[caps.power.code] = on

        if await self._async_send_learned_ir(
            power=on,
            mode_raw=mode_raw,
            temperature=temperature,
            fan_raw=fan_raw,
            optimistic=optimistic,
        ):
            return

        # Graceful fallback: keep thermostat UI usable when that exact IR
        # combination has not been learned yet.
        if caps.power:
            await self.async_send(caps.power.code, on)

    async def async_set_temperature(self, temperature: float) -> None:
        caps = self.capabilities
        power, mode_raw, _, fan_raw = self._raw_state()
        power = True if not power else power

        optimistic = {}
        if caps.power:
            optimistic[caps.power.code] = True
        if caps.target_temp:
            optimistic[caps.target_temp.code] = caps.target_temp.encode_number(
                temperature
            )

        if await self._async_send_learned_ir(
            power=True,
            mode_raw=mode_raw,
            temperature=temperature,
            fan_raw=fan_raw,
            optimistic=optimistic,
        ):
            return

        if caps.target_temp:
            await self.async_send(
                caps.target_temp.code,
                caps.target_temp.encode_number(temperature),
            )

    async def async_set_fan(self, fan_raw: str) -> None:
        caps = self.capabilities
        _, mode_raw, temperature, _ = self._raw_state()

        optimistic = {}
        if caps.power:
            optimistic[caps.power.code] = True
        if caps.fan:
            optimistic[caps.fan.code] = fan_raw

        if await self._async_send_learned_ir(
            power=True,
            mode_raw=mode_raw,
            temperature=temperature,
            fan_raw=fan_raw,
            optimistic=optimistic,
        ):
            return

        if caps.fan:
            await self.async_send(caps.fan.code, fan_raw)

    async def async_set_hvac(self, mode_raw: str) -> None:
        caps = self.capabilities
        _, _, temperature, fan_raw = self._raw_state()

        optimistic = {}
        if caps.power:
            optimistic[caps.power.code] = True
        if caps.mode:
            optimistic[caps.mode.code] = mode_raw

        if await self._async_send_learned_ir(
            power=True,
            mode_raw=mode_raw,
            temperature=temperature,
            fan_raw=fan_raw,
            optimistic=optimistic,
        ):
            return

        commands: list[dict[str, Any]] = []
        if caps.power:
            commands.append({"code": caps.power.code, "value": True})
        if caps.mode:
            commands.append({"code": caps.mode.code, "value": mode_raw})
        if not commands:
            return

        try:
            route = await self.api.send_commands(
                self.device_id,
                commands,
            )
        except TuyaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TuyaApiError as err:
            raise UpdateFailed(str(err)) from err

        self.last_command_route = f"dp:{route}"
        self.last_local_command_ms = _now_ms()
        updated = dict(self.data)
        for command in commands:
            updated[command["code"]] = command["value"]
        self.async_set_updated_data(updated)
        await self.async_request_refresh()
