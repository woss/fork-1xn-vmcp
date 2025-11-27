"""HTTP proxy server for network filtering."""

import asyncio
from collections.abc import Coroutine
from typing import Any, Callable, Optional, Union

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response, StreamResponse

from sandbox_runtime.utils.debug import log_for_debugging


class HttpProxyServer:
    """HTTP proxy server that filters connections based on domain allowlists."""

    def __init__(
        self,
        filter_func: Callable[[int, str], Union[bool, asyncio.Future[bool], Coroutine[Any, Any, bool]]],
    ):
        """Initialize the HTTP proxy server.

        Args:
            filter_func: Function that takes (port, hostname) and returns True if allowed
        """
        self._filter_func = filter_func
        self._app = web.Application()
        self._app.router.add_route("CONNECT", "/{path:.*}", self._handle_connect)
        self._app.router.add_route("*", "/{path:.*}", self._handle_request)
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None

    async def _handle_connect(self, request: Request) -> Response | StreamResponse:
        """Handle CONNECT requests for HTTPS tunneling."""
        try:
            # Parse the target from the request URL
            target = str(request.url.path)
            if target.startswith("/"):
                target = target[1:]

            if ":" in target:
                hostname, port_str = target.rsplit(":", 1)
                try:
                    port = int(port_str)
                except ValueError:
                    log_for_debugging(
                        f"Invalid CONNECT request: {request.url}",
                        {"level": "error"},
                    )
                    return web.Response(
                        status=400, text="Bad Request", reason="Bad Request"
                    )
            else:
                log_for_debugging(
                    f"Invalid CONNECT request: {request.url}",
                    {"level": "error"},
                )
                return web.Response(
                    status=400, text="Bad Request", reason="Bad Request"
                )

            # Check if connection is allowed
            if asyncio.iscoroutinefunction(self._filter_func):
                allowed = await self._filter_func(port, hostname)
            else:
                result = self._filter_func(port, hostname)
                if isinstance(result, asyncio.Future):
                    allowed = await result
                else:
                    allowed = result

            if not allowed:
                log_for_debugging(
                    f"Connection blocked to {hostname}:{port}",
                    {"level": "error"},
                )
                return web.Response(
                    status=403,
                    text="Connection blocked by network allowlist",
                    reason="Forbidden",
                    headers={"X-Proxy-Error": "blocked-by-allowlist"},
                )

            # Upgrade to raw socket for tunneling
            # Note: aiohttp doesn't support raw socket access easily,
            # so we'll use a StreamResponse and handle the tunnel manually
            response = web.StreamResponse(status=200, reason="Connection Established")
            await response.prepare(request)

            # Create tunnel using asyncio
            async def tunnel():
                try:
                    # Connect to target server
                    reader, writer = await asyncio.open_connection(hostname, port)

                    # Get the client's raw transport
                    client_transport = request.transport
                    if client_transport:
                        # Create bidirectional data forwarding
                        async def forward_to_server():
                            try:
                                while True:
                                    data = await request.content.read(8192)
                                    if not data:
                                        break
                                    writer.write(data)
                                    await writer.drain()
                            except Exception:
                                pass
                            finally:
                                writer.close()

                        async def forward_to_client():
                            try:
                                while True:
                                    data = await reader.read(8192)
                                    if not data:
                                        break
                                    await response.write(data)
                            except Exception:
                                pass
                            finally:
                                await response.write_eof()

                        await asyncio.gather(
                            forward_to_server(),
                            forward_to_client(),
                            return_exceptions=True,
                        )
                except Exception as err:
                    log_for_debugging(
                        f"CONNECT tunnel failed: {err}",
                        {"level": "error"},
                    )
                    try:
                        await response.write(
                            b"HTTP/1.1 502 Bad Gateway\r\n\r\n"
                        )
                    except Exception:
                        pass

            # Start tunneling
            asyncio.create_task(tunnel())

            return response

        except Exception as err:
            log_for_debugging(
                f"Error handling CONNECT: {err}",
                {"level": "error"},
            )
            return web.Response(
                status=500, text="Internal Server Error", reason="Internal Server Error"
            )

    async def _handle_request(self, request: Request) -> Response:
        """Handle regular HTTP requests."""
        try:
            # For regular HTTP requests, we need to parse the URL
            # This is a simplified version - full implementation would need
            # to handle various URL formats
            url_str = str(request.url)
            if not url_str.startswith("http"):
                url_str = f"http://{url_str}"

            from urllib.parse import urlparse

            parsed = urlparse(url_str)
            hostname = parsed.hostname or ""
            port = parsed.port or (443 if parsed.scheme == "https" else 80)

            # Check if connection is allowed
            if asyncio.iscoroutinefunction(self._filter_func):
                allowed = await self._filter_func(port, hostname)
            else:
                allowed = self._filter_func(port, hostname)

            if not allowed:
                log_for_debugging(
                    f"HTTP request blocked to {hostname}:{port}",
                    {"level": "error"},
                )
                return web.Response(
                    status=403,
                    text="Connection blocked by network allowlist",
                    reason="Forbidden",
                    headers={"X-Proxy-Error": "blocked-by-allowlist"},
                )

            # Forward the request using aiohttp client
            import aiohttp

            async with aiohttp.ClientSession() as session:
                headers = dict(request.headers)
                headers.pop("Host", None)
                if port not in (80, 443):
                    headers["Host"] = f"{hostname}:{port}"
                else:
                    headers["Host"] = hostname

                async with session.request(
                    method=request.method,
                    url=url_str,
                    headers=headers,
                    data=await request.read(),
                    allow_redirects=False,
                ) as resp:
                    response_headers = dict(resp.headers)
                    response_headers.pop("Content-Encoding", None)  # Remove encoding
                    body = await resp.read()
                    return web.Response(
                        status=resp.status,
                        headers=response_headers,
                        body=body,
                    )

        except Exception as err:
            log_for_debugging(
                f"Error handling HTTP request: {err}",
                {"level": "error"},
            )
            return web.Response(
                status=500, text="Internal Server Error", reason="Internal Server Error"
            )

    async def listen(self, host: str = "127.0.0.1", port: int = 0) -> int:
        """Start the proxy server and return the actual port.

        Args:
            host: Host to bind to
            port: Port to bind to (0 for random port)

        Returns:
            The actual port the server is listening on
        """
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host, port)
        await self._site.start()

        # Get the actual port
        if self._site and self._site._server:
            sockets = list(self._site._server.sockets) if hasattr(self._site._server, 'sockets') else []
            if sockets:
                actual_port = sockets[0].getsockname()[1]
                log_for_debugging(f"HTTP proxy listening on {host}:{actual_port}")
                return actual_port
        raise RuntimeError("Failed to start HTTP proxy server")

    async def close(self) -> None:
        """Close the proxy server."""
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()

    def unref(self) -> None:
        """Unreference the server (allows process to exit even if server is running)."""
        # In Python, we don't need to explicitly unref - the event loop handles this
        pass


def create_http_proxy_server(
    filter_func: Callable[[int, str], Union[bool, asyncio.Future[bool], Coroutine[Any, Any, bool]]],
) -> HttpProxyServer:
    """Create an HTTP proxy server with domain filtering.

    Args:
        filter_func: Function that takes (port, hostname) and returns True if allowed

    Returns:
        HttpProxyServer instance
    """
    return HttpProxyServer(filter_func)

