"""Platform detection utilities."""

import platform
from typing import Literal

Platform = Literal["macos", "linux", "windows", "unknown"]


def get_platform() -> Platform:
    """Detect the current platform."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "linux":
        return "linux"
    elif system == "windows":
        return "windows"
    else:
        return "unknown"

