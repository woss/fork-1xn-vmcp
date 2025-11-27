"""Seccomp filter handling for Linux sandboxing."""

import platform
from pathlib import Path
from typing import Optional

from sandbox_runtime.utils.debug import log_for_debugging


def _get_vendor_architecture() -> Optional[str]:
    """Map Python platform.machine() to our vendor directory architecture names.

    Returns None for unsupported architectures.
    """
    arch = platform.machine().lower()
    if arch in ("x64", "x86_64", "amd64"):
        return "x64"
    elif arch in ("arm64", "aarch64"):
        return "arm64"
    elif arch in ("ia32", "i386", "i686", "x86"):
        # 32-bit x86 is not supported (see TypeScript comments)
        log_for_debugging(
            "[SeccompFilter] 32-bit x86 (ia32) is not currently supported due to missing socketcall() syscall blocking.",
            {"level": "error"},
        )
        return None
    else:
        log_for_debugging(
            f"[SeccompFilter] Unsupported architecture: {arch}. Only x64 and arm64 are supported.",
        )
        return None


def get_pre_generated_bpf_path() -> Optional[str]:
    """Get the path to a pre-generated BPF filter file from the vendor directory.

    Returns the path if it exists, None otherwise.

    Pre-generated BPF files are organized by architecture:
    - vendor/seccomp/{x64,arm64}/unix-block.bpf

    Tries multiple paths for resilience:
    1. vendor/seccomp/{arch}/unix-block.bpf (package root)
    2. ../vendor/seccomp/{arch}/unix-block.bpf (relative to module)
    """
    # Determine architecture
    arch = _get_vendor_architecture()
    if not arch:
        log_for_debugging(
            f"[SeccompFilter] Cannot find pre-generated BPF filter: unsupported architecture {platform.machine()}",
        )
        return None

    log_for_debugging(f"[SeccompFilter] Detected architecture: {arch}")

    # Get the package root directory (where vendor/ should be)
    # Try to find it relative to this file
    current_file = Path(__file__).resolve()
    package_root = current_file.parent.parent.parent  # sandbox_runtime/
    project_root = package_root.parent  # sandbox-runtime-py/

    # Try paths in order of preference
    paths_to_try = [
        project_root / "vendor" / "seccomp" / arch / "unix-block.bpf",
        package_root / "vendor" / "seccomp" / arch / "unix-block.bpf",
    ]

    for bpf_path in paths_to_try:
        if bpf_path.exists():
            log_for_debugging(
                f"[SeccompFilter] Found pre-generated BPF filter: {bpf_path} ({arch})",
            )
            return str(bpf_path)

    log_for_debugging(
        f"[SeccompFilter] Pre-generated BPF filter not found in any expected location ({arch})",
    )
    return None


def get_apply_seccomp_binary_path() -> Optional[str]:
    """Get the path to the apply-seccomp binary from the vendor directory.

    Returns the path if it exists, None otherwise.

    Pre-built apply-seccomp binaries are organized by architecture:
    - vendor/seccomp/{x64,arm64}/apply-seccomp

    Tries multiple paths for resilience:
    1. vendor/seccomp/{arch}/apply-seccomp (package root)
    2. ../vendor/seccomp/{arch}/apply-seccomp (relative to module)
    """
    # Determine architecture
    arch = _get_vendor_architecture()
    if not arch:
        log_for_debugging(
            f"[SeccompFilter] Cannot find apply-seccomp binary: unsupported architecture {platform.machine()}",
        )
        return None

    log_for_debugging(
        f"[SeccompFilter] Looking for apply-seccomp binary for architecture: {arch}",
    )

    # Get the package root directory (where vendor/ should be)
    current_file = Path(__file__).resolve()
    package_root = current_file.parent.parent.parent  # sandbox_runtime/
    project_root = package_root.parent  # sandbox-runtime-py/

    # Try paths in order of preference
    paths_to_try = [
        project_root / "vendor" / "seccomp" / arch / "apply-seccomp",
        package_root / "vendor" / "seccomp" / arch / "apply-seccomp",
    ]

    for binary_path in paths_to_try:
        if binary_path.exists():
            log_for_debugging(
                f"[SeccompFilter] Found apply-seccomp binary: {binary_path} ({arch})",
            )
            return str(binary_path)

    log_for_debugging(
        f"[SeccompFilter] apply-seccomp binary not found in any expected location ({arch})",
    )
    return None


def generate_seccomp_filter() -> Optional[str]:
    """Get the path to a pre-generated seccomp BPF filter that blocks Unix domain socket creation.

    Returns the path to the BPF filter file, or None if not available.

    The filter blocks socket(AF_UNIX, ...) syscalls while allowing all other syscalls.
    This prevents creation of new Unix domain socket file descriptors.

    Security scope:
    - Blocks: socket(AF_UNIX, ...) syscall (creating new Unix socket FDs)
    - Does NOT block: Operations on inherited Unix socket FDs (bind, connect, sendto, etc.)
    - Does NOT block: Unix socket FDs passed via SCM_RIGHTS
    - For most sandboxing scenarios, blocking socket creation is sufficient

    Note: This blocks ALL Unix socket creation, regardless of path. The allowUnixSockets
    configuration is not supported on Linux due to seccomp-bpf limitations (it cannot
    read user-space memory to inspect socket paths).

    Requirements:
    - Pre-generated BPF filters included for x64 and ARM64 only
    - Other architectures are not supported

    Returns:
        Path to the pre-generated BPF filter file, or None if not available
    """
    pre_generated_bpf = get_pre_generated_bpf_path()
    if pre_generated_bpf:
        log_for_debugging("[SeccompFilter] Using pre-generated BPF filter")
        return pre_generated_bpf

    log_for_debugging(
        "[SeccompFilter] Pre-generated BPF filter not available for this architecture. "
        "Only x64 and arm64 are supported.",
        {"level": "error"},
    )
    return None


def cleanup_seccomp_filter(_filter_path: str) -> None:
    """Clean up a seccomp filter file.

    Since we only use pre-generated BPF files from vendor/, this is a no-op.
    Pre-generated files are never deleted.
    Kept for backward compatibility with existing code that calls it.
    """
    # No-op: pre-generated BPF files are never cleaned up
    pass

