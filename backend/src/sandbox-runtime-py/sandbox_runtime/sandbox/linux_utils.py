"""Linux sandbox wrapper using bubblewrap (bwrap) for containerization."""

import shlex
import subprocess
from pathlib import Path
from typing import Optional

from sandbox_runtime.config.schemas import RipgrepConfig
from sandbox_runtime.sandbox.seccomp import (
    generate_seccomp_filter,
    get_apply_seccomp_binary_path,
)
from sandbox_runtime.sandbox.utils import (
    generate_proxy_env_vars,
    get_mandatory_deny_within_allow,
    normalize_path_for_sandbox,
)
from sandbox_runtime.utils.debug import log_for_debugging

# Type aliases for internal configs
FsReadRestrictionConfig = dict[str, list[str]]
FsWriteRestrictionConfig = dict[str, list[str]]


def has_linux_sandbox_dependencies_sync(
    allow_all_unix_sockets: bool = False,
) -> bool:
    """Check if Linux sandbox dependencies are available (synchronous).

    Returns True if bwrap and socat are installed.
    """
    try:
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

        has_basic_deps = (
            bwrap_result.returncode == 0 and socat_result.returncode == 0
        )

        # Check for seccomp dependencies (optional security feature)
        if not allow_all_unix_sockets:
            # Check if we have a pre-generated BPF filter for this architecture
            from sandbox_runtime.sandbox.seccomp import get_pre_generated_bpf_path

            has_pre_generated_bpf = get_pre_generated_bpf_path() is not None

            # Check if we have the apply-seccomp binary for this architecture
            has_apply_seccomp_binary = get_apply_seccomp_binary_path() is not None

            if not has_pre_generated_bpf or not has_apply_seccomp_binary:
                # Seccomp not available - log warning but continue with basic sandbox
                log_for_debugging(
                    "[Sandbox Linux] Seccomp filtering not available (missing binaries). "
                    "Sandbox will run without Unix socket blocking (allowAllUnixSockets mode). "
                    "This is less restrictive but still provides filesystem and network isolation.",
                    {"level": "warn"},
                )

        return has_basic_deps
    except Exception:
        return False


def _build_sandbox_command(
    http_socket_path: str,
    socks_socket_path: str,
    user_command: str,
    seccomp_filter_path: Optional[str],
    shell: str,
) -> str:
    """Build the command that runs inside the sandbox.

    Sets up HTTP proxy on port 3128 and SOCKS proxy on port 1080.
    """
    socat_commands = [
        f"socat TCP-LISTEN:3128,fork,reuseaddr UNIX-CONNECT:{http_socket_path} >/dev/null 2>&1 &",
        f"socat TCP-LISTEN:1080,fork,reuseaddr UNIX-CONNECT:{socks_socket_path} >/dev/null 2>&1 &",
        'trap "kill %1 %2 2>/dev/null; exit" EXIT',
    ]

    # If seccomp filter is provided, use apply-seccomp to apply it
    if seccomp_filter_path:
        apply_seccomp_binary = get_apply_seccomp_binary_path()
        if not apply_seccomp_binary:
            raise RuntimeError(
                "apply-seccomp binary not found. This should have been caught earlier. "
                "Ensure vendor/seccomp/{x64,arm64}/apply-seccomp binaries are included in the package."
            )

        apply_seccomp_cmd = " ".join(
            shlex.quote(part)
            for part in [
                apply_seccomp_binary,
                seccomp_filter_path,
                shell,
                "-c",
                user_command,
            ]
        )

        inner_script = "\n".join([*socat_commands, apply_seccomp_cmd])
        return f"{shell} -c {shlex.quote(inner_script)}"
    else:
        # No seccomp filter - run user command directly
        inner_script = "\n".join([*socat_commands, f"eval {shlex.quote(user_command)}"])
        return f"{shell} -c {shlex.quote(inner_script)}"


async def _generate_filesystem_args(
    read_config: Optional[FsReadRestrictionConfig],
    write_config: Optional[FsWriteRestrictionConfig],
    ripgrep_config: Optional[RipgrepConfig] = None,
) -> list[str]:
    """Generate filesystem bind mount arguments for bwrap."""
    args = []

    # Determine initial root mount based on write restrictions
    if write_config:
        # Write restrictions: Start with read-only root, then allow writes to specific paths
        args.extend(["--ro-bind", "/", "/"])

        # Collect normalized allowed write paths for later checking
        allowed_write_paths = []

        # Allow writes to specific paths
        for path_pattern in write_config.get("allowOnly", []):
            normalized_path = normalize_path_for_sandbox(path_pattern)

            log_for_debugging(
                f"[Sandbox Linux] Processing write path: {path_pattern} -> {normalized_path}"
            )

            # Skip /dev/* paths since --dev /dev already handles them
            if normalized_path.startswith("/dev/"):
                log_for_debugging(
                    f"[Sandbox Linux] Skipping /dev path: {normalized_path}"
                )
                continue

            if not Path(normalized_path).exists():
                log_for_debugging(
                    f"[Sandbox Linux] Skipping non-existent write path: {normalized_path}"
                )
                continue

            args.extend(["--bind", normalized_path, normalized_path])
            allowed_write_paths.append(normalized_path)

        # Deny writes within allowed paths (user-specified + mandatory denies)
        deny_paths = list(write_config.get("denyWithinAllow", []))
        if ripgrep_config:
            mandatory_deny = await get_mandatory_deny_within_allow(ripgrep_config)
            deny_paths.extend(mandatory_deny)

        for path_pattern in deny_paths:
            normalized_path = normalize_path_for_sandbox(path_pattern)

            # Skip /dev/* paths
            if normalized_path.startswith("/dev/"):
                continue

            # Skip non-existent paths
            if not Path(normalized_path).exists():
                log_for_debugging(
                    f"[Sandbox Linux] Skipping non-existent deny path: {normalized_path}"
                )
                continue

            # Only add deny binding if this path is within an allowed write path
            is_within_allowed_path = any(
                normalized_path.startswith(allowed_path + "/")
                or normalized_path == allowed_path
                for allowed_path in allowed_write_paths
            )

            if is_within_allowed_path:
                args.extend(["--ro-bind", normalized_path, normalized_path])
            else:
                log_for_debugging(
                    f"[Sandbox Linux] Skipping deny path not within allowed paths: {normalized_path}"
                )
    else:
        # No write restrictions: Allow all writes
        args.extend(["--bind", "/", "/"])

    # Handle read restrictions by mounting tmpfs over denied paths
    read_deny_paths = list(read_config.get("denyOnly", []) if read_config else [])

    # Always hide /etc/ssh/ssh_config.d to avoid permission issues with OrbStack
    if Path("/etc/ssh/ssh_config.d").exists():
        read_deny_paths.append("/etc/ssh/ssh_config.d")

    for path_pattern in read_deny_paths:
        normalized_path = normalize_path_for_sandbox(path_pattern)
        if not Path(normalized_path).exists():
            log_for_debugging(
                f"[Sandbox Linux] Skipping non-existent read deny path: {normalized_path}"
            )
            continue

        path_obj = Path(normalized_path)
        if path_obj.is_dir():
            args.extend(["--tmpfs", normalized_path])
        else:
            # For files, bind /dev/null instead of tmpfs
            args.extend(["--ro-bind", "/dev/null", normalized_path])

    return args


def wrap_command_with_sandbox_linux(
    command: str,
    needs_network_restriction: bool,
    http_socket_path: Optional[str] = None,
    socks_socket_path: Optional[str] = None,
    http_proxy_port: Optional[int] = None,
    socks_proxy_port: Optional[int] = None,
    read_config: Optional[FsReadRestrictionConfig] = None,
    write_config: Optional[FsWriteRestrictionConfig] = None,
    enable_weaker_nested_sandbox: Optional[bool] = None,
    allow_all_unix_sockets: Optional[bool] = None,
    bin_shell: Optional[str] = None,
    ripgrep_config: Optional[RipgrepConfig] = None,
) -> str:
    """Wrap a command with sandbox restrictions on Linux.

    This uses bubblewrap (bwrap) for containerization with network namespace isolation.
    """
    # Determine if we have restrictions to apply
    has_read_restrictions = read_config and len(read_config.get("denyOnly", [])) > 0
    has_write_restrictions = write_config is not None

    # Check if we need any sandboxing
    if (
        not needs_network_restriction
        and not has_read_restrictions
        and not has_write_restrictions
    ):
        return command

    bwrap_args = []
    seccomp_filter_path = None

    try:
        # ========== SECCOMP FILTER (Unix Socket Blocking) ==========
        if not allow_all_unix_sockets:
            seccomp_filter_path = generate_seccomp_filter()
            if not seccomp_filter_path:
                log_for_debugging(
                    "[Sandbox Linux] Seccomp filter not available (missing binaries). "
                    "Continuing without Unix socket blocking - sandbox will still provide "
                    "filesystem and network isolation but Unix sockets will be allowed.",
                    {"level": "warn"},
                )
            else:
                log_for_debugging(
                    "[Sandbox Linux] Generated seccomp BPF filter for Unix socket blocking"
                )
        elif allow_all_unix_sockets:
            log_for_debugging(
                "[Sandbox Linux] Skipping seccomp filter - allowAllUnixSockets is enabled"
            )

        # ========== NETWORK RESTRICTIONS ==========
        if needs_network_restriction:
            # Only sandbox if we have network config and Linux bridges
            if not http_socket_path or not socks_socket_path:
                raise RuntimeError(
                    "Linux network sandboxing was requested but bridge socket paths are not available"
                )

            # Verify socket files still exist before trying to bind them
            if not Path(http_socket_path).exists():
                raise RuntimeError(
                    f"Linux HTTP bridge socket does not exist: {http_socket_path}. "
                    "The bridge process may have died. Try reinitializing the sandbox."
                )
            if not Path(socks_socket_path).exists():
                raise RuntimeError(
                    f"Linux SOCKS bridge socket does not exist: {socks_socket_path}. "
                    "The bridge process may have died. Try reinitializing the sandbox."
                )

            bwrap_args.append("--unshare-net")

            # Bind both sockets into the sandbox
            bwrap_args.extend(["--bind", http_socket_path, http_socket_path])
            bwrap_args.extend(["--bind", socks_socket_path, socks_socket_path])

            # Add proxy environment variables
            proxy_env = generate_proxy_env_vars(3128, 1080)  # Internal ports
            for env_var in proxy_env:
                if "=" in env_var:
                    key, value = env_var.split("=", 1)
                    bwrap_args.extend(["--setenv", key, value])

            # Add host proxy port environment variables for debugging
            if http_proxy_port is not None:
                bwrap_args.extend(
                    [
                        "--setenv",
                        "CLAUDE_CODE_HOST_HTTP_PROXY_PORT",
                        str(http_proxy_port),
                    ]
                )
            if socks_proxy_port is not None:
                bwrap_args.extend(
                    [
                        "--setenv",
                        "CLAUDE_CODE_HOST_SOCKS_PROXY_PORT",
                        str(socks_proxy_port),
                    ]
                )

        # ========== FILESYSTEM RESTRICTIONS ==========
        import asyncio
        import concurrent.futures

        try:
            asyncio.get_running_loop()
            # Event loop is running - we need to run in a thread
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    _generate_filesystem_args(
                        read_config, write_config, ripgrep_config
                    ),
                )
                fs_args = future.result()
        except RuntimeError:
            # No event loop running - create one
            fs_args = asyncio.run(
                _generate_filesystem_args(read_config, write_config, ripgrep_config)
            )

        bwrap_args.extend(fs_args)

        # Always bind /dev
        bwrap_args.extend(["--dev", "/dev"])

        # ========== PID NAMESPACE ISOLATION ==========
        bwrap_args.append("--unshare-pid")
        if not enable_weaker_nested_sandbox:
            # Mount fresh /proc if PID namespace is isolated (secure mode)
            bwrap_args.extend(["--proc", "/proc"])

        # ========== COMMAND ==========
        # Use the user's shell
        shell_name = bin_shell or "bash"
        shell_path_result = subprocess.run(
            ["which", shell_name], capture_output=True, text=True
        )
        if shell_path_result.returncode != 0:
            raise RuntimeError(f"Shell '{shell_name}' not found in PATH")
        shell = shell_path_result.stdout.strip()
        bwrap_args.extend(["--", shell, "-c"])

        # If we have network restrictions, use the network bridge setup
        if needs_network_restriction and http_socket_path and socks_socket_path:
            sandbox_command = _build_sandbox_command(
                http_socket_path,
                socks_socket_path,
                command,
                seccomp_filter_path,
                shell,
            )
            bwrap_args.append(sandbox_command)
        elif seccomp_filter_path:
            # No network restrictions but we have seccomp - use apply-seccomp directly
            apply_seccomp_binary = get_apply_seccomp_binary_path()
            if not apply_seccomp_binary:
                raise RuntimeError(
                    "apply-seccomp binary not found. This should have been caught earlier. "
                    "Ensure vendor/seccomp/{x64,arm64}/apply-seccomp binaries are included in the package."
                )

            apply_seccomp_cmd = " ".join(
                shlex.quote(part)
                for part in [
                    apply_seccomp_binary,
                    seccomp_filter_path,
                    shell,
                    "-c",
                    command,
                ]
            )
            bwrap_args.append(apply_seccomp_cmd)
        else:
            bwrap_args.append(command)

        # Build the outer bwrap command
        wrapped_command = " ".join(
            shlex.quote(part) for part in ["bwrap", *bwrap_args]
        )

        restrictions = []
        if needs_network_restriction:
            restrictions.append("network")
        if has_read_restrictions or has_write_restrictions:
            restrictions.append("filesystem")
        if seccomp_filter_path:
            restrictions.append("seccomp(unix-block)")

        log_for_debugging(
            f"[Sandbox Linux] Wrapped command with bwrap ({', '.join(restrictions)} restrictions)"
        )

        return wrapped_command

    except Exception as error:
        # Re-throw the original error
        raise error

