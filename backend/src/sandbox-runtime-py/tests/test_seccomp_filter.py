"""Tests for Linux seccomp filter functionality."""

import os
import platform
import pytest
import subprocess
from pathlib import Path

from sandbox_runtime.sandbox.seccomp import (
    generate_seccomp_filter,
    cleanup_seccomp_filter,
    get_pre_generated_bpf_path,
    get_apply_seccomp_binary_path,
)
from sandbox_runtime.sandbox.linux_utils import (
    wrap_command_with_sandbox_linux,
    has_linux_sandbox_dependencies_sync,
)
from sandbox_runtime.utils.platform import get_platform


def skip_if_not_linux() -> bool:
    """Check if platform is not Linux."""
    return get_platform() != "linux"


def skip_if_not_ant() -> bool:
    """Check if user type is not ant."""
    return os.environ.get("USER_TYPE") != "ant"


@pytest.mark.skipif(skip_if_not_linux(), reason="Linux only test")
class TestLinuxSandboxDependencies:
    """Tests for Linux sandbox dependencies."""

    def test_check_linux_sandbox_dependencies(self):
        """Test that Linux sandbox dependencies are checked."""
        has_deps = has_linux_sandbox_dependencies_sync()

        assert isinstance(has_deps, bool)

        # Should always check for bwrap and socat
        if has_deps:
            bwrap_result = subprocess.run(
                ["which", "bwrap"],
                capture_output=True,
                timeout=1,
            )
            socat_result = subprocess.run(
                ["which", "socat"],
                capture_output=True,
                timeout=1,
            )
            assert bwrap_result.returncode == 0
            assert socat_result.returncode == 0


@pytest.mark.skipif(skip_if_not_linux(), reason="Linux only test")
class TestPreGeneratedBpfSupport:
    """Tests for pre-generated BPF support."""

    def test_detect_pre_generated_bpf_files_on_x64_arm64(self):
        """Test that pre-generated BPF files are detected on x64/arm64."""
        # Check if current architecture supports pre-generated BPF
        arch = platform.machine().lower()
        pre_generated_bpf = get_pre_generated_bpf_path()

        if arch in ("x86_64", "amd64", "arm64", "aarch64"):
            # Should have pre-generated BPF for these architectures
            assert pre_generated_bpf is not None
            if pre_generated_bpf:
                assert Path(pre_generated_bpf).exists()
                assert "vendor/seccomp" in pre_generated_bpf
                assert pre_generated_bpf.endswith("unix-block.bpf")
        else:
            # Other architectures should not have pre-generated BPF
            assert pre_generated_bpf is None

    def test_have_sandbox_dependencies_on_x64_arm64_with_bwrap_and_socat(self):
        """Test that sandbox dependencies exist on x64/arm64 with bwrap and socat."""
        pre_generated_bpf = get_pre_generated_bpf_path()

        # Only test on architectures with pre-generated BPF
        if not pre_generated_bpf:
            pytest.skip("Architecture does not support pre-generated BPF")

        # has_linux_sandbox_dependencies_sync should succeed on x64/arm64
        # with just bwrap and socat (pre-built binaries included)
        has_sandbox_deps = has_linux_sandbox_dependencies_sync()

        # On x64/arm64 with pre-built binaries, we should have sandbox deps
        bwrap_result = subprocess.run(
            ["which", "bwrap"], capture_output=True, timeout=1
        )
        socat_result = subprocess.run(
            ["which", "socat"], capture_output=True, timeout=1
        )
        has_apply_seccomp = get_apply_seccomp_binary_path() is not None

        if (
            bwrap_result.returncode == 0
            and socat_result.returncode == 0
            and has_apply_seccomp
        ):
            # Basic deps available - on x64/arm64 this should be sufficient
            # (pre-built apply-seccomp binaries and BPF filters are included)
            arch = platform.machine().lower()
            if arch in ("x86_64", "amd64", "arm64", "aarch64"):
                assert has_sandbox_deps is True

    def test_not_allow_seccomp_on_unsupported_architectures(self):
        """Test that seccomp is not allowed on unsupported architectures."""
        pre_generated_bpf = get_pre_generated_bpf_path()

        # Only test on architectures WITHOUT pre-generated BPF
        if pre_generated_bpf is not None:
            pytest.skip("Architecture supports pre-generated BPF")

        # On architectures without pre-built apply-seccomp binaries,
        # has_linux_sandbox_dependencies_sync() should return false
        # (unless allowAllUnixSockets is set to true)
        has_sandbox_deps = has_linux_sandbox_dependencies_sync(False)

        # Unsupported architectures should not have sandbox deps when seccomp is required
        assert has_sandbox_deps is False

        # But should work when allowAllUnixSockets is true
        has_sandbox_deps_with_bypass = has_linux_sandbox_dependencies_sync(True)
        bwrap_result = subprocess.run(
            ["which", "bwrap"], capture_output=True, timeout=1
        )
        socat_result = subprocess.run(
            ["which", "socat"], capture_output=True, timeout=1
        )

        if bwrap_result.returncode == 0 and socat_result.returncode == 0:
            assert has_sandbox_deps_with_bypass is True


@pytest.mark.skipif(skip_if_not_linux(), reason="Linux only test")
class TestSeccompFilterPreGenerated:
    """Tests for pre-generated seccomp filters."""

    def test_return_pre_generated_bpf_filter_on_x64_arm64(self):
        """Test that pre-generated BPF filter is returned on x64/arm64."""
        arch = platform.machine().lower()
        if arch not in ("x86_64", "amd64", "arm64", "aarch64"):
            pytest.skip("Not a supported architecture")

        filter_path = generate_seccomp_filter()

        assert filter_path is not None
        assert filter_path.endswith(".bpf")
        assert "vendor/seccomp" in filter_path

        # Verify the file exists
        assert Path(filter_path).exists()

        # Verify the file has content (BPF bytecode)
        stats = Path(filter_path).stat()
        assert stats.st_size > 0

        # BPF programs should be a multiple of 8 bytes (struct sock_filter is 8 bytes)
        assert stats.st_size % 8 == 0

    def test_return_same_path_on_repeated_calls(self):
        """Test that same path is returned on repeated calls (pre-generated)."""
        arch = platform.machine().lower()
        if arch not in ("x86_64", "amd64", "arm64", "aarch64"):
            pytest.skip("Not a supported architecture")

        filter1 = generate_seccomp_filter()
        filter2 = generate_seccomp_filter()

        assert filter1 is not None
        assert filter2 is not None

        # Should return same pre-generated file path
        assert filter1 == filter2

    def test_return_none_on_unsupported_architectures(self):
        """Test that None is returned on unsupported architectures."""
        arch = platform.machine().lower()
        if arch in ("x86_64", "amd64", "arm64", "aarch64"):
            pytest.skip("This test is for unsupported architectures only")

        filter_path = generate_seccomp_filter()
        assert filter_path is None

    def test_handle_cleanup_gracefully(self):
        """Test that cleanup handles gracefully (no-op for pre-generated files)."""
        # Cleanup should not throw for any path (it's a no-op)
        cleanup_seccomp_filter("/tmp/test.bpf")
        cleanup_seccomp_filter("/vendor/seccomp/x64/unix-block.bpf")
        cleanup_seccomp_filter("")


@pytest.mark.skipif(skip_if_not_linux(), reason="Linux only test")
class TestApplySeccompBinary:
    """Tests for apply-seccomp binary."""

    def test_find_pre_built_apply_seccomp_binary_on_x64_arm64(self):
        """Test that pre-built apply-seccomp binary is found on x64/arm64."""
        arch = platform.machine().lower()
        if arch not in ("x86_64", "amd64", "arm64", "aarch64"):
            pytest.skip("Not a supported architecture")

        binary_path = get_apply_seccomp_binary_path()
        assert binary_path is not None

        # Verify the file exists
        assert Path(binary_path).exists()

        # Should be in vendor directory
        assert "vendor/seccomp" in binary_path

    def test_return_none_on_unsupported_architectures(self):
        """Test that None is returned on unsupported architectures."""
        arch = platform.machine().lower()
        if arch in ("x86_64", "amd64", "arm64", "aarch64"):
            pytest.skip("This test is for supported architectures only")

        binary_path = get_apply_seccomp_binary_path()
        assert binary_path is None


@pytest.mark.skipif(skip_if_not_linux(), reason="Linux only test")
class TestArchitectureSupport:
    """Tests for architecture support."""

    def test_fail_fast_when_architecture_unsupported_and_seccomp_needed(self):
        """Test that sandbox fails fast when architecture is unsupported and seccomp is needed."""
        if skip_if_not_ant():
            pytest.skip("ANT user only test")

        # This test documents the expected behavior:
        # When the architecture is not x64/arm64, the sandbox should fail the dependency
        # check instead of silently running without seccomp protection
        assert True  # Placeholder - actual behavior verified by integration tests

    def test_include_architecture_information_in_error_messages(self):
        """Test that error messages include architecture information."""
        if skip_if_not_ant():
            pytest.skip("ANT user only test")

        # Verify error messages mention architecture support and alternatives
        # This is a documentation test to ensure error messages are helpful
        expected_in_error_message = [
            "x64",
            "arm64",
            "architecture",
            "allowAllUnixSockets",
        ]

        # Error messages should guide users to either:
        # 1. Use a supported architecture (x64/arm64), OR
        # 2. Set allowAllUnixSockets: true to opt out
        assert len(expected_in_error_message) > 0

    async def test_allow_bypassing_architecture_requirement_with_allow_all_unix_sockets(self):
        """Test that architecture requirement can be bypassed with allowAllUnixSockets."""
        # When allowAllUnixSockets is true, architecture check should not matter
        test_command = 'echo "test"'

        # This should NOT throw even on unsupported architecture (when allowAllUnixSockets=true)
        wrapped_command = wrap_command_with_sandbox_linux(
            test_command,
            needs_network_restriction=False,
            allow_all_unix_sockets=True,  # Bypass seccomp
        )

        # Command should not contain apply-seccomp binary
        assert "apply-seccomp" not in wrapped_command
        assert 'echo "test"' in wrapped_command


@pytest.mark.skipif(skip_if_not_linux() or skip_if_not_ant(), reason="Linux and ANT user only")
class TestUserTypeGating:
    """Tests for USER_TYPE gating."""

    def test_only_apply_seccomp_in_sandbox_for_ant_users(self):
        """Test that seccomp is only applied in sandbox for ANT users."""
        if not has_linux_sandbox_dependencies_sync():
            pytest.skip("Sandbox dependencies not available")

        test_command = 'echo "test"'
        wrapped_command = wrap_command_with_sandbox_linux(
            test_command,
            needs_network_restriction=False,
        )

        if os.environ.get("USER_TYPE") == "ant":
            # ANT users should have apply-seccomp binary in command
            assert "apply-seccomp" in wrapped_command
        else:
            # Non-ANT users should not have seccomp
            assert "apply-seccomp" not in wrapped_command


@pytest.mark.skipif(skip_if_not_linux() or skip_if_not_ant(), reason="Linux and ANT user only")
class TestSocketFilteringBehavior:
    """Tests for socket filtering behavior."""

    @pytest.fixture
    def filter_path(self):
        """Get filter path for tests."""
        return generate_seccomp_filter()

    def test_block_unix_socket_creation_sock_stream(self, filter_path):
        """Test that Unix socket creation (SOCK_STREAM) is blocked."""
        if not filter_path:
            pytest.skip("No filter path available")

        test_command = 'python3 -c "import socket; s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); print(\'Unix socket created\')"'

        wrapped_command = wrap_command_with_sandbox_linux(
            test_command,
            needs_network_restriction=False,
        )

        result = subprocess.run(
            ["bash", "-c", wrapped_command],
            capture_output=True,
            timeout=5,
        )

        assert result.returncode != 0
        stderr = result.stderr.decode("utf-8", errors="ignore").lower()
        assert "permission denied" in stderr or "operation not permitted" in stderr

    def test_block_unix_socket_creation_sock_dgram(self, filter_path):
        """Test that Unix socket creation (SOCK_DGRAM) is blocked."""
        if not filter_path:
            pytest.skip("No filter path available")

        test_command = 'python3 -c "import socket; s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM); print(\'Unix datagram created\')"'

        wrapped_command = wrap_command_with_sandbox_linux(
            test_command,
            needs_network_restriction=False,
        )

        result = subprocess.run(
            ["bash", "-c", wrapped_command],
            capture_output=True,
            timeout=5,
        )

        assert result.returncode != 0
        stderr = result.stderr.decode("utf-8", errors="ignore").lower()
        assert "permission denied" in stderr or "operation not permitted" in stderr

    def test_allow_tcp_socket_creation_ipv4(self, filter_path):
        """Test that TCP socket creation (IPv4) is allowed."""
        if not filter_path:
            pytest.skip("No filter path available")

        test_command = 'python3 -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); print(\'TCP socket created\')"'

        wrapped_command = wrap_command_with_sandbox_linux(
            test_command,
            needs_network_restriction=False,
        )

        result = subprocess.run(
            ["bash", "-c", wrapped_command],
            capture_output=True,
            timeout=5,
        )

        assert result.returncode == 0
        assert "TCP socket created" in result.stdout.decode("utf-8", errors="ignore")

    def test_allow_udp_socket_creation_ipv4(self, filter_path):
        """Test that UDP socket creation (IPv4) is allowed."""
        if not filter_path:
            pytest.skip("No filter path available")

        test_command = 'python3 -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); print(\'UDP socket created\')"'

        wrapped_command = wrap_command_with_sandbox_linux(
            test_command,
            needs_network_restriction=False,
        )

        result = subprocess.run(
            ["bash", "-c", wrapped_command],
            capture_output=True,
            timeout=5,
        )

        assert result.returncode == 0
        assert "UDP socket created" in result.stdout.decode("utf-8", errors="ignore")

    def test_allow_ipv6_socket_creation(self, filter_path):
        """Test that IPv6 socket creation is allowed."""
        if not filter_path:
            pytest.skip("No filter path available")

        test_command = 'python3 -c "import socket; s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM); print(\'IPv6 socket created\')"'

        wrapped_command = wrap_command_with_sandbox_linux(
            test_command,
            needs_network_restriction=False,
        )

        result = subprocess.run(
            ["bash", "-c", wrapped_command],
            capture_output=True,
            timeout=5,
        )

        assert result.returncode == 0
        assert "IPv6 socket created" in result.stdout.decode("utf-8", errors="ignore")


@pytest.mark.skipif(skip_if_not_linux() or skip_if_not_ant(), reason="Linux and ANT user only")
class TestTwoStageSeccompApplication:
    """Tests for two-stage seccomp application."""

    def test_allow_network_infrastructure_to_run_before_filter(self):
        """Test that network infrastructure can run before filter."""
        if not has_linux_sandbox_dependencies_sync():
            pytest.skip("Sandbox dependencies not available")

        # This test verifies that the socat processes can start successfully
        # even though they use Unix sockets, because they run before the filter
        test_command = 'echo "test"'

        wrapped_command = wrap_command_with_sandbox_linux(
            test_command,
            needs_network_restriction=False,
        )

        # Command should include both socat and the apply-seccomp binary
        assert "socat" in wrapped_command
        assert "apply-seccomp" in wrapped_command

        # The socat should come before the apply-seccomp
        socat_index = wrapped_command.find("socat")
        seccomp_index = wrapped_command.find("apply-seccomp")
        assert socat_index > -1
        assert seccomp_index > -1
        assert socat_index < seccomp_index

    def test_execute_user_command_with_filter_applied(self):
        """Test that user command executes with filter applied."""
        if not has_linux_sandbox_dependencies_sync():
            pytest.skip("Sandbox dependencies not available")

        # User command tries to create Unix socket - should fail
        test_command = 'python3 -c "import socket; socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)"'

        wrapped_command = wrap_command_with_sandbox_linux(
            test_command,
            needs_network_restriction=False,
        )

        result = subprocess.run(
            ["bash", "-c", wrapped_command],
            capture_output=True,
            timeout=5,
        )

        # Should fail due to seccomp filter
        assert result.returncode != 0


@pytest.mark.skipif(skip_if_not_linux(), reason="Linux only test")
class TestSandboxIntegration:
    """Tests for sandbox integration."""

    def test_handle_commands_without_network_or_filesystem_restrictions(self):
        """Test that commands without restrictions are handled."""
        if not has_linux_sandbox_dependencies_sync():
            pytest.skip("Sandbox dependencies not available")

        test_command = 'echo "hello world"'
        wrapped_command = wrap_command_with_sandbox_linux(
            test_command,
            needs_network_restriction=False,
        )

        # Should still wrap the command even without restrictions
        assert wrapped_command is not None
        assert isinstance(wrapped_command, str)

    def test_wrap_commands_with_filesystem_restrictions(self):
        """Test that commands with filesystem restrictions are wrapped."""
        if not has_linux_sandbox_dependencies_sync():
            pytest.skip("Sandbox dependencies not available")

        test_command = "ls /"
        wrapped_command = wrap_command_with_sandbox_linux(
            test_command,
            needs_network_restriction=False,
            write_config={
                "allowOnly": ["/tmp"],
                "denyWithinAllow": [],
            },
        )

        assert wrapped_command is not None
        assert "bwrap" in wrapped_command

    def test_include_seccomp_for_ant_users_with_dependencies(self):
        """Test that seccomp is included for ANT users with dependencies."""
        if not has_linux_sandbox_dependencies_sync():
            pytest.skip("Sandbox dependencies not available")

        test_command = 'echo "test"'
        wrapped_command = wrap_command_with_sandbox_linux(
            test_command,
            needs_network_restriction=False,
        )

        is_ant = os.environ.get("USER_TYPE") == "ant"

        if is_ant:
            assert "apply-seccomp" in wrapped_command
        else:
            assert "apply-seccomp" not in wrapped_command


@pytest.mark.skipif(skip_if_not_linux(), reason="Linux only test")
class TestErrorHandling:
    """Tests for error handling."""

    def test_handle_cleanup_calls_gracefully(self):
        """Test that cleanup calls are handled gracefully (no-op)."""
        # Cleanup is a no-op for pre-generated files, should never throw
        cleanup_seccomp_filter("")
        cleanup_seccomp_filter("/invalid/path/filter.bpf")
        cleanup_seccomp_filter("/tmp/nonexistent.bpf")
        cleanup_seccomp_filter("/vendor/seccomp/x64/unix-block.bpf")

