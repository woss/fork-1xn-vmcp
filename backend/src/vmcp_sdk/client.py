"""
Core vMCP client for interacting with vMCPs.

This is a thin wrapper around the existing VMCPConfigManager that creates
typed Python functions from tool schemas.
"""

import asyncio
from typing import Any, Dict, List, Optional

from vmcp.storage.dummy_user import UserContext
from vmcp.vmcps.vmcp_config_manager.config_core import VMCPConfigManager
from vmcp.vmcps.models import VMCPToolCallRequest

from .schema import create_function_with_signature, normalize_name


class VMCPClient:
    """
    Client for interacting with vMCPs.
    
    This is a thin wrapper around VMCPConfigManager that provides
    typed Python functions for each tool.
    """
    
    def __init__(self, vmcp_name: Optional[str] = None, user_id: int = 1):
        """
        Initialize the vMCP client.
        
        Args:
            vmcp_name: Name of the vMCP to connect to. If None, uses active vmcp.
            user_id: User ID for database access (default: 1 for OSS)
        """
        self.user_id = user_id
        self.user_context = UserContext(user_id=user_id)
        
        # Resolve vmcp_id from vmcp_name
        self.vmcp_name = vmcp_name
        self.vmcp_id = None
        
        if vmcp_name:
            self.vmcp_id = self._resolve_vmcp_id(vmcp_name)
        
        # Initialize manager
        self.manager = VMCPConfigManager(
            user_id=str(user_id),
            vmcp_id=self.vmcp_id,
            logging_config={
                "agent_name": "vmcp_sdk",
                "agent_id": "vmcp_sdk",
                "client_id": "vmcp_sdk"
            }
        )
        
        # Cache for tools and typed functions
        self._tools_cache: Optional[List[Dict[str, Any]]] = None
        self._typed_functions: Dict[str, Any] = {}
        self._tools_loaded = False
    
    def _resolve_vmcp_id(self, vmcp_name: str) -> Optional[str]:
        """Resolve vmcp_name to vmcp_id."""
        from vmcp.storage.base import StorageBase
        
        storage = StorageBase(user_id=self.user_id)
        vmcp_id = storage.find_vmcp_name(vmcp_name)
        return vmcp_id
    
    async def _load_tools(self) -> None:
        """Load tools and create typed functions."""
        if self._tools_loaded:
            return
        
        if not self.vmcp_id:
            raise ValueError("No vMCP specified. Set vmcp_name or use set_active_vmcp()")
        
        tools = await self.manager.tools_list()
        
        # Convert Tool objects to dicts
        self._tools_cache = []
        for tool in tools:
            if hasattr(tool, 'model_dump'):
                tool_dict = tool.model_dump()
            elif isinstance(tool, dict):
                tool_dict = tool
            else:
                # Fallback: convert to dict manually
                tool_dict = {
                    "name": getattr(tool, 'name', str(tool)),
                    "description": getattr(tool, 'description', ''),
                    "inputSchema": getattr(tool, 'inputSchema', {})
                }
            self._tools_cache.append(tool_dict)
        
        # Create typed functions for each tool
        for tool_dict in self._tools_cache:
            tool_name = tool_dict.get("name", "")
            if not tool_name:
                continue

            # Normalize name for Python attribute access
            normalized_name = normalize_name(tool_name)

            # Create implementation function - capture tool_name in closure
            # Use a factory function to properly capture the tool_name
            def make_tool_impl(original_name: str):
                """Create a tool implementation function."""
                async def async_impl(**kwargs):
                    request = VMCPToolCallRequest(
                        tool_name=original_name,
                        arguments=kwargs
                    )
                    result = await self.manager.call_tool(
                        request,
                        connect_if_needed=True,
                        return_metadata=False
                    )

                    # Extract result data
                    if isinstance(result, dict):
                        return result
                    elif hasattr(result, 'model_dump'):
                        return result.model_dump()
                    elif hasattr(result, 'dict'):
                        return result.dict()
                    else:
                        return {"result": str(result)}

                # Wrap in sync function for compatibility
                def sync_wrapper(**kwargs):
                    return asyncio.run(async_impl(**kwargs))

                return sync_wrapper

            # Create typed function
            input_schema = tool_dict.get("inputSchema", {})
            description = tool_dict.get("description", "")

            # Create implementation - properly capture tool_name
            tool_impl = make_tool_impl(tool_name)

            # Create typed function with signature
            typed_func = create_function_with_signature(
                name=normalized_name,
                description=description,
                input_schema=input_schema,
                implementation=tool_impl
            )

            self._typed_functions[normalized_name] = typed_func
            # Also store by original name for lookup
            self._typed_functions[tool_name] = typed_func
        
        self._tools_loaded = True
    
    async def list_vmcps(self) -> List[Dict[str, Any]]:
        """List all available vMCPs."""
        vmcps = self.manager.list_available_vmcps()
        return vmcps
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all tools available in this vMCP."""
        await self._load_tools()
        return self._tools_cache or []
    
    async def list_prompts(self) -> List[Dict[str, Any]]:
        """List all prompts available in this vMCP."""
        if not self.vmcp_id:
            raise ValueError("No vMCP specified. Set vmcp_name or use set_active_vmcp()")
        
        prompts = await self.manager.prompts_list()
        
        # Convert Prompt objects to dicts
        prompts_list = []
        for prompt in prompts:
            if hasattr(prompt, 'model_dump'):
                prompts_list.append(prompt.model_dump())
            elif isinstance(prompt, dict):
                prompts_list.append(prompt)
            else:
                prompts_list.append({
                    "name": getattr(prompt, 'name', str(prompt)),
                    "description": getattr(prompt, 'description', ''),
                    "arguments": getattr(prompt, 'arguments', [])
                })
        
        return prompts_list
    
    async def list_resources(self) -> List[Dict[str, Any]]:
        """List all resources available in this vMCP."""
        if not self.vmcp_id:
            raise ValueError("No vMCP specified. Set vmcp_name or use set_active_vmcp()")
        
        vmcp_config = self.manager.load_vmcp_config(self.vmcp_id)
        if not vmcp_config:
            return []
        
        resources = vmcp_config.resources or []
        return resources
    
    def get_tool_function(self, tool_name: str):
        """
        Get a typed function for a tool.
        
        Args:
            tool_name: Name of the tool (original or normalized)
            
        Returns:
            Typed Python function for the tool
        """
        # Ensure tools are loaded
        asyncio.run(self._load_tools())
        
        # Try normalized name first, then original
        func = self._typed_functions.get(tool_name)
        if func:
            return func
        
        # Try with normalized name
        normalized = normalize_name(tool_name)
        return self._typed_functions.get(normalized)
    
    def __getattr__(self, name: str):
        """Dynamically access tool functions."""
        # Ensure tools are loaded
        asyncio.run(self._load_tools())
        
        # Check if it's a tool function
        if name in self._typed_functions:
            return self._typed_functions[name]
        
        # Check if it's a method
        if name in ["list_tools", "list_prompts", "list_resources", "list_vmcps"]:
            return getattr(self, name)
        
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

