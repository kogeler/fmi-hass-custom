# Copyright (c) 2026 kogeler
# SPDX-License-Identifier: MIT

"""Passing proof that ordinary pytest cannot open an Internet socket."""

import subprocess
import sys


def test_unexpected_network_call_is_blocked_in_isolated_process() -> None:
    """Prove pytest-socket denial without tripping HA's parent-process sentinel."""
    probe = """
import socket
import pytest_socket

pytest_socket.disable_socket()
try:
    socket.socket(socket.AF_INET, socket.SOCK_STREAM)
except pytest_socket.SocketBlockedError:
    raise SystemExit(0)
raise SystemExit(1)
"""
    result = subprocess.run(
        [sys.executable, "-c", probe],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
