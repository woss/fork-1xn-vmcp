"""Integration tests for sandbox functionality."""

import os
import socket
import tempfile
import time
import pytest
import subprocess
from pathlib import Path

from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig
from sandbox_runtime.sandbox.seccomp import generate_seccomp_filter
from sandbox_runtime.sandbox.linux_utils import wrap_command_with_sandbox_linux
from sandbox_runtime.utils.platform import get_platform


def create_test_config(test_dir: str) -> SandboxRuntimeConfig:
    """Create a minimal test configuration for the sandbox with example.com allowed."""
    return SandboxRuntimeConfig.from_json({
        "network": {
            "allowedDomains": ["example.com"],
            "deniedDomains": [],
        },
        "filesystem": {
            "denyRead": [],
            "allowWrite": [test_dir],
            "denyWrite": [],
        },
    })


def skip_if_not_linux() -> bool:
    """Check if platform is not Linux."""
    return get_platform() != "linux"


def assert_precompiled_bpf_in_use():
    """Assert that the sandbox is using pre-generated BPF files from vendor/."""
    bpf_path = generate_seccomp_filter()

    assert bpf_path is not None
    assert "/vendor/seccomp/" in bpf_path
    assert Path(bpf_path).exists()

    print(f"✓ Verified using pre-compiled BPF: {bpf_path}")


@pytest.mark.skipif(skip_if_not_linux(), reason="Linux only test")
@pytest.mark.asyncio
class TestSandboxIntegration:
    """Integration tests for sandbox functionality."""

    @pytest.fixture(scope="class")
    def test_dir(self):
        """Create test directory."""
        # Use a directory within the repository (which is the CWD)
        test_dir = Path.cwd() / ".sandbox-test-tmp"
        test_dir.mkdir(parents=True, exist_ok=True)
        yield test_dir
        # Cleanup
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)

    @pytest.fixture(scope="class")
    def socket_server(self):
        """Create a Unix socket server for testing."""
        import threading

        test_socket_path = "/tmp/claude-test.sock"

        # Clean up any existing socket
        if Path(test_socket_path).exists():
            Path(test_socket_path).unlink()

        # Create Unix socket server
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(test_socket_path)
        server.listen(1)

        def handle_client():
            while True:
                try:
                    client_socket, addr = server.accept()
                    data = client_socket.recv(1024)
                    client_socket.send(b"Echo: " + data)
                    client_socket.close()
                except Exception:
                    break

        server_thread = threading.Thread(target=handle_client, daemon=True)
        server_thread.start()

        yield server, test_socket_path

        # Cleanup
        server.close()
        if Path(test_socket_path).exists():
            Path(test_socket_path).unlink()

    @pytest.fixture(autouse=True)
    async def setup_and_teardown(self, test_dir):
        """Setup and teardown for each test."""
        await SandboxManager.initialize(create_test_config(str(test_dir)))
        yield
        await SandboxManager.reset()

    @pytest.fixture
    def precompiled_bpf_setup(self):
        """Setup for pre-compiled BPF tests."""
        print("\n=== Testing with Pre-compiled BPF ===")
        assert_precompiled_bpf_in_use()

    async def test_block_unix_socket_connections_with_seccomp(self, socket_server, precompiled_bpf_setup):
        """Test that Unix socket connections are blocked with seccomp."""
        server, test_socket_path = socket_server

        # Wrap command with sandbox
        command = await SandboxManager.wrap_with_sandbox(
            f'echo "Test message" | nc -U {test_socket_path}',
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Should fail due to seccomp filter blocking socket creation
        output = (result.stderr or result.stdout or "").lower()
        # Different netcat versions report the error differently
        has_expected_error = (
            "operation not permitted" in output
            or "create unix socket failed" in output
        )
        assert has_expected_error
        assert result.returncode != 0

    async def test_block_http_requests_to_non_allowlisted_domains(self, precompiled_bpf_setup):
        """Test that HTTP requests to non-allowlisted domains are blocked."""
        command = await SandboxManager.wrap_with_sandbox(
            "curl -s http://blocked-domain.example",
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        output = (result.stderr or result.stdout or "").lower()
        assert "blocked by network allowlist" in output

    async def test_block_http_requests_to_anthropic_com(self, precompiled_bpf_setup):
        """Test that HTTP requests to anthropic.com (not in allowlist) are blocked."""
        # Use --max-time to timeout quickly, and --show-error to see proxy errors
        command = await SandboxManager.wrap_with_sandbox(
            "curl -s --show-error --max-time 2 https://www.anthropic.com",
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=3,
        )

        # The proxy blocks the connection, causing curl to timeout or fail
        # Check that the request did not succeed
        output = (result.stderr or result.stdout or "").lower()
        did_fail = result.returncode != 0 or result.returncode is None
        assert did_fail

        # The output should either contain an error or be empty (timeout)
        # It should NOT contain successful HTML response
        assert "<!doctype html" not in output
        assert "<html" not in output

    async def test_allow_http_requests_to_allowlisted_domains(self, precompiled_bpf_setup):
        """Test that HTTP requests to allowlisted domains are allowed."""
        # Note: example.com should be in the allowlist via config
        command = await SandboxManager.wrap_with_sandbox(
            "curl -s http://example.com",
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Should succeed and return HTML
        output = result.stdout or ""
        assert result.returncode == 0
        assert "Example Domain" in output

    async def test_block_writes_outside_current_working_directory(self, test_dir, precompiled_bpf_setup):
        """Test that writes outside current working directory are blocked."""
        test_file = Path(tempfile.gettempdir()) / "sandbox-blocked-write.txt"

        # Clean up if exists
        if test_file.exists():
            test_file.unlink()

        command = await SandboxManager.wrap_with_sandbox(
            f'echo "should fail" > {test_file}',
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(test_dir),
            timeout=5,
        )

        # Should fail with read-only file system error
        output = (result.stderr or result.stdout or "").lower()
        assert "read-only file system" in output
        assert not test_file.exists()

    async def test_allow_writes_within_current_working_directory(self, test_dir, precompiled_bpf_setup):
        """Test that writes within current working directory are allowed."""
        # Ensure test directory exists
        test_dir.mkdir(parents=True, exist_ok=True)

        test_file = test_dir / "allowed-write.txt"
        test_content = "test content from sandbox"

        # Clean up if exists
        if test_file.exists():
            test_file.unlink()

        command = await SandboxManager.wrap_with_sandbox(
            f'echo "{test_content}" > allowed-write.txt',
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(test_dir),
            timeout=5,
        )

        # Debug output if failed
        if result.returncode != 0:
            print(f"Command failed: {command}")
            print(f"Status: {result.returncode}")
            print(f"Stdout: {result.stdout}")
            print(f"Stderr: {result.stderr}")
            print(f"CWD: {test_dir}")
            print(f"Test file path: {test_file}")

        # Should succeed
        assert result.returncode == 0
        assert test_file.exists()

        # Verify content
        content = test_file.read_text()
        assert test_content in content

        # Clean up
        if test_file.exists():
            test_file.unlink()

    async def test_allow_reads_from_anywhere(self, precompiled_bpf_setup):
        """Test that reads from anywhere are allowed."""
        # Try reading from home directory
        command = await SandboxManager.wrap_with_sandbox(
            "head -n 5 ~/.bashrc",
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Should succeed (assuming .bashrc exists)
        assert result.returncode == 0

        # If .bashrc exists, should have some content
        bashrc_path = Path.home() / ".bashrc"
        if bashrc_path.exists():
            assert result.stdout

    async def test_allow_writes_in_seccomp_only_mode(self, test_dir, precompiled_bpf_setup):
        """Test that writes are allowed in seccomp-only mode (no network restrictions)."""
        test_file = test_dir / "seccomp-only-write.txt"
        test_content = "seccomp-only test content"

        # Call wrap_command_with_sandbox_linux with no network restrictions
        # This forces the seccomp-only code path
        command = wrap_command_with_sandbox_linux(
            f'echo "{test_content}" > {test_file}',
            needs_network_restriction=False,  # No network - forces seccomp-only path
            write_config={
                "allowOnly": [str(test_dir)],  # Only allow writes to TEST_DIR
                "denyWithinAllow": [],
            },
            allow_all_unix_sockets=False,  # Enable seccomp
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(test_dir),
            timeout=5,
        )

        if result.returncode != 0:
            print("Command failed in seccomp-only mode")
            print(f"Status: {result.returncode}")
            print(f"Stdout: {result.stdout}")
            print(f"Stderr: {result.stderr}")
            print(f"CWD: {test_dir}")
            print(f"Test file path: {test_file}")

        # Should succeed
        assert result.returncode == 0
        assert test_file.exists()

        content = test_file.read_text()
        assert content.strip() == test_content

        # Clean up
        if test_file.exists():
            test_file.unlink()

    async def test_execute_basic_commands_successfully(self, precompiled_bpf_setup):
        """Test that basic commands execute successfully."""
        command = await SandboxManager.wrap_with_sandbox(
            'echo "Hello from sandbox"',
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0
        assert "Hello from sandbox" in result.stdout

    async def test_handle_complex_command_pipelines(self, precompiled_bpf_setup):
        """Test that complex command pipelines are handled."""
        command = await SandboxManager.wrap_with_sandbox(
            'echo "line1\nline2\nline3" | grep line2',
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0
        assert "line2" in result.stdout
        assert "line1" not in result.stdout

    async def test_execute_commands_with_zsh_when_bin_shell_specified(self, precompiled_bpf_setup):
        """Test that commands execute with zsh when binShell is specified."""
        # Check if zsh is available
        zsh_check = subprocess.run(
            "which zsh",
            shell=True,
            capture_output=True,
            text=True,
        )
        if zsh_check.returncode != 0:
            pytest.skip("zsh not available")

        # Use a zsh-specific feature: $ZSH_VERSION
        command = await SandboxManager.wrap_with_sandbox(
            'echo "Shell: $ZSH_VERSION"',
            "zsh",
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0
        # Should contain version number (e.g., "Shell: 5.8.1")
        assert "Shell:" in result.stdout
        import re
        assert re.search(r"Shell: \d+\.\d+", result.stdout)

    async def test_use_zsh_syntax_successfully_with_bin_shell_zsh(self, precompiled_bpf_setup):
        """Test that zsh syntax works successfully with binShell=zsh."""
        # Check if zsh is available
        zsh_check = subprocess.run(
            "which zsh",
            shell=True,
            capture_output=True,
            text=True,
        )
        if zsh_check.returncode != 0:
            pytest.skip("zsh not available")

        # Use zsh parameter expansion feature
        command = await SandboxManager.wrap_with_sandbox(
            'VAR="hello world" && echo ${VAR:u}',
            "zsh",
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0
        assert "HELLO WORLD" in result.stdout

    async def test_default_to_bash_when_bin_shell_not_specified(self, precompiled_bpf_setup):
        """Test that bash is used by default when binShell is not specified."""
        # Check for bash-specific variable
        command = await SandboxManager.wrap_with_sandbox(
            'echo "Shell: $BASH_VERSION"',
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0
        # Should contain bash version
        import re
        assert re.search(r"Shell: \d+\.\d+", result.stdout)

    async def test_isolate_pid_namespace(self, precompiled_bpf_setup):
        """Test that PID namespace is isolated - sandboxed processes cannot see host PIDs."""
        # Use /proc to check PID namespace isolation
        # Inside sandbox, should only see sandbox PIDs in /proc
        command = await SandboxManager.wrap_with_sandbox(
            "ls /proc | grep -E '^[0-9]+$' | wc -l",
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0

        # Should see very few PIDs (only sandbox processes)
        pid_count = int(result.stdout.strip())
        assert pid_count < 30  # Host would have 100+
        assert pid_count > 0  # But at least some processes

    async def test_prevent_symlink_based_filesystem_escape_attempts(self, test_dir, precompiled_bpf_setup):
        """Test that symlink-based filesystem escape attempts are prevented."""
        # Note: Reads are allowed from anywhere, so test WRITE escape attempt
        link_in_allowed = test_dir / "escape-link-write"
        target_outside = Path(tempfile.gettempdir()) / f"escape-test-{int(time.time())}.txt"

        # Try to create symlink inside allowed dir pointing to restricted location
        # Then try to write through it
        command = await SandboxManager.wrap_with_sandbox(
            f'ln -s {target_outside} {link_in_allowed} 2>&1 && echo "escaped" > {link_in_allowed} 2>&1',
        )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(test_dir),
            timeout=5,
        )

        # Write should fail (read-only file system for /tmp)
        output = (result.stderr or result.stdout or "").lower()
        assert "read-only file system" in output

        # Target file should NOT exist
        assert not target_outside.exists()

        # Clean up
        if link_in_allowed.exists():
            link_in_allowed.unlink()
        if target_outside.exists():
            target_outside.unlink()

    async def test_terminate_background_processes_when_sandbox_exits(self, test_dir, precompiled_bpf_setup):
        """Test that background processes are terminated when sandbox exits."""
        # Create a unique marker file that a background process will touch
        marker_file = test_dir / "background-process-marker.txt"

        if marker_file.exists():
            marker_file.unlink()

        # Start a background process that writes every 0.5 second
        command = await SandboxManager.wrap_with_sandbox(
            f'(while true; do echo "alive" >> {marker_file}; sleep 0.5; done) & sleep 2',
        )

        start_time = time.time()
        subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(test_dir),
            timeout=5,
        )
        end_time = time.time()

        # Wait a bit to ensure background process would continue if not killed
        time.sleep(2)

        if marker_file.exists():
            content = marker_file.read_text()
            lines = len(content.strip().split("\n"))

            # Should have ~4 lines (2 seconds / 0.5s each), not 10+ (if process continued for 5s)
            assert lines < 10

            marker_file.unlink()
        else:
            # If file doesn't exist, that's also fine - process was killed
            assert True

        # Verify total execution was ~2 seconds, not hanging
        assert (end_time - start_time) < 4

    async def test_prevent_privilege_escalation_attempts(self, test_dir, precompiled_bpf_setup):
        """Test that privilege escalation attempts are prevented."""
        # Test 1: Setuid binaries cannot actually elevate privileges
        # Note: The setuid bit CAN be set on files in writable directories,
        # but bwrap ensures it doesn't grant actual privilege escalation
        setuid_test = test_dir / "setuid-test"

        command1 = await SandboxManager.wrap_with_sandbox(
            f'cp /bin/bash {setuid_test} 2>&1 && chmod u+s {setuid_test} 2>&1 && {setuid_test} -c "id -u" 2>&1',
        )

        result1 = subprocess.run(
            command1,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(test_dir),
            timeout=5,
        )

        # Should still run as the same UID (not root), proving setuid doesn't work
        uid_lines = result1.stdout.strip().split("\n")
        uid = uid_lines[-1] if uid_lines else "0"
        assert int(uid) > 0  # Not root (0)

        # Test 2: Cannot use sudo/su (should not be available or fail)
        command2 = await SandboxManager.wrap_with_sandbox(
            'sudo -n echo "elevated" 2>&1 || su -c "echo elevated" 2>&1 || echo "commands blocked"',
        )

        result2 = subprocess.run(
            command2,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Should not successfully escalate
        output = result2.stdout.lower()
        if "elevated" in output and "commands blocked" not in output:
            # If "elevated" appears without "commands blocked", it should be in an error message
            import re
            assert re.search(
                r"not found|command not found|no such file|not permitted|password|cannot|no password",
                output,
            )

        # Cleanup
        if setuid_test.exists():
            setuid_test.unlink()

    async def test_enforce_network_restrictions_across_protocols_and_ports(self, precompiled_bpf_setup):
        """Test that network restrictions are enforced across protocols and ports."""
        # Test 1: HTTPS to blocked domain (not just HTTP)
        command1 = await SandboxManager.wrap_with_sandbox(
            'curl -s --show-error --max-time 2 --connect-timeout 2 https://blocked-domain.example 2>&1 || echo "curl_failed"',
        )

        result1 = subprocess.run(
            command1,
            shell=True,
            capture_output=True,
            text=True,
            timeout=4,
        )

        # Should fail - curl should not succeed
        output1 = result1.stdout.lower()
        # Should either timeout, fail to resolve, or curl should fail
        did_not_succeed = (
            "curl_failed" in output1
            or "timeout" in output1
            or "could not resolve" in output1
            or "failed" in output1
            or len(output1) == 0  # Timeout with no output
        )
        assert did_not_succeed

        # Test 2: Non-standard port should also be blocked
        command2 = await SandboxManager.wrap_with_sandbox(
            "curl -s --show-error --max-time 2 http://blocked-domain.example:8080 2>&1",
        )

        result2 = subprocess.run(
            command2,
            shell=True,
            capture_output=True,
            text=True,
            timeout=3,
        )

        # Should be blocked - check output contains block message
        output2 = result2.stdout.lower()
        assert "blocked by network allowlist" in output2

        # Test 3: Direct IP addresses should also be blocked
        # The network allowlist blocks ALL domains/IPs not explicitly allowed
        command3 = await SandboxManager.wrap_with_sandbox(
            "curl -s --max-time 2 http://1.1.1.1 2>&1",  # Cloudflare DNS
        )

        result3 = subprocess.run(
            command3,
            shell=True,
            capture_output=True,
            text=True,
            timeout=3,
        )

        # IP addresses should be blocked by the proxy
        # Note: curl may return 0 even when blocked if it receives a 403 response
        output3 = result3.stdout.lower()
        assert "blocked by network allowlist" in output3

        # Test 4: Verify HTTPS to allowed domain still works
        command4 = await SandboxManager.wrap_with_sandbox(
            "curl -s --max-time 5 https://example.com 2>&1",
        )

        result4 = subprocess.run(
            command4,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # HTTPS should work for allowed domain (unless transient network issue)
        # At minimum, it shouldn't be blocked by our proxy
        output4 = result4.stdout.lower()
        assert "blocked by network allowlist" not in output4
        if result4.returncode == 0:
            assert "Example Domain" in result4.stdout

    async def test_enforce_wildcard_domain_pattern_matching_correctly(self, test_dir, precompiled_bpf_setup):
        """Test that wildcard domain pattern matching is enforced correctly."""
        # Reset and reinitialize with wildcard pattern
        await SandboxManager.reset()
        await SandboxManager.initialize(
            SandboxRuntimeConfig.from_json({
                "network": {
                    "allowedDomains": ["*.github.com", "example.com"],
                    "deniedDomains": [],
                },
                "filesystem": {
                    "denyRead": [],
                    "allowWrite": [str(test_dir)],
                    "denyWrite": [],
                },
            })
        )

        # Test 1: Subdomain should match wildcard
        command1 = await SandboxManager.wrap_with_sandbox(
            "curl -s --max-time 3 http://api.github.com 2>&1 | head -20",
        )

        result1 = subprocess.run(
            command1,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Should NOT be blocked - api.github.com matches *.github.com
        output1 = result1.stdout.lower()
        assert "blocked by network allowlist" not in output1

        # Test 2: Base domain should NOT match wildcard (*.github.com doesn't match github.com)
        command2 = await SandboxManager.wrap_with_sandbox(
            "curl -s --max-time 2 http://github.com 2>&1",
        )

        result2 = subprocess.run(
            command2,
            shell=True,
            capture_output=True,
            text=True,
            timeout=3,
        )

        # Should be blocked - github.com does NOT match *.github.com
        output2 = result2.stdout.lower()
        assert "blocked by network allowlist" in output2

        # Test 3: Malicious lookalike domain should NOT match
        command3 = await SandboxManager.wrap_with_sandbox(
            "curl -s --max-time 2 http://malicious-github.com 2>&1",
        )

        result3 = subprocess.run(
            command3,
            shell=True,
            capture_output=True,
            text=True,
            timeout=3,
        )

        # Should be blocked - malicious-github.com does NOT match *.github.com
        output3 = result3.stdout.lower()
        assert "blocked by network allowlist" in output3

        # Test 4: Multiple subdomains should match
        command4 = await SandboxManager.wrap_with_sandbox(
            "curl -s --max-time 3 http://raw.githubusercontent.com 2>&1 | head -20",
        )

        result4 = subprocess.run(
            command4,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # githubusercontent.com should be blocked (doesn't match *.github.com)
        output4 = result4.stdout.lower()
        assert "blocked by network allowlist" in output4

        # Restore original config
        await SandboxManager.reset()
        await SandboxManager.initialize(create_test_config(str(test_dir)))

    async def test_prevent_creation_of_special_file_types(self, test_dir, precompiled_bpf_setup):
        """Test that creation of special file types that could bypass restrictions is prevented."""
        fifo_path = test_dir / "test.fifo"
        regular_file = test_dir / "regular.txt"
        hardlink_path = test_dir / "hardlink.txt"
        device_path = test_dir / "fake-device"

        # Clean up any existing test files
        for path in [fifo_path, regular_file, hardlink_path, device_path]:
            if path.exists():
                path.unlink()

        # Test 1: FIFO (named pipe) creation in allowed location should work
        command1 = await SandboxManager.wrap_with_sandbox(
            f"mkfifo {fifo_path} && test -p {fifo_path} && echo 'FIFO created'",
        )

        result1 = subprocess.run(
            command1,
            shell=True,
            capture_output=True,
            text=True,
            timeout=3,
        )

        assert result1.returncode == 0
        assert "FIFO created" in result1.stdout
        assert fifo_path.exists()

        # Test 2: Hard link pointing outside allowed location should fail
        # First create a file in allowed location
        command2a = await SandboxManager.wrap_with_sandbox(
            f'echo "test content" > {regular_file}',
        )

        subprocess.run(
            command2a,
            shell=True,
            capture_output=True,
            text=True,
            timeout=3,
        )

        # Try to create hard link to /etc/passwd (outside allowed location)
        command2b = await SandboxManager.wrap_with_sandbox(
            f"ln /etc/passwd {hardlink_path} 2>&1",
        )

        result2b = subprocess.run(
            command2b,
            shell=True,
            capture_output=True,
            text=True,
            timeout=3,
        )

        # Should fail - cannot create hard link to read-only location
        # Note: May fail with "invalid cross-device link" due to mount namespaces
        assert result2b.returncode != 0
        output2 = result2b.stdout.lower()
        import re
        assert re.search(
            r"read-only|permission denied|not permitted|operation not permitted|cross-device",
            output2,
        )

        # Test 3: Device node creation should fail (requires CAP_MKNOD which sandbox doesn't have)
        command3 = await SandboxManager.wrap_with_sandbox(
            f"mknod {device_path} c 1 3 2>&1",
        )

        result3 = subprocess.run(
            command3,
            shell=True,
            capture_output=True,
            text=True,
            timeout=3,
        )

        # Should fail - mknod requires special privileges
        assert result3.returncode != 0
        output3 = result3.stdout.lower()
        assert re.search(
            r"operation not permitted|permission denied|not permitted",
            output3,
        )
        assert not device_path.exists()

        # Cleanup
        for path in [fifo_path, regular_file, hardlink_path, device_path]:
            if path.exists():
                path.unlink()

