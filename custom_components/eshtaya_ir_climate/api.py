"""Async Tuya OpenAPI client for Eshtaya IR Climate."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Iterable
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
        """Return True if token is safely valid."""
        return bool(self.access_token) and time.time() < self.expires_at - 60


class TuyaOpenApi:
    """Minimal Tuya Cloud OpenAPI client with endpoint fallbacks."""

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
        sign_payload = (
            self._access_id
            + access_token
            + timestamp
            + nonce
            + string_to_sign
        )
        return hmac.new(
            self._access_secret.encode(),
            sign_payload.encode(),
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

        url = f"{self._endpoint}{path_with_query}"
        try:
            async with self._session.request(
                method,
                url,
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

    async def _request_first(
        self,
        candidates: Iterable[tuple[str, str, dict[str, Any] | None]],
        *,
        json_body: Any | None = None,
    ) -> Any:
        last_error: Exception | None = None
        for method, path, query in candidates:
            try:
                return await self._request(
                    method,
                    path,
                    query=query,
                    json_body=json_body,
                )
            except TuyaAuthError:
                raise
            except TuyaDeviceError as err:
                last_error = err
                continue
        if last_error is not None:
            raise last_error
        raise TuyaApiError("No Tuya API endpoint candidates were provided")

    async def ensure_token(self) -> None:
        """Ensure a valid simple-mode project token."""
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
        """Get device details using current then legacy endpoints."""
        result = await self._request_first(
            (
                ("GET", f"/v1.1/iot-03/devices/{device_id}", None),
                ("GET", f"/v1.0/devices/{device_id}", None),
            )
        )
        if not isinstance(result, dict):
            raise TuyaDeviceError("Invalid device details response")
        return result

    async def get_specification(self, device_id: str) -> dict[str, Any]:
        """Get instruction/status specification with documented fallbacks."""
        result = await self._request_first(
            (
                ("GET", f"/v1.2/iot-03/devices/{device_id}/specification", None),
                ("GET", f"/v1.0/iot-03/devices/{device_id}/specification", None),
                ("GET", f"/v1.0/devices/{device_id}/specifications", None),
            )
        )
        if not isinstance(result, dict):
            raise TuyaDeviceError("Invalid device specification response")
        return result

    async def get_status(self, device_id: str) -> dict[str, Any]:
        """Get latest device status."""
        result = await self._request_first(
            (
                ("GET", f"/v1.0/iot-03/devices/{device_id}/status", None),
                ("GET", f"/v1.0/devices/{device_id}/status", None),
            )
        )
        if isinstance(result, dict):
            # Some newer APIs can return code/value pairs under a nested key.
            for key in ("status", "properties", "list"):
                if isinstance(result.get(key), list):
                    result = result[key]
                    break
        if not isinstance(result, list):
            raise TuyaDeviceError("Invalid device status response")
        return {
            str(item["code"]): item.get("value")
            for item in result
            if isinstance(item, dict) and item.get("code")
        }

    async def send_commands(
        self,
        device_id: str,
        commands: list[dict[str, Any]],
    ) -> None:
        """Send one or more standard/DP commands."""
        await self._request_first(
            (
                ("POST", f"/v1.0/iot-03/devices/{device_id}/commands", None),
                ("POST", f"/v1.0/devices/{device_id}/commands", None),
            ),
            json_body={"commands": commands},
        )

    async def send_command(self, device_id: str, code: str, value: Any) -> None:
        """Send one command."""
        await self.send_commands(
            device_id,
            [{"code": code, "value": value}],
        )

    async def list_devices(self, limit: int = 100) -> list[dict[str, Any]]:
        """List devices linked to the cloud project/app account.

        Smart Home projects commonly expose linked Tuya app-account devices
        through the associated-users endpoint. A legacy project device-list
        fallback is kept for broader compatibility.
        """
        try:
            devices = await self._list_associated_devices(limit)
            if devices:
                return devices
        except TuyaAuthError:
            raise
        except TuyaApiError:
            pass

        result = await self._request_first(
            (
                ("GET", "/v1.0/devices", {"page_size": min(limit, 100)}),
                ("GET", "/v2.0/devices", {"page_size": min(limit, 100)}),
            )
        )
        if isinstance(result, list):
            return [d for d in result if isinstance(d, dict)][:limit]
        if isinstance(result, dict):
            for key in ("list", "devices"):
                rows = result.get(key)
                if isinstance(rows, list):
                    return [d for d in rows if isinstance(d, dict)][:limit]
        return []

    async def _list_associated_devices(self, limit: int) -> list[dict[str, Any]]:
        devices: list[dict[str, Any]] = []
        last_row_key: str | None = None

        while len(devices) < limit:
            query: dict[str, Any] = {"size": min(100, limit - len(devices))}
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
            devices.extend(d for d in rows if isinstance(d, dict))

            if not result.get("has_more"):
                break
            last_row_key = result.get("last_row_key")
            if not last_row_key:
                break

        return devices[:limit]
