"""macOS sandbox wrapper using sandbox-exec with Seatbelt profiles."""

import json
import os
import random
import re
import shlex
import subprocess
from pathlib import Path
from typing import Callable, Optional

from sandbox_runtime.config.schemas import RipgrepConfig
from sandbox_runtime.sandbox.utils import (
    contains_glob_chars,
    decode_sandboxed_command,
    encode_sandboxed_command,
    generate_proxy_env_vars,
    get_mandatory_deny_within_allow,
    normalize_path_for_sandbox,
)
from sandbox_runtime.sandbox.violation_store import SandboxViolationEvent
from sandbox_runtime.utils.debug import log_for_debugging

# Type aliases for internal configs
FsReadRestrictionConfig = dict[str, list[str]]
FsWriteRestrictionConfig = dict[str, list[str]]

SESSION_SUFFIX = f"_{random.randbytes(9).hex()}_SBX"


def glob_to_regex(glob_pattern: str) -> str:
    """Convert a glob pattern to a regular expression for macOS sandbox profiles.

    This implements gitignore-style pattern matching.

    Supported patterns:
    - * matches any characters except / (e.g., *.ts matches foo.ts but not foo/bar.ts)
    - ** matches any characters including / (e.g., src/**/*.ts matches all .ts files in src/)
    - ? matches any single character except / (e.g., file?.txt matches file1.txt)
    - [abc] matches any character in the set (e.g., file[0-9].txt matches file3.txt)
    """
    pattern = glob_pattern
    # Escape regex special characters (except glob chars * ? [ ])
    pattern = re.sub(r"[.^$+{}()|\\]", r"\\\g<0>", pattern)
    # Escape unclosed brackets (no matching ])
    pattern = re.sub(r"\[([^\]]*?)$", r"\\[\1", pattern)
    # Convert glob patterns to regex (order matters - ** before *)
    pattern = pattern.replace("**/", "__GLOBSTAR_SLASH__")
    pattern = pattern.replace("**", "__GLOBSTAR__")
    pattern = pattern.replace("*", "[^/]*")
    pattern = pattern.replace("?", "[^/]")
    # Restore placeholders
    pattern = pattern.replace("__GLOBSTAR_SLASH__", "(.*/)?")
    pattern = pattern.replace("__GLOBSTAR__", ".*")
    return "^" + pattern + "$"


def generate_log_tag(command: str) -> str:
    """Generate a unique log tag for sandbox monitoring."""
    encoded_command = encode_sandboxed_command(command)
    return f"CMD64_{encoded_command}_END_{SESSION_SUFFIX}"


def get_ancestor_directories(path_str: str) -> list[str]:
    """Get all ancestor directories for a path, up to (but not including) root."""
    ancestors = []
    current_path = Path(path_str).parent

    # Walk up the directory tree until we reach root
    while str(current_path) != "/" and str(current_path) != ".":
        ancestors.append(str(current_path))
        parent_path = current_path.parent
        # Break if we've reached the top
        if parent_path == current_path:
            break
        current_path = parent_path

    return ancestors


def generate_move_blocking_rules(
    path_patterns: list[str], log_tag: str
) -> list[str]:
    """Generate deny rules for file movement (file-write-unlink) to protect paths."""
    rules = []

    for path_pattern in path_patterns:
        normalized_path = normalize_path_for_sandbox(path_pattern)

        if contains_glob_chars(normalized_path):
            # Use regex matching for glob patterns
            regex_pattern = glob_to_regex(normalized_path)

            # Block moving/renaming files matching this pattern
            rules.append(
                f'(deny file-write-unlink\n'
                f'  (regex {escape_path(regex_pattern)})\n'
                f'  (with message "{log_tag}"))'
            )

            # For glob patterns, extract the static prefix and block ancestor moves
            static_prefix = re.split(r"[*?[\]]", normalized_path)[0]
            if static_prefix and static_prefix != "/":
                # Get the directory containing the glob pattern
                base_dir = (
                    static_prefix[:-1]
                    if static_prefix.endswith("/")
                    else str(Path(static_prefix).parent)
                )

                # Block moves of the base directory itself
                rules.append(
                    f'(deny file-write-unlink\n'
                    f'  (literal {escape_path(base_dir)})\n'
                    f'  (with message "{log_tag}"))'
                )

                # Block moves of ancestor directories
                for ancestor_dir in get_ancestor_directories(base_dir):
                    rules.append(
                        f'(deny file-write-unlink\n'
                        f'  (literal {escape_path(ancestor_dir)})\n'
                        f'  (with message "{log_tag}"))'
                    )
        else:
            # Use subpath matching for literal paths
            # Block moving/renaming the denied path itself
            rules.append(
                f'(deny file-write-unlink\n'
                f'  (subpath {escape_path(normalized_path)})\n'
                f'  (with message "{log_tag}"))'
            )

            # Block moves of ancestor directories
            for ancestor_dir in get_ancestor_directories(normalized_path):
                rules.append(
                    f'(deny file-write-unlink\n'
                    f'  (literal {escape_path(ancestor_dir)})\n'
                    f'  (with message "{log_tag}"))'
                )

    return rules


def generate_read_rules(
    config: Optional[FsReadRestrictionConfig], log_tag: str
) -> list[str]:
    """Generate filesystem read rules for sandbox profile."""
    if not config:
        return ["(allow file-read*)"]

    rules = []

    # Start by allowing everything
    rules.append("(allow file-read*)")

    # Then deny specific paths
    for path_pattern in config.get("denyOnly", []):
        normalized_path = normalize_path_for_sandbox(path_pattern)

        if contains_glob_chars(normalized_path):
            # Use regex matching for glob patterns
            regex_pattern = glob_to_regex(normalized_path)
            rules.append(
                f'(deny file-read*\n'
                f'  (regex {escape_path(regex_pattern)})\n'
                f'  (with message "{log_tag}"))'
            )
        else:
            # Use subpath matching for literal paths
            rules.append(
                f'(deny file-read*\n'
                f'  (subpath {escape_path(normalized_path)})\n'
                f'  (with message "{log_tag}"))'
            )

    # Block file movement to prevent bypass via mv/rename
    rules.extend(generate_move_blocking_rules(config.get("denyOnly", []), log_tag))

    return rules


async def generate_write_rules(
    config: Optional[FsWriteRestrictionConfig],
    log_tag: str,
    ripgrep_config: Optional[RipgrepConfig] = None,
) -> list[str]:
    """Generate filesystem write rules for sandbox profile."""
    if not config:
        return ["(allow file-write*)"]

    rules = []

    # Automatically allow TMPDIR parent on macOS when write restrictions are enabled
    tmpdir_parents = get_tmpdir_parent_if_macos_pattern()
    for tmpdir_parent in tmpdir_parents:
        normalized_path = normalize_path_for_sandbox(tmpdir_parent)
        rules.append(
            f'(allow file-write*\n'
            f'  (subpath {escape_path(normalized_path)})\n'
            f'  (with message "{log_tag}"))'
        )

    # Generate allow rules
    for path_pattern in config.get("allowOnly", []):
        normalized_path = normalize_path_for_sandbox(path_pattern)

        if contains_glob_chars(normalized_path):
            # Use regex matching for glob patterns
            regex_pattern = glob_to_regex(normalized_path)
            rules.append(
                f'(allow file-write*\n'
                f'  (regex {escape_path(regex_pattern)})\n'
                f'  (with message "{log_tag}"))'
            )
        else:
            # Use subpath matching for literal paths
            rules.append(
                f'(allow file-write*\n'
                f'  (subpath {escape_path(normalized_path)})\n'
                f'  (with message "{log_tag}"))'
            )

    # Combine user-specified and mandatory deny rules
    deny_paths = list(config.get("denyWithinAllow", []))
    if ripgrep_config:
        mandatory_deny = await get_mandatory_deny_within_allow(ripgrep_config)
        deny_paths.extend(mandatory_deny)

    for path_pattern in deny_paths:
        normalized_path = normalize_path_for_sandbox(path_pattern)

        if contains_glob_chars(normalized_path):
            # Use regex matching for glob patterns
            regex_pattern = glob_to_regex(normalized_path)
            rules.append(
                f'(deny file-write*\n'
                f'  (regex {escape_path(regex_pattern)})\n'
                f'  (with message "{log_tag}"))'
            )
        else:
            # Use subpath matching for literal paths
            rules.append(
                f'(deny file-write*\n'
                f'  (subpath {escape_path(normalized_path)})\n'
                f'  (with message "{log_tag}"))'
            )

    # Block file movement to prevent bypass via mv/rename
    rules.extend(generate_move_blocking_rules(deny_paths, log_tag))

    return rules


def escape_path(path_str: str) -> str:
    """Escape path for sandbox profile using JSON encoding."""
    return json.dumps(path_str)


def get_tmpdir_parent_if_macos_pattern() -> list[str]:
    """Get TMPDIR parent directory if it matches macOS pattern /var/folders/XX/YYY/T/."""
    tmpdir = os.environ.get("TMPDIR")
    if not tmpdir:
        return []

    match = re.match(r"^/(private/)?var/folders/[^/]{2}/[^/]+/T/?$", tmpdir)
    if not match:
        return []

    parent = tmpdir.replace("/T/", "").replace("/T", "")

    # Return both /var/ and /private/var/ versions since /var is a symlink
    if parent.startswith("/private/var/"):
        return [parent, parent.replace("/private", "")]
    elif parent.startswith("/var/"):
        return [parent, "/private" + parent]

    return [parent]


async def generate_sandbox_profile(
    read_config: Optional[FsReadRestrictionConfig],
    write_config: Optional[FsWriteRestrictionConfig],
    http_proxy_port: Optional[int],
    socks_proxy_port: Optional[int],
    needs_network_restriction: bool,
    allow_unix_sockets: Optional[list[str]],
    allow_all_unix_sockets: Optional[bool],
    allow_local_binding: Optional[bool],
    log_tag: str,
    ripgrep_config: Optional[RipgrepConfig] = None,
) -> str:
    """Generate complete sandbox profile."""
    profile = [
        "(version 1)",
        f'(deny default (with message "{log_tag}"))',
        "",
        f"; LogTag: {log_tag}",
        "",
        "; Essential permissions - based on Chrome sandbox policy",
        "; Process permissions",
        "(allow process-exec)",
        "(allow process-fork)",
        "(allow process-info* (target same-sandbox))",
        "(allow signal (target same-sandbox))",
        "(allow mach-priv-task-port (target same-sandbox))",
        "",
        "; User preferences",
        "(allow user-preference-read)",
        "",
        "; Mach IPC - specific services only (no wildcard)",
        "(allow mach-lookup",
        '  (global-name "com.apple.audio.systemsoundserver")',
        '  (global-name "com.apple.distributed_notifications@Uv3")',
        '  (global-name "com.apple.FontObjectsServer")',
        '  (global-name "com.apple.fonts")',
        '  (global-name "com.apple.logd")',
        '  (global-name "com.apple.lsd.mapdb")',
        '  (global-name "com.apple.PowerManagement.control")',
        '  (global-name "com.apple.system.logger")',
        '  (global-name "com.apple.system.notification_center")',
        '  (global-name "com.apple.trustd.agent")',
        '  (global-name "com.apple.system.opendirectoryd.libinfo")',
        '  (global-name "com.apple.system.opendirectoryd.membership")',
        '  (global-name "com.apple.bsd.dirhelper")',
        '  (global-name "com.apple.securityd.xpc")',
        '  (global-name "com.apple.coreservices.launchservicesd")',
        ")",
        "",
        "; POSIX IPC - shared memory",
        "(allow ipc-posix-shm)",
        "",
        "; POSIX IPC - semaphores for Python multiprocessing",
        "(allow ipc-posix-sem)",
        "",
        "; IOKit - specific operations only",
        "(allow iokit-open",
        '  (iokit-registry-entry-class "IOSurfaceRootUserClient")',
        '  (iokit-registry-entry-class "RootDomainUserClient")',
        '  (iokit-user-client-class "IOSurfaceSendRight")',
        ")",
        "",
        "; IOKit properties",
        "(allow iokit-get-properties)",
        "",
        "; Specific safe system-sockets, doesn't allow network access",
        "(allow system-socket (require-all (socket-domain AF_SYSTEM) (socket-protocol 2)))",
        "",
        "; sysctl - specific sysctls only",
        "(allow sysctl-read",
        '  (sysctl-name "hw.activecpu")',
        '  (sysctl-name "hw.busfrequency_compat")',
        '  (sysctl-name "hw.byteorder")',
        '  (sysctl-name "hw.cacheconfig")',
        '  (sysctl-name "hw.cachelinesize_compat")',
        '  (sysctl-name "hw.cpufamily")',
        '  (sysctl-name "hw.cpufrequency")',
        '  (sysctl-name "hw.cpufrequency_compat")',
        '  (sysctl-name "hw.cputype")',
        '  (sysctl-name "hw.l1dcachesize_compat")',
        '  (sysctl-name "hw.l1icachesize_compat")',
        '  (sysctl-name "hw.l2cachesize_compat")',
        '  (sysctl-name "hw.l3cachesize_compat")',
        '  (sysctl-name "hw.logicalcpu")',
        '  (sysctl-name "hw.logicalcpu_max")',
        '  (sysctl-name "hw.machine")',
        '  (sysctl-name "hw.memsize")',
        '  (sysctl-name "hw.ncpu")',
        '  (sysctl-name "hw.nperflevels")',
        '  (sysctl-name "hw.packages")',
        '  (sysctl-name "hw.pagesize_compat")',
        '  (sysctl-name "hw.pagesize")',
        '  (sysctl-name "hw.physicalcpu")',
        '  (sysctl-name "hw.physicalcpu_max")',
        '  (sysctl-name "hw.tbfrequency_compat")',
        '  (sysctl-name "hw.vectorunit")',
        '  (sysctl-name "kern.argmax")',
        '  (sysctl-name "kern.bootargs")',
        '  (sysctl-name "kern.hostname")',
        '  (sysctl-name "kern.maxfiles")',
        '  (sysctl-name "kern.maxfilesperproc")',
        '  (sysctl-name "kern.maxproc")',
        '  (sysctl-name "kern.ngroups")',
        '  (sysctl-name "kern.osproductversion")',
        '  (sysctl-name "kern.osrelease")',
        '  (sysctl-name "kern.ostype")',
        '  (sysctl-name "kern.osvariant_status")',
        '  (sysctl-name "kern.osversion")',
        '  (sysctl-name "kern.secure_kernel")',
        '  (sysctl-name "kern.tcsm_available")',
        '  (sysctl-name "kern.tcsm_enable")',
        '  (sysctl-name "kern.usrstack64")',
        '  (sysctl-name "kern.version")',
        '  (sysctl-name "kern.willshutdown")',
        '  (sysctl-name "machdep.cpu.brand_string")',
        '  (sysctl-name "machdep.ptrauth_enabled")',
        '  (sysctl-name "security.mac.lockdown_mode_state")',
        '  (sysctl-name "sysctl.proc_cputype")',
        '  (sysctl-name "vm.loadavg")',
        '  (sysctl-name-prefix "hw.optional.arm")',
        '  (sysctl-name-prefix "hw.optional.arm.")',
        '  (sysctl-name-prefix "hw.optional.armv8_")',
        '  (sysctl-name-prefix "hw.perflevel")',
        '  (sysctl-name-prefix "kern.proc.pgrp.")',
        '  (sysctl-name-prefix "kern.proc.pid.")',
        '  (sysctl-name-prefix "machdep.cpu.")',
        '  (sysctl-name-prefix "net.routetable.")',
        ")",
        "",
        "; V8 thread calculations",
        "(allow sysctl-write",
        '  (sysctl-name "kern.tcsm_enable")',
        ")",
        "",
        "; Distributed notifications",
        "(allow distributed-notification-post)",
        "",
        "; Specific mach-lookup permissions for security operations",
        '(allow mach-lookup (global-name "com.apple.SecurityServer"))',
        "",
        "; File I/O on device files",
        '(allow file-ioctl (literal "/dev/null"))',
        '(allow file-ioctl (literal "/dev/zero"))',
        '(allow file-ioctl (literal "/dev/random"))',
        '(allow file-ioctl (literal "/dev/urandom"))',
        '(allow file-ioctl (literal "/dev/dtracehelper"))',
        '(allow file-ioctl (literal "/dev/tty"))',
        "",
        "(allow file-ioctl file-read-data file-write-data",
        "  (require-all",
        '    (literal "/dev/null")',
        "    (vnode-type CHARACTER-DEVICE)",
        "  )",
        ")",
        "",
    ]

    # Network rules
    profile.append("; Network")
    if not needs_network_restriction:
        profile.append("(allow network*)")
    else:
        # Allow local binding if requested
        if allow_local_binding:
            profile.append('(allow network-bind (local ip "localhost:*"))')
            profile.append('(allow network-inbound (local ip "localhost:*"))')
            profile.append('(allow network-outbound (local ip "localhost:*"))')
        
        # Allow DNS resolution (critical for network operations)
        profile.append("; DNS Resolution")
        profile.append('(allow network-outbound (literal "/private/var/run/mDNSResponder"))')
        profile.append('(allow network-outbound (remote ip "localhost:53"))')
        profile.append('(allow network-outbound (remote ip "localhost:5353"))')
        
        # Allow system sockets for DNS/mDNS
        profile.append("(allow system-socket)")
        
        # Unix domain sockets for local IPC (SSH agent, Docker, etc.)
        if allow_all_unix_sockets:
            profile.append('(allow network* (subpath "/"))')
        elif allow_unix_sockets and len(allow_unix_sockets) > 0:
            # Allow specific Unix socket paths
            for socket_path in allow_unix_sockets:
                normalized_path = normalize_path_for_sandbox(socket_path)
                profile.append(
                    f"(allow network* (subpath {escape_path(normalized_path)}))"
                )

        # Allow localhost TCP operations for the HTTP proxy
        if http_proxy_port is not None:
            profile.append(
                f'(allow network-bind (local ip "localhost:{http_proxy_port}"))'
            )
            profile.append(
                f'(allow network-inbound (local ip "localhost:{http_proxy_port}"))'
            )
            profile.append(
                f'(allow network-outbound (remote ip "localhost:{http_proxy_port}"))'
            )

        # Allow localhost TCP operations for the SOCKS proxy
        if socks_proxy_port is not None:
            profile.append(
                f'(allow network-bind (local ip "localhost:{socks_proxy_port}"))'
            )
            profile.append(
                f'(allow network-inbound (local ip "localhost:{socks_proxy_port}"))'
            )
            profile.append(
                f'(allow network-outbound (remote ip "localhost:{socks_proxy_port}"))'
            )
    profile.append("")

    # Read rules
    profile.append("; File read")
    profile.extend(generate_read_rules(read_config, log_tag))
    profile.append("")

    # Write rules
    profile.append("; File write")
    write_rules = await generate_write_rules(write_config, log_tag, ripgrep_config)
    profile.extend(write_rules)

    return "\n".join(profile)


async def wrap_command_with_sandbox_macos(
    command: str,
    needs_network_restriction: bool,
    http_proxy_port: Optional[int] = None,
    socks_proxy_port: Optional[int] = None,
    allow_unix_sockets: Optional[list[str]] = None,
    allow_all_unix_sockets: Optional[bool] = None,
    allow_local_binding: Optional[bool] = None,
    read_config: Optional[FsReadRestrictionConfig] = None,
    write_config: Optional[FsWriteRestrictionConfig] = None,
    bin_shell: Optional[str] = None,
    ripgrep_config: Optional[RipgrepConfig] = None,
    sandbox_dir: Optional[str] = None,
) -> str:
    """Wrap command with macOS sandbox."""
    # Determine if we have restrictions to apply
    has_read_restrictions = read_config and len(read_config.get("denyOnly", [])) > 0
    has_write_restrictions = write_config is not None

    # No sandboxing needed
    if (
        not needs_network_restriction
        and not has_read_restrictions
        and not has_write_restrictions
    ):
        return command

    log_tag = generate_log_tag(command)

    profile = await generate_sandbox_profile(
        read_config=read_config,
        write_config=write_config,
        http_proxy_port=http_proxy_port,
        socks_proxy_port=socks_proxy_port,
        needs_network_restriction=needs_network_restriction,
        allow_unix_sockets=allow_unix_sockets,
        allow_all_unix_sockets=allow_all_unix_sockets,
        allow_local_binding=allow_local_binding,
        log_tag=log_tag,
        ripgrep_config=ripgrep_config,
    )

    if sandbox_dir:
        try:
            profile_path = Path(sandbox_dir) / "sandbox_profile.sb"
            # Write profile to file
            with open(profile_path, "w") as f:
                f.write(profile)
            log_for_debugging(f"[Sandbox macOS] Wrote profile to {profile_path}")
        except Exception as e:
            log_for_debugging(f"[Sandbox macOS] Failed to write profile: {e}", {"level": "error"})

    # Generate proxy environment variables
    proxy_env_vars = generate_proxy_env_vars(http_proxy_port, socks_proxy_port)
    proxy_env = " ".join(f"export {var}" for var in proxy_env_vars) + " && "

    # Use the user's shell (zsh, bash, etc.)
    shell_name = bin_shell or "bash"
    shell_path_result = subprocess.run(
        ["which", shell_name], capture_output=True, text=True
    )
    if shell_path_result.returncode != 0:
        raise RuntimeError(f"Shell '{shell_name}' not found in PATH")
    shell = shell_path_result.stdout.strip()

    # Build the wrapped command
    wrapped_command_parts = [
        "sandbox-exec",
        "-p",
        profile,
        shell,
        "-c",
        proxy_env + command,
    ]

    wrapped_command = " ".join(shlex.quote(part) for part in wrapped_command_parts)

    log_for_debugging(
        f"[Sandbox macOS] Applied restrictions - network: {bool(http_proxy_port or socks_proxy_port)}, "
        f"read: {bool(has_read_restrictions)}, write: {bool(has_write_restrictions)}"
    )

    return wrapped_command


def start_macos_sandbox_log_monitor(
    callback: Callable[[SandboxViolationEvent], None],
    ignore_violations: Optional[dict[str, list[str]]] = None,
) -> Callable[[], None]:
    """Start monitoring macOS system logs for sandbox violations."""
    # Pre-compile regex patterns for better performance
    cmd_extract_regex = re.compile(r"CMD64_(.+?)_END")
    sandbox_extract_regex = re.compile(r"Sandbox:\s+(.+)$")

    # Pre-process ignore patterns for faster lookup
    wildcard_paths = ignore_violations.get("*", []) if ignore_violations else []
    command_patterns = (
        [
            (pattern, paths)
            for pattern, paths in ignore_violations.items()
            if pattern != "*"
        ]
        if ignore_violations
        else []
    )

    # Stream and filter kernel logs for all sandbox violations
    log_process = subprocess.Popen(
        [
            "log",
            "stream",
            "--predicate",
            f'(eventMessage ENDSWITH "{SESSION_SUFFIX}")',
            "--style",
            "compact",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    def process_output():
        """Process log output line by line."""
        if not log_process.stdout:
            return

        violation_line = None
        command_line = None

        for line in log_process.stdout:
            if "Sandbox:" in line and "deny" in line:
                violation_line = line
            if line.startswith("CMD64_"):
                command_line = line

            if violation_line:
                # Extract violation details
                sandbox_match = sandbox_extract_regex.search(violation_line)
                if not sandbox_match:
                    continue

                violation_details = sandbox_match.group(1)

                # Try to get command
                command = None
                encoded_command = None
                if command_line:
                    cmd_match = cmd_extract_regex.search(command_line)
                    if cmd_match:
                        encoded_command = cmd_match.group(1)
                        try:
                            command = decode_sandboxed_command(encoded_command)
                        except Exception:
                            pass

                # Always filter out noisy violations
                if any(
                    noise in violation_details
                    for noise in [
                        "mDNSResponder",
                        "mach-lookup com.apple.diagnosticd",
                        "mach-lookup com.apple.analyticsd",
                    ]
                ):
                    continue

                # Check if we should ignore this violation
                if ignore_violations and command:
                    # Check wildcard patterns first
                    if wildcard_paths:
                        if any(path in violation_details for path in wildcard_paths):
                            continue

                    # Check command-specific patterns
                    for pattern, paths in command_patterns:
                        if pattern in command:
                            if any(path in violation_details for path in paths):
                                continue

                # Not ignored - report the violation
                callback(
                    SandboxViolationEvent(
                        line=violation_details,
                        command=command,
                        encoded_command=encoded_command,
                    )
                )

                violation_line = None
                command_line = None

    # Start processing in background
    import threading

    thread = threading.Thread(target=process_output, daemon=True)
    thread.start()

    def shutdown():
        """Stop the log monitor."""
        log_for_debugging("[Sandbox Monitor] Stopping log monitor")
        log_process.terminate()
        log_process.wait()

    return shutdown

