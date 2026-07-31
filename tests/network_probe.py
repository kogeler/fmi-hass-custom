"""Deliberately failing probe used by `make test-network-block`."""

import socket


def test_unexpected_network_call_fails() -> None:
    """Demonstrate the failure raised for unexpected network access."""
    socket.socket(socket.AF_INET, socket.SOCK_STREAM)
