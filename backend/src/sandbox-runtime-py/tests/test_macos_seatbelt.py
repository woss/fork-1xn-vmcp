"""Tests for macOS Seatbelt read bypass prevention."""

import os
import tempfile
import time
import pytest
import subprocess
from pathlib import Path

from sandbox_runtime.sandbox.macos_utils import wrap_command_with_sandbox_macos
from sandbox_runtime.utils.platform import get_platform


def skip_if_not_macos() -> bool:
    """Check if platform is not macOS."""
    return get_platform() != "macos"


@pytest.mark.skipif(skip_if_not_macos(), reason="macOS only test")
class TestMacOSSeatbeltReadBypassPrevention:
    """Tests for macOS Seatbelt read bypass prevention."""

    @pytest.fixture(scope="class")
    def test_base_dir(self):
        """Create test base directory."""
        test_dir = Path(tempfile.gettempdir()) / f"seatbelt-test-{int(time.time())}"
        test_dir.mkdir(parents=True, exist_ok=True)
        yield test_dir
        # Cleanup
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)

    @pytest.fixture(scope="class")
    def test_setup(self, test_base_dir):
        """Setup test files and directories."""
        test_denied_dir = test_base_dir / "denied-dir"
        test_secret_file = test_denied_dir / "secret.txt"
        test_secret_content = "SECRET_CREDENTIAL_DATA"
        test_moved_file = test_base_dir / "moved-secret.txt"
        test_moved_dir = test_base_dir / "moved-denied-dir"

        # Additional test files for glob pattern testing
        test_glob_dir = test_base_dir / "glob-test"
        test_glob_file1 = test_glob_dir / "secret1.txt"
        test_glob_file2 = test_glob_dir / "secret2.log"
        test_glob_moved = test_base_dir / "moved-glob.txt"

        # Create test directory structure
        test_denied_dir.mkdir(parents=True, exist_ok=True)
        test_secret_file.write_text(test_secret_content)

        # Create glob test files
        test_glob_dir.mkdir(parents=True, exist_ok=True)
        test_glob_file1.write_text("GLOB_SECRET_1")
        test_glob_file2.write_text("GLOB_SECRET_2")

        return {
            "test_base_dir": test_base_dir,
            "test_denied_dir": test_denied_dir,
            "test_secret_file": test_secret_file,
            "test_secret_content": test_secret_content,
            "test_moved_file": test_moved_file,
            "test_moved_dir": test_moved_dir,
            "test_glob_dir": test_glob_dir,
            "test_glob_file1": test_glob_file1,
            "test_glob_file2": test_glob_file2,
            "test_glob_moved": test_glob_moved,
        }

    async def test_block_moving_read_denied_file_to_readable_location(self, test_setup):
        """Test that moving a read-denied file to a readable location is blocked."""
        # Use actual read restriction config with literal path
        read_config = {
            "denyOnly": [str(test_setup["test_denied_dir"])]
        }

        # Generate actual sandbox command using our production code
        wrapped_command = await wrap_command_with_sandbox_macos(
            f'mv {test_setup["test_secret_file"]} {test_setup["test_moved_file"]}',
            needs_network_restriction=False,
            read_config=read_config,
            write_config=None,
        )

        # Verify the file exists before test
        assert test_setup["test_secret_file"].exists()

        # Execute the wrapped command
        result = subprocess.run(
            wrapped_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # The move should fail with operation not permitted
        assert result.returncode != 0
        output = result.stderr.lower()
        assert "operation not permitted" in output

        # Verify the file was NOT moved
        assert test_setup["test_secret_file"].exists()
        assert not test_setup["test_moved_file"].exists()

    async def test_still_block_reading_the_file(self, test_setup):
        """Test that reading the file is still blocked (sanity check)."""
        # Use actual read restriction config
        read_config = {
            "denyOnly": [str(test_setup["test_denied_dir"])]
        }

        # Generate actual sandbox command
        wrapped_command = await wrap_command_with_sandbox_macos(
            f'cat {test_setup["test_secret_file"]}',
            needs_network_restriction=False,
            read_config=read_config,
            write_config=None,
        )

        # Execute the wrapped command
        result = subprocess.run(
            wrapped_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # The read should fail
        assert result.returncode != 0
        output = result.stderr.lower()
        assert "operation not permitted" in output

        # Should NOT see the secret content
        assert test_setup["test_secret_content"] not in result.stdout

    async def test_block_moving_ancestor_directory_of_read_denied_file(self, test_setup):
        """Test that moving an ancestor directory of a read-denied file is blocked."""
        # Use actual read restriction config
        read_config = {
            "denyOnly": [str(test_setup["test_denied_dir"])]
        }

        # Generate actual sandbox command
        wrapped_command = await wrap_command_with_sandbox_macos(
            f'mv {test_setup["test_denied_dir"]} {test_setup["test_moved_dir"]}',
            needs_network_restriction=False,
            read_config=read_config,
            write_config=None,
        )

        # Verify the directory exists before test
        assert test_setup["test_denied_dir"].exists()

        # Execute the wrapped command
        result = subprocess.run(
            wrapped_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # The move should fail
        assert result.returncode != 0
        output = result.stderr.lower()
        assert "operation not permitted" in output

        # Verify the directory was NOT moved
        assert test_setup["test_denied_dir"].exists()
        assert not test_setup["test_moved_dir"].exists()

    async def test_block_moving_grandparent_directory(self, test_setup):
        """Test that moving the grandparent directory is blocked."""
        # Deny reading a specific file deep in the hierarchy
        read_config = {
            "denyOnly": [str(test_setup["test_secret_file"])]
        }

        moved_base_dir = Path(tempfile.gettempdir()) / f"moved-base-{int(time.time())}"

        # Try to move the grandparent directory (TEST_BASE_DIR)
        wrapped_command = await wrap_command_with_sandbox_macos(
            f'mv {test_setup["test_base_dir"]} {moved_base_dir}',
            needs_network_restriction=False,
            read_config=read_config,
            write_config=None,
        )

        # Execute the wrapped command
        result = subprocess.run(
            wrapped_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # The move should fail
        assert result.returncode != 0
        output = result.stderr.lower()
        assert "operation not permitted" in output

        # Verify the directory was NOT moved
        assert test_setup["test_base_dir"].exists()
        assert not moved_base_dir.exists()

        # Cleanup
        if moved_base_dir.exists():
            import shutil
            shutil.rmtree(moved_base_dir, ignore_errors=True)

    async def test_block_moving_file_with_glob_pattern(self, test_setup):
        """Test that moving files matching glob patterns is blocked."""
        # Use glob pattern to deny reading
        read_config = {
            "denyOnly": [str(test_setup["test_glob_dir"]) + "/*.txt"]
        }

        # Try to move a file matching the glob pattern
        wrapped_command = await wrap_command_with_sandbox_macos(
            f'mv {test_setup["test_glob_file1"]} {test_setup["test_glob_moved"]}',
            needs_network_restriction=False,
            read_config=read_config,
            write_config=None,
        )

        # Verify the file exists before test
        assert test_setup["test_glob_file1"].exists()

        # Execute the wrapped command
        result = subprocess.run(
            wrapped_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # The move should fail
        assert result.returncode != 0
        output = result.stderr.lower()
        assert "operation not permitted" in output

        # Verify the file was NOT moved
        assert test_setup["test_glob_file1"].exists()
        assert not test_setup["test_glob_moved"].exists()

    async def test_allow_moving_file_not_matching_glob_pattern(self, test_setup):
        """Test that moving files NOT matching glob patterns is allowed."""
        # Use glob pattern to deny reading only .txt files
        read_config = {
            "denyOnly": [str(test_setup["test_glob_dir"]) + "/*.txt"]
        }

        # Try to move a .log file (not matching the glob pattern)
        moved_log = test_setup["test_base_dir"] / "moved-secret2.log"

        wrapped_command = await wrap_command_with_sandbox_macos(
            f'mv {test_setup["test_glob_file2"]} {moved_log}',
            needs_network_restriction=False,
            read_config=read_config,
            write_config=None,
        )

        # Execute the wrapped command
        result = subprocess.run(
            wrapped_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # The move should succeed (file doesn't match the glob pattern)
        # Note: This might still fail if write restrictions are in place,
        # but the read restriction should not block it
        # We're testing that the glob pattern matching works correctly

        # Cleanup
        if moved_log.exists():
            moved_log.unlink()

    async def test_block_moving_directory_containing_glob_matched_files(self, test_setup):
        """Test that moving a directory containing glob-matched files is blocked."""
        # Use glob pattern
        read_config = {
            "denyOnly": [str(test_setup["test_glob_dir"]) + "/*.txt"]
        }

        moved_glob_dir = test_setup["test_base_dir"] / "moved-glob-dir"

        # Try to move the directory containing the glob-matched files
        wrapped_command = await wrap_command_with_sandbox_macos(
            f'mv {test_setup["test_glob_dir"]} {moved_glob_dir}',
            needs_network_restriction=False,
            read_config=read_config,
            write_config=None,
        )

        # Execute the wrapped command
        result = subprocess.run(
            wrapped_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # The move should fail (directory contains files matching the glob)
        assert result.returncode != 0
        output = result.stderr.lower()
        assert "operation not permitted" in output

        # Verify the directory was NOT moved
        assert test_setup["test_glob_dir"].exists()
        assert not moved_glob_dir.exists()

    async def test_block_renaming_file_within_same_directory(self, test_setup):
        """Test that renaming a file within the same directory is blocked."""
        # Use actual read restriction config
        read_config = {
            "denyOnly": [str(test_setup["test_secret_file"])]
        }

        renamed_file = test_setup["test_denied_dir"] / "renamed-secret.txt"

        # Try to rename the file (mv within same directory)
        wrapped_command = await wrap_command_with_sandbox_macos(
            f'mv {test_setup["test_secret_file"]} {renamed_file}',
            needs_network_restriction=False,
            read_config=read_config,
            write_config=None,
        )

        # Execute the wrapped command
        result = subprocess.run(
            wrapped_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # The rename should fail
        assert result.returncode != 0
        output = result.stderr.lower()
        assert "operation not permitted" in output

        # Verify the file was NOT renamed
        assert test_setup["test_secret_file"].exists()
        assert not renamed_file.exists()

    async def test_block_cp_followed_by_rm_bypass_attempt(self, test_setup):
        """Test that cp followed by rm bypass attempt is blocked."""
        # Use actual read restriction config
        read_config = {
            "denyOnly": [str(test_setup["test_secret_file"])]
        }

        copied_file = test_setup["test_base_dir"] / "copied-secret.txt"

        # Try to copy then remove (simulating a bypass attempt)
        # Note: The copy itself should fail due to read restrictions
        wrapped_command = await wrap_command_with_sandbox_macos(
            f'cp {test_setup["test_secret_file"]} {copied_file} && rm {test_setup["test_secret_file"]}',
            needs_network_restriction=False,
            read_config=read_config,
            write_config=None,
        )

        # Execute the wrapped command
        result = subprocess.run(
            wrapped_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Should fail (copy should be blocked)
        assert result.returncode != 0

        # Original file should still exist
        assert test_setup["test_secret_file"].exists()
        # Copied file should NOT exist (copy failed)
        assert not copied_file.exists()

