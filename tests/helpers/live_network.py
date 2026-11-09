# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Network enablement and bounded retries shared by marker-isolated live FMI tests."""

from __future__ import annotations

import asyncio
import os
import socket
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

import pytest
import pytest_socket
from fmi_weather_client.errors import ClientError, ServerError
from requests.exceptions import RequestException

from tests.helpers.live_budget import LiveRequestBudget

_REAL_GETADDRINFO = socket.getaddrinfo
_REAL_GETHOSTBYNAME = socket.gethostbyname
_REAL_GETHOSTBYNAME_EX = socket.gethostbyname_ex
_REAL_SOCKET_CONNECT = socket.socket.connect


def _set_socket_connect(connect: Any) -> None:
    """Set the connect implementation on pytest-socket's mutable socket class."""
    socket_class = cast(Any, socket.socket)
    socket_class.connect = connect


@contextmanager
def live_network() -> Iterator[None]:
    """Undo the HA test plugin's per-test network guard only inside one live test."""
    guarded_getaddrinfo = socket.getaddrinfo
    guarded_gethostbyname = socket.gethostbyname
    guarded_gethostbyname_ex = socket.gethostbyname_ex
    guarded_connect = socket.socket.connect
    pytest_socket.enable_socket()
    _set_socket_connect(_REAL_SOCKET_CONNECT)
    socket.getaddrinfo = _REAL_GETADDRINFO
    socket.gethostbyname = _REAL_GETHOSTBYNAME
    socket.gethostbyname_ex = _REAL_GETHOSTBYNAME_EX
    try:
        yield
    finally:
        socket.getaddrinfo = guarded_getaddrinfo
        socket.gethostbyname = guarded_gethostbyname
        socket.gethostbyname_ex = guarded_gethostbyname_ex
        _set_socket_connect(guarded_connect)
        pytest_socket.disable_socket(allow_unix_socket=True)


async def live_call[T](label: str, operation: Callable[[], Awaitable[T]]) -> T:
    """Retry one bounded transport/service failure and classify final output."""
    for attempt in range(2):
        try:
            budget = LiveRequestBudget(
                Path(os.environ.get("FMI_LIVE_BUDGET_DIR", "/tmp/fmi-live-budget"))
            )
            async with budget.request(), asyncio.timeout(15):
                return await operation()
        except ClientError as error:
            pytest.fail(
                f"FMI request/contract failure for {label}: "
                f"HTTP {getattr(error, 'status_code', 'unknown')} "
                f"{getattr(error, 'message', '')}",
                pytrace=False,
            )
        except (TimeoutError, OSError, RequestException, ServerError) as error:
            if attempt == 0:
                await asyncio.sleep(1)
                continue
            pytest.fail(
                f"FMI transport/service failure for {label} after 2 attempts: "
                f"{type(error).__name__}: {error}",
                pytrace=False,
            )
        except (
            AttributeError,
            KeyError,
            SyntaxError,
            TypeError,
            ValueError,
        ) as error:
            pytest.fail(
                f"FMI parsing/contract failure for {label}: {type(error).__name__}: {error}",
                pytrace=False,
            )
    raise AssertionError("unreachable live retry state")
