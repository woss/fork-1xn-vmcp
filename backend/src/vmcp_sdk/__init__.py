"""
vMCP SDK - Lightweight Python SDK for Virtual MCP Servers

This SDK provides a simple, Pythonic interface to interact with vMCPs.
It wraps the existing vmcp library with a clean API and typed functions.

Example:
    >>> import vmcp_sdk as vmcp
    >>>
    >>> # List all available vMCPs
    >>> vmcps = vmcp.list_mcps()
    >>>
    >>> # Access a specific vMCP - tools are typed functions!
    >>> linear = vmcp.linear
    >>> tools = linear.list_tools()
    >>> result = linear.search_issues(query="bug")  # Typed function!
"""

import asyncio
import importlib.util
import sys
from typing import Any, Dict, List, Union

from .active_vmcp import ActiveVMCPManager
from .client import VMCPClient

# Global active vmcp manager
_active_vmcp_manager = ActiveVMCPManager()

# Cache for vmcp clients
_vmcp_clients: Dict[str, VMCPClient] = {}


def list_mcps() -> List[Dict[str, Any]]:
    """
    List all available vMCPs.

    Returns:
        List of vMCP dictionaries with name, id, description, etc.
    """
    client = VMCPClient()
    return asyncio.run(client.list_vmcps())


def _get_vmcp_client(vmcp_name: str) -> VMCPClient:
    """Get or create a VMCPClient for a specific vmcp."""
    if vmcp_name not in _vmcp_clients:
        _vmcp_clients[vmcp_name] = VMCPClient(vmcp_name=vmcp_name)
    return _vmcp_clients[vmcp_name]


class VMCPProxy:
    """
    Dynamic proxy for accessing vMCPs by name.

    This allows syntax like: vmcp.linear.search_issues(query="bug")
    Tools are exposed as typed Python functions.
    """

    def __init__(self, vmcp_name: str):
        self._vmcp_name = vmcp_name
        self._client = _get_vmcp_client(vmcp_name)
        # Pre-load tools to create typed functions
        asyncio.run(self._client._load_tools())

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all tools available in this vMCP."""
        return asyncio.run(self._client.list_tools())

    def list_prompts(self) -> List[Dict[str, Any]]:
        """List all prompts available in this vMCP."""
        return asyncio.run(self._client.list_prompts())

    def list_resources(self) -> List[Dict[str, Any]]:
        """List all resources available in this vMCP."""
        return asyncio.run(self._client.list_resources())

    def __getattr__(self, name: str):
        """Dynamically access tool functions."""
        # Delegate to client which has the typed functions
        return getattr(self._client, name)

    def __repr__(self):
        return f"<VMCPProxy(vmcp_name='{self._vmcp_name}')>"


# Get the current module
_module = sys.modules[__name__]

# Store original __getattr__ if it exists
_original_getattr = getattr(_module, '__getattr__', None)


def _module_getattr(name: str) -> Union[VMCPProxy, Any]:
    """Custom __getattr__ for the module that handles both submodules and dynamic vMCP access."""
    # First, try to get the attribute from the module's __dict__ directly (for submodules, etc.)
    # Use __dict__ to avoid recursion with hasattr/getattr
    if name in _module.__dict__:
        return _module.__dict__[name]

    # Check if it's a known submodule by trying to import it
    # This handles cases like vmcp_sdk.cli
    try:
        submodule_name = f"{__name__}.{name}"
        # Check if the submodule exists by trying to find it
        spec = importlib.util.find_spec(submodule_name)
        if spec is not None and spec.loader is not None:
            # It's a submodule, let Python handle it normally
            raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
    except (ImportError, ValueError, AttributeError):
        pass

    # Ignore Python's special attributes (__path__, __file__, etc.)
    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

    # Check if it's a method call
    if name == "list_mcps":
        return list_mcps

    # Otherwise, treat as vmcp name
    return VMCPProxy(name)


# Set the custom __getattr__ on the module
_module.__getattr__ = _module_getattr  # type: ignore

# Expose main functions and classes
__all__ = ["list_mcps", "VMCPClient", "VMCPProxy", "ActiveVMCPManager"]
