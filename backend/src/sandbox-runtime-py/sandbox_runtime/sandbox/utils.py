"""Sandbox utility functions for path normalization, glob handling, and default paths."""

import base64
import re
from pathlib import Path
from typing import Optional

from sandbox_runtime.config.schemas import RipgrepConfig
from sandbox_runtime.utils.platform import get_platform
from sandbox_runtime.utils.ripgrep import rip_grep

# Dangerous files that should be protected from writes
DANGEROUS_FILES = [
    ".gitconfig",
    ".gitmodules",
    ".bashrc",
    ".bash_profile",
    ".zshrc",
    ".zprofile",
    ".profile",
    ".ripgreprc",
    ".mcp.json",
]

# Dangerous directories that should be protected from writes
DANGEROUS_DIRECTORIES = [".git", ".vscode", ".idea"]


def normalize_case_for_comparison(path_str: str) -> str:
    """Normalize a path for case-insensitive comparison."""
    return path_str.lower()


def contains_glob_chars(path_pattern: str) -> bool:
    """Check if a path pattern contains glob characters."""
    return bool(
        "*" in path_pattern
        or "?" in path_pattern
        or "[" in path_pattern
        or "]" in path_pattern
    )


def remove_trailing_glob_suffix(path_pattern: str) -> str:
    """Remove trailing /** glob suffix from a path pattern."""
    return re.sub(r"/\*\*$", "", path_pattern)


def normalize_path_for_sandbox(path_pattern: str) -> str:
    """Normalize a path for use in sandbox configurations.

    Handles:
    - Tilde (~) expansion for home directory
    - Relative paths (./foo, ../foo, etc.) converted to absolute
    - Absolute paths remain unchanged
    - Symlinks are resolved to their real paths for non-glob patterns
    - Glob patterns preserve wildcards after path normalization

    Returns the absolute path with symlinks resolved (or normalized glob pattern).
    """
    cwd = Path.cwd()
    normalized_path = path_pattern

    # Expand ~ to home directory
    if path_pattern == "~":
        normalized_path = str(Path.home())
    elif path_pattern.startswith("~/"):
        normalized_path = str(Path.home() / path_pattern[2:])
    elif path_pattern.startswith("./") or path_pattern.startswith("../"):
        # Convert relative to absolute based on current working directory
        normalized_path = str((cwd / path_pattern).resolve())
    elif not Path(path_pattern).is_absolute():
        # Handle other relative paths (e.g., ".", "..", "foo/bar")
        normalized_path = str((cwd / path_pattern).resolve())

    # For glob patterns, resolve symlinks for the directory portion only
    if contains_glob_chars(normalized_path):
        # Extract the static directory prefix before glob characters
        static_prefix = re.split(r"[*?[\]]", normalized_path)[0]
        if static_prefix and static_prefix != "/":
            # Get the directory containing the glob pattern
            # If staticPrefix ends with /, remove it to get the directory
            base_dir = (
                static_prefix[:-1]
                if static_prefix.endswith("/")
                else str(Path(static_prefix).parent)
            )

            # Try to resolve symlinks for the base directory
            try:
                resolved_base_dir = str(Path(base_dir).resolve())
                # Reconstruct the pattern with the resolved directory
                pattern_suffix = normalized_path[len(base_dir) :]
                return resolved_base_dir + pattern_suffix
            except (OSError, ValueError):
                # If directory doesn't exist or can't be resolved, keep the original pattern
                pass
        return normalized_path

    # Resolve symlinks to real paths to avoid bwrap issues
    try:
        normalized_path = str(Path(normalized_path).resolve())
    except (OSError, ValueError):
        # If path doesn't exist or can't be resolved, keep the normalized path
        pass

    return normalized_path


def get_default_write_paths() -> list[str]:
    """Get recommended system paths that should be writable for commands to work properly.

    WARNING: These default paths are intentionally broad for compatibility but may
    allow access to files from other processes. In highly security-sensitive
    environments, you should configure more restrictive write paths.
    """
    home_dir = Path.home()
    recommended_paths = [
        "/dev/stdout",
        "/dev/stderr",
        "/dev/null",
        "/dev/tty",
        "/dev/dtracehelper",
        "/dev/autofs_nowait",
        "/tmp/claude",
        "/private/tmp/claude",
        str(home_dir / ".npm" / "_logs"),
        str(home_dir / ".claude" / "debug"),
    ]

    return recommended_paths


async def get_mandatory_deny_within_allow(
    ripgrep_config: Optional[RipgrepConfig] = None,
) -> list[str]:
    """Get mandatory deny paths within allowed write areas.

    This uses ripgrep to scan the filesystem for dangerous files and directories.
    Returns absolute paths that must be blocked from writes.

    Args:
        ripgrep_config: Ripgrep configuration (command and optional args)

    Returns:
        List of absolute paths that must be denied
    """
    if ripgrep_config is None:
        ripgrep_config = RipgrepConfig(command="rg")

    deny_paths: list[str] = []
    cwd = Path.cwd()
    home_dir = Path.home()

    # Always deny writes to settings.json files
    # Block in home directory
    deny_paths.append(str(home_dir / ".claude" / "settings.json"))
    # Block in current directory
    deny_paths.append(str(cwd / ".claude" / "settings.json"))
    deny_paths.append(str(cwd / ".claude" / "settings.local.json"))

    # Use shared constants for dangerous files
    dangerous_files = DANGEROUS_FILES.copy()

    # Use shared constants plus additional Claude-specific directories
    # Note: We don't include .git as a whole directory since we need it to be writable for git operations
    # Instead, we'll block specific dangerous paths within .git (hooks and config) below
    dangerous_directories = [
        d for d in DANGEROUS_DIRECTORIES if d != ".git"
    ] + [".claude/commands", ".claude/agents"]

    # Add absolute paths for dangerous files in CWD
    for file_name in dangerous_files:
        # Always include the potential path in CWD (even if file doesn't exist yet)
        cwd_file_path = str(cwd / file_name)
        deny_paths.append(cwd_file_path)

        # Find all existing instances of this file in CWD and subdirectories using ripgrep
        try:
            # Use ripgrep to find files with exact name match (case-insensitive)
            matches = await rip_grep(
                [
                    "--files",
                    "--hidden",
                    "--iglob",
                    file_name,
                    "-g",
                    "!**/node_modules/**",
                ],
                str(cwd),
                None,  # abort_signal
                ripgrep_config,
            )
            # Convert relative paths to absolute paths
            absolute_matches = [str(cwd / match) for match in matches]
            deny_paths.extend(absolute_matches)
        except Exception as error:
            # If ripgrep fails, we cannot safely determine all dangerous files
            raise RuntimeError(
                f'Failed to scan for dangerous file "{file_name}": {error}'
            ) from error

    # Add absolute paths for dangerous directories in CWD
    for dir_name in dangerous_directories:
        # Always include the potential path in CWD (even if directory doesn't exist yet)
        cwd_dir_path = str(cwd / dir_name)
        deny_paths.append(cwd_dir_path)

        # Find all existing instances of this directory in CWD and subdirectories using ripgrep
        try:
            # Use ripgrep to find directories (case-insensitive)
            pattern = f"**/{dir_name}/**"
            matches = await rip_grep(
                [
                    "--files",
                    "--hidden",
                    "--iglob",
                    pattern,
                    "-g",
                    "!**/node_modules/**",
                ],
                str(cwd),
                None,  # abort_signal
                ripgrep_config,
            )

            # Extract directory paths from file paths
            dir_paths = set()
            for match in matches:
                absolute_path = str(cwd / match)
                # Find the dangerous directory in the path (case-insensitive)
                segments = Path(absolute_path).parts
                normalized_dir_name = normalize_case_for_comparison(dir_name)
                # Find the directory using case-insensitive comparison
                dir_index = next(
                    (
                        i
                        for i, segment in enumerate(segments)
                        if normalize_case_for_comparison(segment) == normalized_dir_name
                    ),
                    -1,
                )
                if dir_index != -1:
                    # Reconstruct path up to and including the dangerous directory
                    dir_path = str(Path(*segments[: dir_index + 1]))
                    dir_paths.add(dir_path)
            deny_paths.extend(dir_paths)
        except Exception as error:
            # If ripgrep fails, we cannot safely determine all dangerous directories
            raise RuntimeError(
                f'Failed to scan for dangerous directory "{dir_name}": {error}'
            ) from error

    # Special handling for dangerous .git paths
    # We block specific paths within .git that can be used for code execution
    dangerous_git_paths = [
        ".git/hooks",  # Block all hook files to prevent code execution via git hooks
        ".git/config",  # Block config file to prevent dangerous config options
    ]

    for git_path in dangerous_git_paths:
        # Add the path in the current working directory
        absolute_git_path = str(cwd / git_path)
        deny_paths.append(absolute_git_path)

        # Also find .git directories in subdirectories and block their hooks/config
        # This handles nested repositories (case-insensitive)
        try:
            # Find all .git directories by looking for .git/HEAD files (case-insensitive)
            git_head_files = await rip_grep(
                [
                    "--files",
                    "--hidden",
                    "--iglob",
                    "**/.git/HEAD",
                    "-g",
                    "!**/node_modules/**",
                ],
                str(cwd),
                None,  # abort_signal
                ripgrep_config,
            )

            for git_head_file in git_head_files:
                # Get the .git directory path
                git_dir = Path(git_head_file).parent

                # Add the dangerous path within this .git directory
                if git_path == ".git/hooks":
                    hooks_path = str(git_dir / "hooks")
                    deny_paths.append(hooks_path)
                elif git_path == ".git/config":
                    config_path = str(git_dir / "config")
                    deny_paths.append(config_path)
        except Exception as error:
            # If ripgrep fails, we cannot safely determine all .git repositories
            raise RuntimeError(
                f"Failed to scan for .git directories: {error}"
            ) from error

    # Remove duplicates and return
    return list(set(deny_paths))


def generate_proxy_env_vars(
    http_proxy_port: Optional[int] = None,
    socks_proxy_port: Optional[int] = None,
) -> list[str]:
    """Generate proxy environment variables for sandboxed processes."""
    env_vars = ["SANDBOX_RUNTIME=1", "TMPDIR=/tmp/claude"]

    # If no proxy ports provided, return minimal env vars
    if not http_proxy_port and not socks_proxy_port:
        return env_vars

    # Always set NO_PROXY to exclude localhost and private networks from proxying
    no_proxy_addresses = ",".join(
        [
            "localhost",
            "127.0.0.1",
            "::1",
            "*.local",
            ".local",
            "169.254.0.0/16",  # Link-local
            "10.0.0.0/8",  # Private network
            "172.16.0.0/12",  # Private network
            "192.168.0.0/16",  # Private network
        ]
    )
    env_vars.extend([f"NO_PROXY={no_proxy_addresses}", f"no_proxy={no_proxy_addresses}"])

    if http_proxy_port:
        env_vars.extend(
            [
                f"HTTP_PROXY=http://localhost:{http_proxy_port}",
                f"HTTPS_PROXY=http://localhost:{http_proxy_port}",
                f"http_proxy=http://localhost:{http_proxy_port}",
                f"https_proxy=http://localhost:{http_proxy_port}",
            ]
        )

    if socks_proxy_port:
        # Use socks5h:// for proper DNS resolution through proxy
        env_vars.extend(
            [
                f"ALL_PROXY=socks5h://localhost:{socks_proxy_port}",
                f"all_proxy=socks5h://localhost:{socks_proxy_port}",
            ]
        )

        # Configure Git to use SSH through SOCKS proxy (platform-aware)
        if get_platform() == "macos":
            # macOS has nc available
            env_vars.append(
                f'GIT_SSH_COMMAND="ssh -o ProxyCommand=\'nc -X 5 -x localhost:{socks_proxy_port} %h %p\'"'
            )

        # FTP proxy support
        env_vars.extend(
            [
                f"FTP_PROXY=socks5h://localhost:{socks_proxy_port}",
                f"ftp_proxy=socks5h://localhost:{socks_proxy_port}",
            ]
        )

        # rsync proxy support
        env_vars.append(f"RSYNC_PROXY=localhost:{socks_proxy_port}")

        # Docker CLI uses HTTP for the API
        env_vars.extend(
            [
                f"DOCKER_HTTP_PROXY=http://localhost:{http_proxy_port or socks_proxy_port}",
                f"DOCKER_HTTPS_PROXY=http://localhost:{http_proxy_port or socks_proxy_port}",
            ]
        )

        # Google Cloud SDK
        if http_proxy_port:
            env_vars.extend(
                [
                    "CLOUDSDK_PROXY_TYPE=https",
                    "CLOUDSDK_PROXY_ADDRESS=localhost",
                    f"CLOUDSDK_PROXY_PORT={http_proxy_port}",
                ]
            )

        # gRPC-based tools
        env_vars.extend(
            [
                f"GRPC_PROXY=socks5h://localhost:{socks_proxy_port}",
                f"grpc_proxy=socks5h://localhost:{socks_proxy_port}",
            ]
        )

    return env_vars


def encode_sandboxed_command(command: str) -> str:
    """Encode a command for sandbox monitoring.

    Truncates to 100 chars and base64 encodes to avoid parsing issues.
    """
    truncated_command = command[:100]
    return base64.b64encode(truncated_command.encode("utf-8")).decode("ascii")


def decode_sandboxed_command(encoded_command: str) -> str:
    """Decode a base64-encoded command from sandbox monitoring."""
    return base64.b64decode(encoded_command.encode("ascii")).decode("utf-8")

