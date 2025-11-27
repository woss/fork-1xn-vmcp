"""SOCKS5 proxy server for network filtering."""

import asyncio
import struct
from collections.abc import Coroutine
from typing import Any, Callable, Optional, Union

from sandbox_runtime.utils.debug import log_for_debugging


class SocksProxyWrapper:
    """Wrapper for SOCKS5 proxy server with domain filtering."""

    def __init__(
        self,
        filter_func: Callable[[int, str], Union[bool, asyncio.Future[bool], Coroutine[Any, Any, bool]]],
    ):
        """Initialize the SOCKS5 proxy wrapper.

        Args:
            filter_func: Function that takes (port, hostname) and returns True if allowed
        """
        self._filter_func = filter_func
        self._server: Optional[asyncio.Server] = None
        self._port: Optional[int] = None

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Handle a SOCKS5 client connection."""
        try:
            # Read SOCKS5 greeting
            greeting = await reader.read(2)
            if len(greeting) < 2 or greeting[0] != 0x05:
                writer.close()
                return

            # Send method selection (no authentication)
            writer.write(b"\x05\x00")
            await writer.drain()

            # Read connection request
            request = await reader.read(4)
            if len(request) < 4:
                writer.close()
                return

            cmd = request[1]
            if cmd != 0x01:  # CONNECT only
                writer.write(b"\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00")
                await writer.drain()
                writer.close()
                return

            # Read address
            addr_type = request[3]
            hostname_bytes = ""
            port = 0

            if addr_type == 0x01:  # IPv4
                addr_data = await reader.read(4)
                hostname_bytes = ".".join(str(b) for b in addr_data)
                port_data = await reader.read(2)
                port = struct.unpack("!H", port_data)[0]
            elif addr_type == 0x03:  # Domain name
                length_data = await reader.read(1)
                length = length_data[0]
                hostname_bytes = (await reader.read(length)).decode("utf-8")
                port_data = await reader.read(2)
                port = struct.unpack("!H", port_data)[0]
            elif addr_type == 0x04:  # IPv6
                addr_data = await reader.read(16)
                hostname_bytes = ":".join(
                    f"{int.from_bytes(addr_data[i:i+2], 'big'):04x}"
                    for i in range(0, 16, 2)
                )
                port_data = await reader.read(2)
                port = struct.unpack("!H", port_data)[0]
            else:
                writer.write(b"\x05\x08\x00\x01\x00\x00\x00\x00\x00\x00")
                await writer.drain()
                writer.close()
                return

            # Validate connection
            if asyncio.iscoroutinefunction(self._filter_func):
                allowed = await self._filter_func(port, hostname_bytes)
            else:
                result = self._filter_func(port, hostname_bytes)
                if isinstance(result, asyncio.Future):
                    allowed = await result
                else:
                    allowed = result

            if not allowed:
                log_for_debugging(
                    f"Connection blocked to {hostname_bytes}:{port}",
                    {"level": "error"},
                )
                writer.write(b"\x05\x02\x00\x01\x00\x00\x00\x00\x00\x00")
                await writer.drain()
                writer.close()
                return

            # Connect to target
            try:
                target_reader, target_writer = await asyncio.open_connection(
                    hostname_bytes, port
                )
            except Exception as err:
                log_for_debugging(
                    f"Failed to connect to {hostname_bytes}:{port}: {err}",
                    {"level": "error"},
                )
                writer.write(b"\x05\x04\x00\x01\x00\x00\x00\x00\x00\x00")
                await writer.drain()
                writer.close()
                return

            # Send success response
            writer.write(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
            await writer.drain()

            # Tunnel data
            async def forward_to_target():
                try:
                    while True:
                        data = await reader.read(8192)
                        if not data:
                            break
                        target_writer.write(data)
                        await target_writer.drain()
                except Exception:
                    pass
                finally:
                    target_writer.close()

            async def forward_to_client():
                try:
                    while True:
                        data = await target_reader.read(8192)
                        if not data:
                            break
                        writer.write(data)
                        await writer.drain()
                except Exception:
                    pass
                finally:
                    writer.close()

            await asyncio.gather(
                forward_to_target(),
                forward_to_client(),
                return_exceptions=True,
            )

        except Exception as err:
            log_for_debugging(
                f"Error handling SOCKS5 connection: {err}",
                {"level": "error"},
            )
            try:
                writer.close()
            except Exception:
                pass

    async def listen(self, port: int, hostname: str) -> int:
        """Start the SOCKS5 proxy server.

        Args:
            port: Port to bind to (0 for random port)
            hostname: Hostname to bind to

        Returns:
            The actual port the server is listening on
        """
        # Start server
        self._server = await asyncio.start_server(
            self._handle_client, hostname, port
        )

        # Get the actual port
        sockets = list(self._server.sockets)
        if sockets:
            port = sockets[0].getsockname()[1]
            self._port = port
            log_for_debugging(
                f"SOCKS proxy listening on {hostname}:{port}",
            )
            return port
        else:
            raise RuntimeError("Failed to start SOCKS proxy server")

    def get_port(self) -> Optional[int]:
        """Get the port the server is listening on."""
        return self._port

    async def close(self) -> None:
        """Close the SOCKS5 proxy server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    def unref(self) -> None:
        """Unreference the server (allows process to exit even if server is running)."""
        # In Python, we don't need to explicitly unref - the event loop handles this
        pass


def create_socks_proxy_server(
    filter_func: Callable[[int, str], Union[bool, asyncio.Future[bool], Coroutine[Any, Any, bool]]],
) -> SocksProxyWrapper:
    """Create a SOCKS5 proxy server with domain filtering.

    Args:
        filter_func: Function that takes (port, hostname) and returns True if allowed

    Returns:
        SocksProxyWrapper instance
    """
    return SocksProxyWrapper(filter_func)

