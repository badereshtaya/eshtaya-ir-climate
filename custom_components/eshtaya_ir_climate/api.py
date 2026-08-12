"""Resilient async Tuya OpenAPI client for Eshtaya IR Climate."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import aiohttp


class TuyaApiError(Exception):
    """Base Tuya API error."""


class TuyaAuthError(TuyaApiError):
    """Authentication error."""


class TuyaDeviceError(TuyaApiError):
    """Device/API error."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class TuyaToken:
    """Tuya project access token."""

    access_token: str
    refresh_token: str | None
    expires_at: float

    @property
    def valid(self) -> bool:
        return bool(self.access_token) and time.time() < self.expires_at - 60


@dataclass(slots=True)
class ProbeResult:
    """Everything Tuya lets us learn about one device."""

    device: dict[str, Any] = field(default_factory=dict)
    functions: list[dict[str, Any]] = field(default_factory=list)
    status_schema: list[dict[str, Any]] = field(default_factory=list)
    live_status: dict[str, Any] = field(default_factory=dict)
    category: str = ""
    trace: list[str] = field(default_factory=list)


def _rows(payload: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    return []


def _merge_rows(
    target: dict[str, dict[str, Any]],
    rows: list[dict[str, Any]],
) -> None:
    for row in rows:
        code = str(
            row.get("code")
            or row.get("dp_code")
            or row.get("identifier")
            or row.get("name")
            or ""
        ).strip()
        if not code:
            continue
        old = target.get(code, {})
        merged = dict(old)
        for key, value in row.items():
            # Prefer non-empty metadata.
            if value not in (None, "", [], {}, "()"):
                merged[key] = value
        merged.setdefault("code", code)
        target[code] = merged


def _merge_status(target: dict[str, Any], payload: Any) -> None:
    rows = _rows(payload, "status", "properties", "list", "data")
    for row in rows:
        code = str(
            row.get("code")
            or row.get("dp_code")
            or row.get("identifier")
            or ""
        ).strip()
        if code and "value" in row:
            target[code] = row.get("value")


class TuyaOpenApi:
    """Tuya Cloud client that degrades gracefully across API generations."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        endpoint: str,
        access_id: str,
        access_secret: str,
    ) -> None:
        self._session = session
        self._endpoint = endpoint.rstrip("/")
        self._access_id = access_id.strip()
        self._access_secret = access_secret.strip()
        self._token: TuyaToken | None = None

    @staticmethod
    def _sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _signature(
        self,
        method: str,
        path_with_query: str,
        body: bytes,
        timestamp: str,
        nonce: str,
        access_token: str = "",
    ) -> str:
        string_to_sign = (
            f"{method.upper()}\n"
            f"{self._sha256(body)}\n"
            f"\n"
            f"{path_with_query}"
        )
        payload = (
            self._access_id
            + access_token
            + timestamp
            + nonce
            + string_to_sign
        )
        return hmac.new(
            self._access_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest().upper()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        json_body: Any | None = None,
        token_required: bool = True,
    ) -> Any:
        if token_required:
            await self.ensure_token()

        query_string = urlencode(query or {}, doseq=True)
        path_with_query = path + (f"?{query_string}" if query_string else "")
        body = (
            json.dumps(
                json_body,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
            if json_body is not None
            else b""
        )

        timestamp = str(int(time.time() * 1000))
        nonce = uuid.uuid4().hex
        access_token = (
            self._token.access_token
            if token_required and self._token is not None
            else ""
        )
        sign = self._signature(
            method,
            path_with_query,
            body,
            timestamp,
            nonce,
            access_token,
        )

        headers = {
            "client_id": self._access_id,
            "sign": sign,
            "sign_method": "HMAC-SHA256",
            "t": timestamp,
            "nonce": nonce,
            "lang": "en",
        }
        if token_required:
            headers["access_token"] = access_token
        if json_body is not None:
            headers["Content-Type"] = "application/json"

        try:
            async with self._session.request(
                method,
                f"{self._endpoint}{path_with_query}",
                headers=headers,
                data=body if json_body is not None else None,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise TuyaApiError(
                f"Network error communicating with Tuya: {err}"
            ) from err
        except json.JSONDecodeError as err:
            raise TuyaApiError("Tuya returned invalid JSON") from err

        if not isinstance(payload, dict):
            raise TuyaApiError("Unexpected Tuya response")

        if not payload.get("success", False):
            code = str(payload.get("code", "unknown"))
            msg = str(payload.get("msg", "Unknown Tuya API error"))
            if code in {
                "1010", "1011", "1106", "1109", "1110",
                "28841002", "28841008",
            }:
                raise TuyaAuthError(f"{code}: {msg}")
            raise TuyaDeviceError(f"{code}: {msg}", code=code)

        return payload.get("result")

    async def _optional(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        json_body: Any | None = None,
        trace: list[str] | None = None,
    ) -> Any | None:
        """Try an API surface without allowing one unsupported endpoint to fail setup."""
        try:
            result = await self._request(
                method,
                path,
                query=query,
                json_body=json_body,
            )
        except TuyaAuthError:
            raise
        except TuyaApiError as err:
            if trace is not None:
                trace.append(f"ERR {method} {path}: {err}")
            return None

        if trace is not None:
            empty = result in (None, "", [], {})
            trace.append(
                f"OK {method} {path}: {'empty' if empty else 'data'}"
            )
        return result

    async def ensure_token(self) -> None:
        if self._token is not None and self._token.valid:
            return

        result = await self._request(
            "GET",
            "/v1.0/token",
            query={"grant_type": 1},
            token_required=False,
        )
        if not isinstance(result, dict) or not result.get("access_token"):
            raise TuyaAuthError("Tuya did not return an access token")

        expire = int(result.get("expire", 7200))
        self._token = TuyaToken(
            access_token=str(result["access_token"]),
            refresh_token=(
                str(result["refresh_token"])
                if result.get("refresh_token")
                else None
            ),
            expires_at=time.time() + expire,
        )

    async def get_device(self, device_id: str) -> dict[str, Any]:
        """Get device details through multiple Tuya API generations."""
        trace: list[str] = []
        for path in (
            f"/v2.0/cloud/thing/{device_id}",
            f"/v1.0/devices/{device_id}",
            f"/v1.1/iot-03/devices/{device_id}",
        ):
            result = await self._optional("GET", path, trace=trace)
            if isinstance(result, dict) and result:
                # Some v2 responses nest the thing.
                for key in ("device", "thing"):
                    if isinstance(result.get(key), dict):
                        result = result[key]
                        break
                return result
        raise TuyaDeviceError(
            "Tuya accepted the credentials but the device details could not be read"
        )

    async def probe_device(self, device_id: str) -> ProbeResult:
        """Probe all useful metadata/status APIs and merge the non-empty answers."""
        probe = ProbeResult()
        probe.device = await self.get_device(device_id)
        probe.category = str(
            probe.device.get("category")
            or probe.device.get("category_code")
            or ""
        ).strip()

        function_map: dict[str, dict[str, Any]] = {}
        status_schema_map: dict[str, dict[str, Any]] = {}

        # Embedded status from device details is often useful even when the
        # standard-status API returns an empty success.
        _merge_status(probe.live_status, probe.device.get("status"))

        # Specification APIs: DO NOT stop at a successful-but-empty response.
        for path in (
            f"/v1.0/iot-03/devices/{device_id}/specification",
            f"/v1.2/iot-03/devices/{device_id}/specification",
            f"/v1.0/devices/{device_id}/specifications",
            f"/v1.1/devices/{device_id}/specifications",
        ):
            result = await self._optional("GET", path, trace=probe.trace)
            if not isinstance(result, dict):
                continue
            if not probe.category:
                probe.category = str(result.get("category") or "").strip()
            _merge_rows(
                function_map,
                _rows(result, "functions", "function", "instructions"),
            )
            _merge_rows(
                status_schema_map,
                _rows(result, "status", "status_set", "statuses"),
            )

        # Device function APIs: both IoT Core standard/DP mode and Smart Home
        # legacy surfaces are intentionally queried and merged.
        for path in (
            f"/v1.0/iot-03/devices/{device_id}/functions",
            f"/v1.0/devices/{device_id}/functions",
        ):
            result = await self._optional("GET", path, trace=probe.trace)
            if isinstance(result, dict):
                if not probe.category:
                    probe.category = str(result.get("category") or "").strip()
                _merge_rows(function_map, _rows(result, "functions", "list"))

        # Category function/status sets can fill metadata hidden at device level.
        if probe.category:
            for path in (
                f"/v1.0/iot-03/categories/{probe.category}/functions",
                f"/v1.0/functions/{probe.category}",
            ):
                result = await self._optional("GET", path, trace=probe.trace)
                if isinstance(result, dict):
                    _merge_rows(
                        function_map,
                        _rows(result, "functions", "list"),
                    )

            result = await self._optional(
                "GET",
                f"/v1.0/iot-03/categories/{probe.category}/status",
                trace=probe.trace,
            )
            if isinstance(result, dict):
                _merge_rows(
                    status_schema_map,
                    _rows(result, "status", "list"),
                )

        # Latest state: merge every non-empty source instead of trusting the first.
        for path in (
            f"/v1.0/iot-03/devices/{device_id}/status",
            f"/v1.0/devices/{device_id}/status",
        ):
            result = await self._optional("GET", path, trace=probe.trace)
            _merge_status(probe.live_status, result)

        # IoT Core Things Model shadow can expose raw DP properties even when
        # classic status/specification APIs are empty.
        shadow = await self._optional(
            "GET",
            f"/v2.0/cloud/thing/{device_id}/shadow/properties",
            trace=probe.trace,
        )
        _merge_status(probe.live_status, shadow)

        # Things Data Model is an additional metadata source. Its exact shape
        # varies, so recursively collect objects that look like DP properties.
        model = await self._optional(
            "GET",
            f"/v2.0/cloud/thing/{device_id}/model",
            trace=probe.trace,
        )
        self._merge_tdm_model(function_map, status_schema_map, model)

        probe.functions = list(function_map.values())
        probe.status_schema = list(status_schema_map.values())
        return probe

    def _merge_tdm_model(
        self,
        function_map: dict[str, dict[str, Any]],
        status_schema_map: dict[str, dict[str, Any]],
        payload: Any,
    ) -> None:
        """Best-effort parser for Tuya Things Data Model metadata."""
        if isinstance(payload, list):
            for item in payload:
                self._merge_tdm_model(function_map, status_schema_map, item)
            return
        if not isinstance(payload, dict):
            return

        code = str(
            payload.get("code")
            or payload.get("identifier")
            or payload.get("dp_code")
            or ""
        ).strip()

        # TDM models can call a property readable/writable in several ways.
        access = str(
            payload.get("accessMode")
            or payload.get("access_mode")
            or payload.get("mode")
            or ""
        ).lower()
        writable = any(x in access for x in ("write", "rw", "readwrite"))
        readable = not access or "read" in access or "r" == access

        if code:
            row: dict[str, Any] = {"code": code}
            for source, dest in (
                ("type", "type"),
                ("dataType", "type"),
                ("values", "values"),
                ("specs", "values"),
                ("range", "values"),
            ):
                if payload.get(source) not in (None, "", [], {}):
                    row[dest] = payload[source]
            if writable:
                _merge_rows(function_map, [row])
            if readable:
                _merge_rows(status_schema_map, [row])

        for value in payload.values():
            if isinstance(value, (dict, list)):
                self._merge_tdm_model(
                    function_map,
                    status_schema_map,
                    value,
                )

    async def get_status(self, device_id: str) -> dict[str, Any]:
        """Return merged live state from classic status + shadow properties."""
        data: dict[str, Any] = {}

        # Device details may already contain raw status.
        try:
            device = await self.get_device(device_id)
        except TuyaApiError:
            device = {}
        _merge_status(data, device.get("status"))

        for path in (
            f"/v1.0/iot-03/devices/{device_id}/status",
            f"/v1.0/devices/{device_id}/status",
        ):
            result = await self._optional("GET", path)
            _merge_status(data, result)

        shadow = await self._optional(
            "GET",
            f"/v2.0/cloud/thing/{device_id}/shadow/properties",
        )
        _merge_status(data, shadow)
        return data

    async def send_commands(
        self,
        device_id: str,
        commands: list[dict[str, Any]],
    ) -> str:
        """Send commands with three control-path fallbacks.

        Returns a short route name used by diagnostics.
        """
        last_error: Exception | None = None

        # 1) IoT-03 command endpoint honors the project's selected control mode.
        for path, route in (
            (f"/v1.0/iot-03/devices/{device_id}/commands", "iot03"),
            (f"/v1.0/devices/{device_id}/commands", "smart_home"),
        ):
            try:
                await self._request(
                    "POST",
                    path,
                    json_body={"commands": commands},
                )
                return route
            except TuyaAuthError:
                raise
            except TuyaApiError as err:
                last_error = err

        # 3) IoT Core shadow property issue is a separate current control surface.
        properties = {
            str(command["code"]): command.get("value")
            for command in commands
            if command.get("code")
        }
        try:
            await self._request(
                "POST",
                f"/v2.0/cloud/thing/{device_id}/shadow/properties/issue",
                json_body={
                    "properties": json.dumps(
                        properties,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    )
                },
            )
            return "shadow"
        except TuyaAuthError:
            raise
        except TuyaApiError as err:
            last_error = err

        if last_error is not None:
            raise last_error
        raise TuyaDeviceError("No supported Tuya command route was available")

    async def send_command(self, device_id: str, code: str, value: Any) -> str:
        return await self.send_commands(
            device_id,
            [{"code": code, "value": value}],
        )

    async def list_devices(self, limit: int = 100) -> list[dict[str, Any]]:
        """Merge device lists from all available project/app-account APIs."""
        merged: dict[str, dict[str, Any]] = {}

        def add(rows: list[dict[str, Any]]) -> None:
            for row in rows:
                device_id = str(
                    row.get("id")
                    or row.get("device_id")
                    or ""
                ).strip()
                if not device_id:
                    continue
                old = merged.get(device_id, {})
                old.update({k: v for k, v in row.items() if v not in (None, "")})
                old["id"] = device_id
                merged[device_id] = old

        # Associated Tuya/Smart Life account devices.
        try:
            add(await self._list_associated_devices(limit))
        except TuyaAuthError:
            raise
        except TuyaApiError:
            pass

        for path in ("/v1.0/devices", "/v2.0/devices"):
            result = await self._optional(
                "GET",
                path,
                query={"page_size": min(limit, 100)},
            )
            if isinstance(result, list):
                add([x for x in result if isinstance(x, dict)])
            elif isinstance(result, dict):
                add(_rows(result, "list", "devices"))

        return list(merged.values())[:limit]

    async def _list_associated_devices(self, limit: int) -> list[dict[str, Any]]:
        devices: list[dict[str, Any]] = []
        last_row_key: str | None = None

        while len(devices) < limit:
            query: dict[str, Any] = {
                "size": min(100, limit - len(devices))
            }
            if last_row_key:
                query["last_row_key"] = last_row_key

            result = await self._request(
                "GET",
                "/v1.0/iot-01/associated-users/devices",
                query=query,
            )
            if not isinstance(result, dict):
                break
            rows = result.get("devices")
            if not isinstance(rows, list):
                break
            devices.extend(
                x for x in rows if isinstance(x, dict)
            )
            if not result.get("has_more"):
                break
            last_row_key = result.get("last_row_key")
            if not last_row_key:
                break

        return devices[:limit]
