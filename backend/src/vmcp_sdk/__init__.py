"""
vMCP SDK - Lightweight Python SDK for Virtual MCP Servers

This SDK provides a simple, Pythonic interface to interact with vMCPs.
It automatically detects the vMCP from the sandbox config file.

Example:
    >>> import vmcp_sdk
    >>>
    >>> # SDK automatically uses the vMCP for the current sandbox
    >>> tools = vmcp_sdk.list_tools()
    >>> prompts = vmcp_sdk.list_prompts()
    >>> result = vmcp_sdk.some_tool_function(arg1="value")  # Typed function!
"""

import asyncio
import importlib.util
import sys
from typing import Any, Dict, List, Union

from .active_vmcp import ActiveVMCPManager
from .client import VMCPClient

# Global client instance (auto-detects vmcp_id from sandbox)
_client: VMCPClient = None


def _get_client() -> VMCPClient:
    """Get or create the global VMCPClient instance."""
    global _client
    if _client is None:
        _client = VMCPClient()  # Auto-detects vmcp_id from sandbox
    return _client


def list_tools() -> List[Dict[str, Any]]:
    """
    List all tools available in the current vMCP.

    Returns:
        List of tool dictionaries
    """
    client = _get_client()
    return asyncio.run(client.list_tools())


def list_prompts() -> List[Dict[str, Any]]:
    """
    List all prompts available in the current vMCP.

    Returns:
        List of prompt dictionaries
    """
    client = _get_client()
    return asyncio.run(client.list_prompts())


def list_resources() -> List[Dict[str, Any]]:
    """
    List all resources available in the current vMCP.

    Returns:
        List of resource dictionaries
    """
    client = _get_client()
    return asyncio.run(client.list_resources())


# Get the current module
_module = sys.modules[__name__]

# Store original __getattr__ if it exists
_original_getattr = getattr(_module, '__getattr__', None)


def _module_getattr(name: str) -> Any:
    """Custom __getattr__ for the module that handles tool functions."""
    # First, try to get the attribute from the module's __dict__ directly (for submodules, etc.)
    if name in _module.__dict__:
        return _module.__dict__[name]

    # Check if it's a known submodule by trying to import it
    try:
        submodule_name = f"{__name__}.{name}"
        spec = importlib.util.find_spec(submodule_name)
        if spec is not None and spec.loader is not None:
            raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
    except (ImportError, ValueError, AttributeError):
        pass

    # Ignore Python's special attributes
    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

    # Check if it's a module function
    if name in ["list_tools", "list_prompts", "list_resources"]:
        return getattr(_module, name)

    # Otherwise, treat as tool function - delegate to client
    client = _get_client()
    asyncio.run(client._load_tools())
    return getattr(client, name)


# Set the custom __getattr__ on the module
_module.__getattr__ = _module_getattr  # type: ignore

# Expose main functions and classes
__all__ = ["list_tools", "list_prompts", "list_resources", "VMCPClient", "ActiveVMCPManager"]
