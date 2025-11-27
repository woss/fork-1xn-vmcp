"""Linux network bridge setup for sandbox networking."""

import asyncio
import secrets
import subprocess
from pathlib import Path
from tempfile import gettempdir

from sandbox_runtime.utils.debug import log_for_debugging


class LinuxNetworkBridgeContext:
    """Context for Linux network bridge processes."""

    def __init__(
        self,
        http_socket_path: str,
        socks_socket_path: str,
        http_bridge_process: subprocess.Popen,
        socks_bridge_process: subprocess.Popen,
        http_proxy_port: int,
        socks_proxy_port: int,
    ):
        """Initialize the bridge context."""
        self.http_socket_path = http_socket_path
        self.socks_socket_path = socks_socket_path
        self.http_bridge_process = http_bridge_process
        self.socks_bridge_process = socks_bridge_process
        self.http_proxy_port = http_proxy_port
        self.socks_proxy_port = socks_proxy_port


async def initialize_linux_network_bridge(
    http_proxy_port: int,
    socks_proxy_port: int,
) -> LinuxNetworkBridgeContext:
    """Initialize the Linux network bridge for sandbox networking.

    ARCHITECTURE NOTE:
    Linux network sandboxing uses bwrap --unshare-net which creates a completely isolated
    network namespace with NO network access. To enable network access, we:

    1. Host side: Run socat bridges that listen on Unix sockets and forward to host proxy servers
       - HTTP bridge: Unix socket -> host HTTP proxy (for HTTP/HTTPS traffic)
       - SOCKS bridge: Unix socket -> host SOCKS5 proxy (for SSH/git traffic)

    2. Sandbox side: Bind the Unix sockets into the isolated namespace and run socat listeners
       - HTTP listener on port 3128 -> HTTP Unix socket -> host HTTP proxy
       - SOCKS listener on port 1080 -> SOCKS Unix socket -> host SOCKS5 proxy

    3. Configure environment:
       - HTTP_PROXY=http://localhost:3128 for HTTP/HTTPS tools
       - GIT_SSH_COMMAND with socat for SSH through SOCKS5

    LIMITATION: Unlike macOS sandbox which can enforce domain-based allowlists at the kernel level,
    Linux's --unshare-net provides only all-or-nothing network isolation. Domain filtering happens
    at the host proxy level, not the sandbox boundary. This means network restrictions on Linux
    depend on the proxy's filtering capabilities.

    DEPENDENCIES: Requires bwrap (bubblewrap) and socat

    Args:
        http_proxy_port: Port of the HTTP proxy server on the host
        socks_proxy_port: Port of the SOCKS5 proxy server on the host

    Returns:
        LinuxNetworkBridgeContext with bridge process information
    """
    socket_id = secrets.token_hex(8)
    http_socket_path = str(Path(gettempdir()) / f"claude-http-{socket_id}.sock")
    socks_socket_path = str(Path(gettempdir()) / f"claude-socks-{socket_id}.sock")

    # Start HTTP bridge
    http_socat_args = [
        f"UNIX-LISTEN:{http_socket_path},fork,reuseaddr",
        f"TCP:localhost:{http_proxy_port},keepalive,keepidle=10,keepintvl=5,keepcnt=3",
    ]

    log_for_debugging(f"Starting HTTP bridge: socat {' '.join(http_socat_args)}")

    http_bridge_process = subprocess.Popen(
        ["socat"] + http_socat_args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if http_bridge_process.pid is None:
        raise RuntimeError("Failed to start HTTP bridge process")

    # Start SOCKS bridge
    socks_socat_args = [
        f"UNIX-LISTEN:{socks_socket_path},fork,reuseaddr",
        f"TCP:localhost:{socks_proxy_port},keepalive,keepidle=10,keepintvl=5,keepcnt=3",
    ]

    log_for_debugging(f"Starting SOCKS bridge: socat {' '.join(socks_socat_args)}")

    socks_bridge_process = subprocess.Popen(
        ["socat"] + socks_socat_args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if socks_bridge_process.pid is None:
        # Clean up HTTP bridge
        if http_bridge_process.pid:
            try:
                http_bridge_process.terminate()
            except Exception:
                pass
        raise RuntimeError("Failed to start SOCKS bridge process")

    # Wait for both sockets to be ready
    max_attempts = 5
    for i in range(max_attempts):
        if (
            http_bridge_process.poll() is not None
            or socks_bridge_process.poll() is not None
        ):
            # Clean up both processes
            if http_bridge_process.pid:
                try:
                    http_bridge_process.terminate()
                except Exception:
                    pass
            if socks_bridge_process.pid:
                try:
                    socks_bridge_process.terminate()
                except Exception:
                    pass
            raise RuntimeError("Linux bridge process died unexpectedly")

        try:
            if Path(http_socket_path).exists() and Path(socks_socket_path).exists():
                log_for_debugging(f"Linux bridges ready after {i + 1} attempts")
                break
        except Exception as err:
            log_for_debugging(
                f"Error checking sockets (attempt {i + 1}): {err}",
                {"level": "error"},
            )

        if i == max_attempts - 1:
            # Clean up both processes
            if http_bridge_process.pid:
                try:
                    http_bridge_process.terminate()
                except Exception:
                    pass
            if socks_bridge_process.pid:
                try:
                    socks_bridge_process.terminate()
                except Exception:
                    pass
            raise RuntimeError(
                f"Failed to create bridge sockets after {max_attempts} attempts"
            )

        await asyncio.sleep(i * 0.1)

    return LinuxNetworkBridgeContext(
        http_socket_path=http_socket_path,
        socks_socket_path=socks_socket_path,
        http_bridge_process=http_bridge_process,
        socks_bridge_process=socks_bridge_process,
        http_proxy_port=http_proxy_port,
        socks_proxy_port=socks_proxy_port,
    )

