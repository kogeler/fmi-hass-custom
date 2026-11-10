# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT
# Contracts: docs/contracts/OPTIONAL_SOURCES.md, docs/contracts/COMPATIBILITY_SECURITY.md

"""Shared bounded HTTP transport for integration-owned optional FMI sources."""

from aiohttp import (
    ClientError,
    ClientSession,
    ClientTimeout,
    ConnectionTimeoutError,
    SocketTimeoutError,
)

from . import const


class OptionalSourceError(RuntimeError):
    """Report a classified optional-source transport or payload failure."""

    def __init__(self, message: str, *, reason: str = "transport", detail: str = "") -> None:
        super().__init__(message)
        self.reason = reason
        self.detail = detail


def _timeout_error(source: str, error: TimeoutError, limits: ClientTimeout) -> OptionalSourceError:
    """Name the expired limit and its value, never the external exception text."""
    if isinstance(error, ConnectionTimeoutError):
        limit = f"connect timeout of {limits.connect} s"
    elif isinstance(error, SocketTimeoutError):
        limit = f"read timeout of {limits.sock_read} s"
    else:
        limit = f"total timeout of {limits.total} s"
    detail = f"exceeded the {limit}"
    return OptionalSourceError(f"{source} request {detail}", reason="timeout", detail=detail)


async def async_optional_payload(
    session: ClientSession,
    source: str,
    url: str,
    maximum: int,
    *,
    allow_redirects: bool = True,
    expected_status: int | None = None,
    client_timeout: ClientTimeout | None = None,
) -> bytes:
    """Read decoded bytes without retrying or retaining arbitrary transport details."""
    if client_timeout is None:
        client_timeout = ClientTimeout(
            total=const.AUX_HTTP_TOTAL_TIMEOUT_SECONDS,
            connect=const.AUX_HTTP_CONNECT_TIMEOUT_SECONDS,
            sock_connect=const.AUX_HTTP_CONNECT_TIMEOUT_SECONDS,
            sock_read=const.AUX_HTTP_READ_TIMEOUT_SECONDS,
        )
    try:
        async with session.get(
            url,
            timeout=client_timeout,
            allow_redirects=allow_redirects,
        ) as response:
            successful = (
                response.status == expected_status
                if expected_status is not None
                else 200 <= response.status < 300
            )
            if not successful:
                category = "server" if response.status >= 500 else "client"
                raise OptionalSourceError(
                    f"{source} {category} error HTTP {response.status}",
                    reason="redirect" if 300 <= response.status < 400 else f"http_{category}",
                )
            if response.content_length is not None and response.content_length > maximum:
                raise OptionalSourceError(
                    f"{source} response exceeds size limit", reason="response_too_large"
                )
            chunks: list[bytes] = []
            remaining = maximum + 1
            while remaining:
                chunk = await response.content.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            payload = b"".join(chunks)
    except TimeoutError as error:
        raise _timeout_error(source, error, client_timeout) from None
    except ClientError as error:
        raise OptionalSourceError(f"{source} transport error: {type(error).__name__}") from None
    if len(payload) > maximum:
        raise OptionalSourceError(
            f"{source} response exceeds size limit", reason="response_too_large"
        )
    if not payload.strip():
        raise OptionalSourceError(f"{source} empty response", reason="empty_response")
    return payload
