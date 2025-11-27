"""Integration tests for configurable proxy ports feature."""

import pytest
from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig


@pytest.mark.asyncio
class TestConfigurableProxyPorts:
    """Tests for configurable proxy ports."""

    async def test_external_http_proxy_local_socks(self):
        """Test that external HTTP proxy is used when httpProxyPort is provided."""
        config = SandboxRuntimeConfig.from_json({
            "network": {
                "allowedDomains": ["example.com"],
                "deniedDomains": [],
                "httpProxyPort": 8888,  # External HTTP proxy
                # socksProxyPort not specified - should start locally
            },
            "filesystem": {
                "denyRead": [],
                "allowWrite": [],
                "denyWrite": [],
            },
        })

        await SandboxManager.initialize(config)

        # Verify HTTP proxy port matches what was configured
        http_proxy_port = SandboxManager.get_proxy_port()
        assert http_proxy_port == 8888

        # SOCKS proxy should have been started locally with dynamic port
        socks_proxy_port = SandboxManager.get_socks_proxy_port()
        assert socks_proxy_port is not None
        assert socks_proxy_port != 8888
        assert socks_proxy_port > 0

        await SandboxManager.reset()

    async def test_external_socks_proxy_local_http(self):
        """Test that external SOCKS proxy is used when socksProxyPort is provided."""
        config = SandboxRuntimeConfig.from_json({
            "network": {
                "allowedDomains": ["example.com"],
                "deniedDomains": [],
                # httpProxyPort not specified - should start locally
                "socksProxyPort": 1080,  # External SOCKS proxy
            },
            "filesystem": {
                "denyRead": [],
                "allowWrite": [],
                "denyWrite": [],
            },
        })

        await SandboxManager.initialize(config)

        # Verify SOCKS proxy port matches what was configured
        socks_proxy_port = SandboxManager.get_socks_proxy_port()
        assert socks_proxy_port == 1080

        # HTTP proxy should have been started locally with dynamic port
        http_proxy_port = SandboxManager.get_proxy_port()
        assert http_proxy_port is not None
        assert http_proxy_port != 1080
        assert http_proxy_port > 0

        await SandboxManager.reset()

    async def test_both_external_proxies(self):
        """Test that both external proxies are used when both ports are provided."""
        config = SandboxRuntimeConfig.from_json({
            "network": {
                "allowedDomains": ["example.com"],
                "deniedDomains": [],
                "httpProxyPort": 9090,  # External HTTP proxy
                "socksProxyPort": 9091,  # External SOCKS proxy
            },
            "filesystem": {
                "denyRead": [],
                "allowWrite": [],
                "denyWrite": [],
            },
        })

        await SandboxManager.initialize(config)

        # Verify both proxy ports match what was configured
        http_proxy_port = SandboxManager.get_proxy_port()
        assert http_proxy_port == 9090

        socks_proxy_port = SandboxManager.get_socks_proxy_port()
        assert socks_proxy_port == 9091

        await SandboxManager.reset()

    async def test_both_local_proxies(self):
        """Test that both proxies are started locally when no ports are configured."""
        config = SandboxRuntimeConfig.from_json({
            "network": {
                "allowedDomains": ["example.com"],
                "deniedDomains": [],
                # No httpProxyPort or socksProxyPort - both should start locally
            },
            "filesystem": {
                "denyRead": [],
                "allowWrite": [],
                "denyWrite": [],
            },
        })

        await SandboxManager.initialize(config)

        # Both proxies should have been started locally with dynamic ports
        http_proxy_port = SandboxManager.get_proxy_port()
        assert http_proxy_port is not None
        assert http_proxy_port > 0
        assert http_proxy_port < 65536

        socks_proxy_port = SandboxManager.get_socks_proxy_port()
        assert socks_proxy_port is not None
        assert socks_proxy_port > 0
        assert socks_proxy_port < 65536

        # Should be different ports
        assert http_proxy_port != socks_proxy_port

        await SandboxManager.reset()

    async def test_multiple_initialize_reset_cycles(self):
        """Test that multiple initialize and reset cycles work with different configs."""
        # First: both local
        config1 = SandboxRuntimeConfig.from_json({
            "network": {
                "allowedDomains": ["example.com"],
                "deniedDomains": [],
            },
            "filesystem": {
                "denyRead": [],
                "allowWrite": [],
                "denyWrite": [],
            },
        })

        await SandboxManager.initialize(config1)
        http_port1 = SandboxManager.get_proxy_port()
        socks_port1 = SandboxManager.get_socks_proxy_port()
        assert http_port1 is not None
        assert socks_port1 is not None
        await SandboxManager.reset()

        # Second: both external
        config2 = SandboxRuntimeConfig.from_json({
            "network": {
                "allowedDomains": ["example.com"],
                "deniedDomains": [],
                "httpProxyPort": 7777,
                "socksProxyPort": 7778,
            },
            "filesystem": {
                "denyRead": [],
                "allowWrite": [],
                "denyWrite": [],
            },
        })

        await SandboxManager.initialize(config2)
        assert SandboxManager.get_proxy_port() == 7777
        assert SandboxManager.get_socks_proxy_port() == 7778
        await SandboxManager.reset()

        # Third: mixed (external HTTP, local SOCKS)
        config3 = SandboxRuntimeConfig.from_json({
            "network": {
                "allowedDomains": ["example.com"],
                "deniedDomains": [],
                "httpProxyPort": 6666,
            },
            "filesystem": {
                "denyRead": [],
                "allowWrite": [],
                "denyWrite": [],
            },
        })

        await SandboxManager.initialize(config3)
        assert SandboxManager.get_proxy_port() == 6666
        socks_port3 = SandboxManager.get_socks_proxy_port()
        assert socks_port3 is not None
        assert socks_port3 != 6666
        await SandboxManager.reset()

    async def test_port_validation_valid_ports(self):
        """Test that valid port numbers (1-65535) are accepted."""
        config = SandboxRuntimeConfig.from_json({
            "network": {
                "allowedDomains": ["example.com"],
                "deniedDomains": [],
                "httpProxyPort": 1,
                "socksProxyPort": 65535,
            },
            "filesystem": {
                "denyRead": [],
                "allowWrite": [],
                "denyWrite": [],
            },
        })

        await SandboxManager.initialize(config)
        assert SandboxManager.get_proxy_port() == 1
        assert SandboxManager.get_socks_proxy_port() == 65535
        await SandboxManager.reset()

    async def test_port_validation_standard_ports(self):
        """Test that standard proxy ports are accepted."""
        config = SandboxRuntimeConfig.from_json({
            "network": {
                "allowedDomains": ["example.com"],
                "deniedDomains": [],
                "httpProxyPort": 3128,  # Standard HTTP proxy port
                "socksProxyPort": 1080,  # Standard SOCKS proxy port
            },
            "filesystem": {
                "denyRead": [],
                "allowWrite": [],
                "denyWrite": [],
            },
        })

        await SandboxManager.initialize(config)
        assert SandboxManager.get_proxy_port() == 3128
        assert SandboxManager.get_socks_proxy_port() == 1080
        await SandboxManager.reset()

    async def test_idempotent_initialization(self):
        """Test that calling initialize multiple times without reset is idempotent."""
        config = SandboxRuntimeConfig.from_json({
            "network": {
                "allowedDomains": ["example.com"],
                "deniedDomains": [],
                "httpProxyPort": 5555,
                "socksProxyPort": 5556,
            },
            "filesystem": {
                "denyRead": [],
                "allowWrite": [],
                "denyWrite": [],
            },
        })

        # Initialize once
        await SandboxManager.initialize(config)
        http_port1 = SandboxManager.get_proxy_port()
        socks_port1 = SandboxManager.get_socks_proxy_port()

        # Initialize again without reset (should be idempotent)
        await SandboxManager.initialize(config)
        http_port2 = SandboxManager.get_proxy_port()
        socks_port2 = SandboxManager.get_socks_proxy_port()

        # Should return the same ports
        assert http_port2 == http_port1
        assert socks_port2 == socks_port1
        assert http_port2 == 5555
        assert socks_port2 == 5556

        await SandboxManager.reset()

