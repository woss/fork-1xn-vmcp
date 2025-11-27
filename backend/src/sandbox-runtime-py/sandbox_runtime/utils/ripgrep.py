"""Ripgrep integration utilities."""

import asyncio
import subprocess
from typing import Optional

from sandbox_runtime.config.schemas import RipgrepConfig


def has_ripgrep_sync() -> bool:
    """Check if ripgrep (rg) is available synchronously."""
    try:
        result = subprocess.run(
            ["which", "rg"],
            capture_output=True,
            timeout=1,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


async def rip_grep(
    args: list[str],
    target: str,
    abort_signal: Optional[asyncio.Event] = None,
    config: Optional[RipgrepConfig] = None,
) -> list[str]:
    """Execute ripgrep with the given arguments.

    Args:
        args: Command-line arguments to pass to rg
        target: Target directory or file to search
        abort_signal: Event to signal cancellation
        config: Ripgrep configuration (command and optional args)

    Returns:
        Array of matching lines (one per line of output)

    Raises:
        RuntimeError: If ripgrep exits with non-zero status (except exit code 1)
    """
    if config is None:
        config = RipgrepConfig(command="rg")

    command = [config.command]
    if config.args:
        command.extend(config.args)
    command.extend(args)
    command.append(target)

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Wait for process with timeout
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=10.0
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError("ripgrep timed out after 10 seconds")

        # Check if process was cancelled
        if abort_signal and abort_signal.is_set():
            process.kill()
            await process.wait()
            raise RuntimeError("ripgrep was cancelled")

        # Success case - exit code 0
        if process.returncode == 0:
            output = stdout.decode("utf-8").strip()
            return [line for line in output.split("\n") if line]

        # Exit code 1 means "no matches found" - this is normal, return empty array
        if process.returncode == 1:
            return []

        # All other errors should fail
        error_msg = stderr.decode("utf-8") if stderr else "Unknown error"
        raise RuntimeError(
            f"ripgrep failed with exit code {process.returncode}: {error_msg}"
        )

    except FileNotFoundError:
        raise RuntimeError(
            f"ripgrep command not found: {config.command}"
        ) from None

