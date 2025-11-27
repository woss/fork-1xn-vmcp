"""CLI entrypoint for sandbox runtime."""

import asyncio
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import click

from sandbox_runtime.config.schemas import SandboxRuntimeConfig
from sandbox_runtime.sandbox.manager import SandboxManager
from sandbox_runtime.utils.debug import log_for_debugging

__version__ = "0.0.12"


def load_config(file_path: str) -> SandboxRuntimeConfig | None:
    """Load and validate sandbox configuration from a file."""
    try:
        config_path = Path(file_path)
        if not config_path.exists():
            return None

        content = config_path.read_text(encoding="utf-8")
        if content.strip() == "":
            return None

        # Parse JSON
        parsed = json.loads(content)

        # Convert camelCase to snake_case and validate with Pydantic
        config = SandboxRuntimeConfig.from_json(parsed)
        return config

    except json.JSONDecodeError as error:
        print(f"Invalid JSON in config file {file_path}: {error}", file=sys.stderr)
        return None
    except Exception as error:
        print(f"Failed to load config from {file_path}: {error}", file=sys.stderr)
        return None


def get_default_config_path() -> str:
    """Get default config path."""
    return str(Path.home() / ".srt-settings.json")


def get_default_config() -> SandboxRuntimeConfig:
    """Create a minimal default config if no config file exists."""
    return SandboxRuntimeConfig(
        network={
            "allowed_domains": [],
            "denied_domains": [],
        },
        filesystem={
            "deny_read": [],
            "allow_write": [],
            "deny_write": [],
        },
    )


@click.command()
@click.argument("command", nargs=-1, required=True)
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    help="Enable debug logging",
)
@click.option(
    "-s",
    "--settings",
    type=click.Path(exists=False),
    help="Path to config file (default: ~/.srt-settings.json)",
)
@click.version_option(version=__version__)
@click.pass_context
def main(ctx: click.Context, command: tuple[str, ...], debug: bool, settings: str | None) -> None:
    """Run commands in a sandbox with network and filesystem restrictions."""
    try:
        # Enable debug logging if requested
        if debug:
            os.environ["DEBUG"] = "true"

        # Load config from file
        config_path = settings or get_default_config_path()
        runtime_config = load_config(config_path)

        if not runtime_config:
            log_for_debugging(
                f"No config found at {config_path}, using default config"
            )
            runtime_config = get_default_config()

        # Initialize sandbox with config
        log_for_debugging("Initializing sandbox...")
        asyncio.run(SandboxManager.initialize(runtime_config))

        # Join command arguments into a single command string
        command_str = " ".join(command)
        log_for_debugging(f"Original command: {command_str}")

        log_for_debugging(
            json.dumps(
                SandboxManager.get_network_restriction_config(),
                indent=2,
            )
        )

        # Wrap the command with sandbox restrictions
        sandboxed_command = asyncio.run(
            SandboxManager.wrap_with_sandbox(command_str)
        )

        # Execute the sandboxed command
        print(f"Running: {command_str}")

        # Use subprocess to run the command
        process = subprocess.Popen(
            sandboxed_command,
            shell=True,
            stdout=sys.stdout,
            stderr=sys.stderr,
            stdin=sys.stdin,
        )

        # Handle signals
        def signal_handler(signum, frame):
            """Handle interrupt signals."""
            process.send_signal(signum)
            sys.exit(1)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Wait for process to complete
        exit_code = process.wait()
        sys.exit(exit_code)

    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as error:
        error_msg = str(error) if isinstance(error, Exception) else str(error)
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

