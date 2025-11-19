"""Tests for wrapWithSandbox with custom config."""

import pytest
from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig
from sandbox_runtime.utils.platform import get_platform
from sandbox_runtime.sandbox.linux_utils import wrap_command_with_sandbox_linux
from sandbox_runtime.sandbox.macos_utils import wrap_command_with_sandbox_macos


def create_test_config() -> SandboxRuntimeConfig:
    """Create a test configuration with network access."""
    return SandboxRuntimeConfig.from_json({
        "network": {
            "allowedDomains": ["example.com", "api.github.com"],
            "deniedDomains": [],
        },
        "filesystem": {
            "denyRead": ["~/.ssh"],
            "allowWrite": [".", "/tmp"],
            "denyWrite": [".env"],
        },
    })


def skip_if_unsupported_platform() -> bool:
    """Check if platform is unsupported."""
    platform = get_platform()
    return platform not in ("linux", "macos")


@pytest.mark.asyncio
class TestWrapWithSandboxCustomConfig:
    """Tests for wrapWithSandbox with customConfig."""

    @pytest.fixture(autouse=True)
    async def setup_and_teardown(self):
        """Setup and teardown for each test."""
        if skip_if_unsupported_platform():
            pytest.skip("Platform not supported")
        
        await SandboxManager.initialize(create_test_config())
        yield
        await SandboxManager.reset()

    async def test_uses_main_config_values(self):
        """Test that without customConfig, main config values are used."""
        command = "echo hello"
        wrapped = await SandboxManager.wrap_with_sandbox(command)

        # Should wrap the command (not return it as-is)
        assert wrapped != command
        assert len(wrapped) > len(command)

    async def test_uses_custom_allow_write(self):
        """Test that custom allowWrite is used when provided."""
        command = "echo hello"
        wrapped = await SandboxManager.wrap_with_sandbox(
            command,
            None,
            {
                "filesystem": {
                    "denyRead": [],
                    "allowWrite": [],  # Override to block all writes
                    "denyWrite": [],
                },
            },
        )

        # Should still wrap the command
        assert wrapped != command
        assert len(wrapped) > len(command)

    async def test_uses_custom_deny_read(self):
        """Test that custom denyRead is used when provided."""
        command = "cat /etc/passwd"
        wrapped = await SandboxManager.wrap_with_sandbox(
            command,
            None,
            {
                "filesystem": {
                    "denyRead": ["/etc/passwd"],  # Block this specific file
                    "allowWrite": [],
                    "denyWrite": [],
                },
            },
        )

        assert wrapped != command

    async def test_blocks_network_when_allowed_domains_empty(self):
        """Test that network is blocked when allowedDomains is empty."""
        command = "curl https://example.com"
        wrapped = await SandboxManager.wrap_with_sandbox(
            command,
            None,
            {
                "network": {
                    "allowedDomains": [],  # Block all network
                    "deniedDomains": [],
                },
            },
        )

        # Should wrap but without proxy env vars when allowedDomains is empty
        assert wrapped != command

    async def test_uses_main_config_network_when_custom_network_undefined(self):
        """Test that main config network is used when customConfig.network is undefined."""
        command = "echo hello"
        wrapped = await SandboxManager.wrap_with_sandbox(
            command,
            None,
            {
                "filesystem": {
                    "denyRead": [],
                    "allowWrite": [],
                    "denyWrite": [],
                },
                # network is not provided, should use main config
            },
        )

        assert wrapped != command

    async def test_readonly_mode_simulation(self):
        """Test that a fully restricted sandbox config can be created."""
        command = "ls -la"

        # This is what BashTool passes for readonly commands
        readonly_config = {
            "network": {
                "allowedDomains": [],  # Block all network
                "deniedDomains": [],
            },
            "filesystem": {
                "denyRead": [],
                "allowWrite": [],  # Block all writes
                "denyWrite": [],
            },
        }

        wrapped = await SandboxManager.wrap_with_sandbox(
            command,
            None,
            readonly_config,
        )

        # Should wrap the command with restrictions
        assert wrapped != command
        assert len(wrapped) > len(command)

    async def test_only_overrides_specified_filesystem_fields(self):
        """Test that only specified filesystem fields are overridden."""
        command = "echo test"

        # Only override allowWrite, should use main config for denyRead/denyWrite
        wrapped = await SandboxManager.wrap_with_sandbox(
            command,
            None,
            {
                "filesystem": {
                    "denyRead": [],  # Override denyRead
                    "allowWrite": ["/custom/path"],  # Override allowWrite
                    "denyWrite": [],  # Override denyWrite
                },
            },
        )

        assert wrapped != command

    async def test_only_overrides_specified_network_fields(self):
        """Test that only specified network fields are overridden."""
        command = "echo test"

        # Only override allowedDomains
        wrapped = await SandboxManager.wrap_with_sandbox(
            command,
            None,
            {
                "network": {
                    "allowedDomains": ["custom.example.com"],
                    "deniedDomains": [],
                },
            },
        )

        assert wrapped != command


class TestRestrictionPatternSemantics:
    """Tests for restriction pattern semantics."""

    command = "echo hello"

    def test_returns_command_unchanged_when_no_restrictions_linux(self):
        """Test that command is returned unchanged when no restrictions on Linux."""
        if get_platform() != "linux":
            pytest.skip("Linux only test")

        # No network, empty read deny, no write config = no sandboxing
        result = wrap_command_with_sandbox_linux(
            self.command,
            needs_network_restriction=False,
            read_config={"denyOnly": []},
            write_config=None,
        )

        assert result == self.command

    async def test_returns_command_unchanged_when_no_restrictions_macos(self):
        """Test that command is returned unchanged when no restrictions on macOS."""
        if get_platform() != "macos":
            pytest.skip("macOS only test")

        # No network, empty read deny, no write config = no sandboxing
        result = await wrap_command_with_sandbox_macos(
            self.command,
            needs_network_restriction=False,
            read_config={"denyOnly": []},
            write_config=None,
        )

        assert result == self.command

    def test_returns_command_unchanged_with_undefined_read_config_linux(self):
        """Test that command is returned unchanged with undefined readConfig on Linux."""
        if get_platform() != "linux":
            pytest.skip("Linux only test")

        result = wrap_command_with_sandbox_linux(
            self.command,
            needs_network_restriction=False,
            read_config=None,
            write_config=None,
        )

        assert result == self.command

    async def test_returns_command_unchanged_with_undefined_read_config_macos(self):
        """Test that command is returned unchanged with undefined readConfig on macOS."""
        if get_platform() != "macos":
            pytest.skip("macOS only test")

        result = await wrap_command_with_sandbox_macos(
            self.command,
            needs_network_restriction=False,
            read_config=None,
            write_config=None,
        )

        assert result == self.command

    def test_empty_deny_only_means_no_read_restrictions_linux(self):
        """Test that empty denyOnly means no read restrictions on Linux."""
        if get_platform() != "linux":
            pytest.skip("Linux only test")

        # Only write restrictions, empty read = should sandbox but no read rules
        result = wrap_command_with_sandbox_linux(
            self.command,
            needs_network_restriction=False,
            read_config={"denyOnly": []},
            write_config={"allowOnly": ["/tmp"], "denyWithinAllow": []},
        )

        # Should wrap because of write restrictions
        assert result != self.command
        assert "bwrap" in result

    def test_non_empty_deny_only_means_has_read_restrictions_linux(self):
        """Test that non-empty denyOnly means has read restrictions on Linux."""
        if get_platform() != "linux":
            pytest.skip("Linux only test")

        result = wrap_command_with_sandbox_linux(
            self.command,
            needs_network_restriction=False,
            read_config={"denyOnly": ["/secret"]},
            write_config=None,
        )

        # Should wrap because of read restrictions
        assert result != self.command
        assert "bwrap" in result

    def test_undefined_write_config_means_no_write_restrictions_linux(self):
        """Test that undefined writeConfig means no write restrictions on Linux."""
        if get_platform() != "linux":
            pytest.skip("Linux only test")

        # Has read restrictions but no write = should sandbox
        result = wrap_command_with_sandbox_linux(
            self.command,
            needs_network_restriction=False,
            read_config={"denyOnly": ["/secret"]},
            write_config=None,
        )

        assert result != self.command

    def test_empty_allow_only_means_maximally_restrictive_linux(self):
        """Test that empty allowOnly means maximally restrictive on Linux."""
        if get_platform() != "linux":
            pytest.skip("Linux only test")

        # Empty allowOnly = no writes allowed = has restrictions
        result = wrap_command_with_sandbox_linux(
            self.command,
            needs_network_restriction=False,
            read_config={"denyOnly": []},
            write_config={"allowOnly": [], "denyWithinAllow": []},
        )

        # Should wrap because empty allowOnly is still a restriction
        assert result != self.command
        assert "bwrap" in result

    async def test_any_write_config_means_has_restrictions_macos(self):
        """Test that any writeConfig means has restrictions on macOS."""
        if get_platform() != "macos":
            pytest.skip("macOS only test")

        result = await wrap_command_with_sandbox_macos(
            self.command,
            needs_network_restriction=False,
            read_config={"denyOnly": []},
            write_config={"allowOnly": [], "denyWithinAllow": []},
        )

        # Should wrap because writeConfig is defined
        assert result != self.command
        assert "sandbox-exec" in result

    def test_needs_network_restriction_false_skips_network_sandbox_linux(self):
        """Test that needsNetworkRestriction false skips network sandbox on Linux."""
        if get_platform() != "linux":
            pytest.skip("Linux only test")

        result = wrap_command_with_sandbox_linux(
            self.command,
            needs_network_restriction=False,
            read_config={"denyOnly": ["/secret"]},
            write_config=None,
        )

        # Should wrap for filesystem but not include network args
        assert result != self.command
        assert "--unshare-net" not in result

    async def test_needs_network_restriction_false_skips_network_sandbox_macos(self):
        """Test that needsNetworkRestriction false skips network sandbox on macOS."""
        if get_platform() != "macos":
            pytest.skip("macOS only test")

        result = await wrap_command_with_sandbox_macos(
            self.command,
            needs_network_restriction=False,
            read_config={"denyOnly": ["/secret"]},
            write_config=None,
        )

        # Should wrap for filesystem
        assert result != self.command
        assert "sandbox-exec" in result

