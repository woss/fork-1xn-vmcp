#!/usr/bin/env python3
"""
List all tools available in the vMCP.

This script discovers and displays:
- MCP servers and their tools (with authorization status)
- Custom tools
- Sandbox tools

Usage:
    python list_tools.py
"""

import asyncio
import sys
from typing import Any, Dict, List, Optional

try:
    import vmcp_sdk
    from vmcp.mcps.mcp_config_manager import MCPConfigManager
    from vmcp.mcps.models import MCPConnectionStatus
    from vmcp.vmcps.vmcp_config_manager.config_core import VMCPConfigManager
    from vmcp.vmcps.sandbox_service import get_sandbox_service
    from vmcp.config import settings
except ImportError as e:
    print(f"Error importing required modules: {e}", file=sys.stderr)
    print("Make sure you're running this script in the sandbox environment.", file=sys.stderr)
    sys.exit(1)


async def get_authorization_url(server_id: str, user_id: int) -> Optional[str]:
    """Get authorization URL for a server that requires authentication."""
    try:
        from vmcp.mcps.mcp_client_manager import MCPClientManager
        
        config_manager = MCPConfigManager(str(user_id))
        client_manager = MCPClientManager(config_manager)
        
        server_config = config_manager.get_server(server_id)
        if not server_config or not server_config.url:
            return None
        
        # Initiate OAuth flow to get authorization URL
        callback_url = f"{settings.base_url}/api/otherservers/oauth/callback"
        
        result = await client_manager.auth_manager.initiate_oauth_flow(
            server_name=server_id,
            server_url=server_config.url,
            callback_url=callback_url,
            user_id=str(user_id),
            headers=server_config.headers
        )
        
        if result.get('status') == 'error':
            return None
        
        return result.get('authorization_url')
    except Exception as e:
        print(f"Warning: Could not get authorization URL for {server_id}: {e}", file=sys.stderr)
        return None


def format_schema(schema: Dict[str, Any], indent: int = 0) -> str:
    """Format a JSON schema for display."""
    if not schema:
        return "  " * indent + "No schema"
    
    lines = []
    schema_type = schema.get("type", "object")
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    
    if schema_type == "object" and properties:
        for prop_name, prop_schema in properties.items():
            prop_type = prop_schema.get("type", "unknown")
            prop_desc = prop_schema.get("description", "")
            is_req = prop_name in required
            
            req_marker = " (required)" if is_req else " (optional)"
            desc = f" - {prop_desc}" if prop_desc else ""
            
            lines.append("  " * indent + f"  • {prop_name}: {prop_type}{req_marker}{desc}")
    else:
        lines.append("  " * indent + f"Type: {schema_type}")
    
    return "\n".join(lines) if lines else "  " * indent + "No parameters"


def categorize_tools(tools: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Categorize tools by their source."""
    categorized: Dict[str, List[Dict[str, Any]]] = {
        "mcp_servers": [],
        "custom": [],
        "sandbox": []
    }
    
    for tool in tools:
        meta = tool.get("meta", {})
        tool_type = meta.get("type", "unknown")
        source = meta.get("source", "")
        
        if tool_type == "custom":
            tool_type_meta = meta.get("tool_type", "unknown")
            if tool_type_meta == "python" and source == "sandbox_discovered":
                categorized["sandbox"].append(tool)
            else:
                categorized["custom"].append(tool)
        elif "server" in meta or "server_id" in meta:
            categorized["mcp_servers"].append(tool)
        else:
            # Default to custom if we can't determine
            categorized["custom"].append(tool)
    
    return categorized


async def get_mcp_server_info(vmcp_id: str, user_id: int) -> List[Dict[str, Any]]:
    """Get information about MCP servers in the vMCP."""
    try:
        vmcp_manager = VMCPConfigManager(
            user_id=str(user_id),
            vmcp_id=vmcp_id,
            logging_config={
                "agent_name": "list_tools",
                "agent_id": "list_tools",
                "client_id": "list_tools"
            }
        )
        
        vmcp_config = vmcp_manager.load_vmcp_config(vmcp_id)
        if not vmcp_config:
            return []
        
        selected_servers = vmcp_config.vmcp_config.get('selected_servers', [])
        mcp_config_manager = MCPConfigManager(str(user_id))
        
        server_info_list = []
        for server in selected_servers:
            server_id = server.get('server_id')
            server_name = server.get('name', server_id)
            server_status = server.get('status', MCPConnectionStatus.UNKNOWN)
            
            # Get tools for this server
            server_tools = []
            try:
                tools_list = mcp_config_manager.tools_list(server_id)
                for tool_obj in tools_list:
                    if hasattr(tool_obj, 'model_dump'):
                        tool_dict = tool_obj.model_dump()
                    elif isinstance(tool_obj, dict):
                        tool_dict = tool_obj
                    else:
                        tool_dict = {
                            "name": getattr(tool_obj, 'name', 'unknown'),
                            "description": getattr(tool_obj, 'description', ''),
                            "inputSchema": getattr(tool_obj, 'inputSchema', {})
                        }
                    server_tools.append(tool_dict)
            except (KeyError, AttributeError):
                # Server might not be in config or not have tools
                pass
            except Exception as e:
                # Other errors
                print(f"Warning: Could not get tools for server {server_id}: {e}", file=sys.stderr)
            
            # Check if authorization is needed
            auth_url = None
            if server_status == MCPConnectionStatus.AUTH_REQUIRED:
                auth_url = await get_authorization_url(server_id, user_id)
            
            server_info_list.append({
                "server_id": server_id,
                "server_name": server_name,
                "status": str(server_status),
                "tools": server_tools,
                "auth_url": auth_url,
                "url": server.get('url')
            })
        
        return server_info_list
    except Exception as e:
        print(f"Warning: Could not get MCP server info: {e}", file=sys.stderr)
        return []


async def main_async():
    """Async main function to list all tools."""
    try:
        # Get vmcp_id from sandbox config
        sandbox_service = get_sandbox_service()
        vmcp_id = sandbox_service.get_sandbox_vmcp_id()
        
        if not vmcp_id:
            print("Error: Could not detect vmcp_id from sandbox config.", file=sys.stderr)
            print("Make sure you're running this script in a sandbox directory with .vmcp-config.json", file=sys.stderr)
            sys.exit(1)
        
        user_id = 1  # OSS uses user_id=1
        
        print("=" * 80)
        print(f"vMCP Tools Discovery: {vmcp_id}")
        print("=" * 80)
        print()
        
        # Check if progressive discovery is enabled
        vmcp_manager = VMCPConfigManager(
            user_id=str(user_id),
            vmcp_id=vmcp_id,
            logging_config={
                "agent_name": "list_tools",
                "agent_id": "list_tools",
                "client_id": "list_tools"
            }
        )
        vmcp_config = vmcp_manager.load_vmcp_config(vmcp_id)
        progressive_discovery_enabled = False
        sandbox_enabled = False
        if vmcp_config:
            metadata = getattr(vmcp_config, 'metadata', {}) or {}
            if isinstance(metadata, dict):
                progressive_discovery_enabled = metadata.get('progressive_discovery_enabled', False) is True
                sandbox_enabled = metadata.get('sandbox_enabled', False) is True
        
        # Get all tools via SDK (call async method directly since we're in an async context)
        try:
            from vmcp_sdk.client import VMCPClient
            client = VMCPClient(vmcp_id=vmcp_id, user_id=user_id)
            all_tools = await client.list_tools()
        except Exception as e:
            print(f"Error listing tools: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            all_tools = []
        
        # Categorize tools
        categorized = categorize_tools(all_tools)
        
        # Get MCP server information (always show MCP servers, even when progressive discovery is enabled)
        mcp_servers = await get_mcp_server_info(vmcp_id, user_id)
        
        # Display MCP Servers
        print("📡 MCP SERVERS")
        print("-" * 80)
        if progressive_discovery_enabled and sandbox_enabled:
            print("  ⚠️  NOTE: Progressive discovery is enabled. MCP tools are hidden from the main tools list")
            print("     but are still available for execution via the SDK using lowercase format: <servername>_<tool_name>")
            print("     Examples:")
            print("       - vmcp_sdk.allfeature_get_weather(city='Sydney')")
            print("       - vmcp_sdk.allfeature_list_cities()")
            print("       - vmcp_sdk.everythingremoteserver_echo(message='hello')")
            print("     The SDK normalizes tool names to lowercase. Calls are automatically routed to the correct MCP server.")
            print()
        if not mcp_servers:
            print("  No MCP servers configured.")
        else:
            for server_info in mcp_servers:
                server_name = server_info["server_name"]
                server_id = server_info["server_id"]
                status = server_info["status"]
                tools = server_info["tools"]
                auth_url = server_info.get("auth_url")
                url = server_info.get("url")
                
                print(f"\n  🔌 {server_name} ({server_id})")
                print(f"     Status: {status}")
                if url:
                    print(f"     URL: {url}")
                
                if status == MCPConnectionStatus.AUTH_REQUIRED.value:
                    if auth_url:
                        print("     ⚠️  Authorization Required")
                        print(f"     🔗 Authorization URL: {auth_url}")
                    else:
                        print("     ⚠️  Authorization Required (could not generate URL)")
                elif status == MCPConnectionStatus.CONNECTED.value:
                    print("     ✅ Connected")
                elif status == MCPConnectionStatus.ERROR.value:
                    print("     ❌ Error")
                else:
                    print(f"     ⚠️  Status: {status}")
                
                if tools:
                    print(f"     Tools ({len(tools)}):")
                    for tool in tools:
                        tool_name = tool.get("name", "unknown")
                        tool_desc = tool.get("description", "")
                        # Show SDK call format when progressive discovery is enabled
                        if progressive_discovery_enabled and sandbox_enabled:
                            server_name_clean = server_name.replace('_', '').lower()
                            tool_name_normalized = tool_name.lower()
                            sdk_call_name = f"{server_name_clean}_{tool_name_normalized}"
                            print(f"       • {tool_name} (SDK: {sdk_call_name})")
                        else:
                            print(f"       • {tool_name}")
                        if tool_desc:
                            print(f"         {tool_desc}")
                        schema = tool.get("inputSchema", {})
                        if schema:
                            schema_str = format_schema(schema, indent=3)
                            if schema_str.strip():
                                print(schema_str)
                else:
                    print("     No tools available")
        
        print()
        print("=" * 80)
        
        # Display Custom Tools
        print("\n🛠️  CUSTOM TOOLS")
        print("-" * 80)
        custom_tools = categorized["custom"]
        if not custom_tools:
            print("  No custom tools configured.")
        else:
            for tool in custom_tools:
                tool_name = tool.get("name", "unknown")
                tool_desc = tool.get("description", "")
                meta = tool.get("meta", {})
                tool_type = meta.get("tool_type", "unknown")
                
                print(f"\n  • {tool_name}")
                print(f"    Type: {tool_type}")
                if tool_desc:
                    print(f"    Description: {tool_desc}")
                schema = tool.get("inputSchema", {})
                if schema:
                    schema_str = format_schema(schema, indent=2)
                    if schema_str.strip():
                        print(f"    Parameters:")
                        print(schema_str)
        
        print()
        print("=" * 80)
        
        # Display Sandbox Tools
        print("\n🏖️  SANDBOX TOOLS")
        print("-" * 80)
        sandbox_tools = categorized["sandbox"]
        if not sandbox_tools:
            print("  No sandbox tools discovered.")
        else:
            for tool in sandbox_tools:
                tool_name = tool.get("name", "unknown")
                tool_desc = tool.get("description", "")
                meta = tool.get("meta", {})
                script_path = meta.get("script_path", "unknown")
                
                print(f"\n  • {tool_name}")
                if script_path != "unknown":
                    print(f"    Script: {script_path}")
                if tool_desc:
                    print(f"    Description: {tool_desc}")
                schema = tool.get("inputSchema", {})
                if schema:
                    schema_str = format_schema(schema, indent=2)
                    if schema_str.strip():
                        print(f"    Parameters:")
                        print(schema_str)
        
        print()
        print("=" * 80)
        print("\n📊 SUMMARY")
        print("-" * 80)
        print(f"  MCP Servers: {len(mcp_servers)}")
        total_mcp_tools = sum(len(s["tools"]) for s in mcp_servers)
        print(f"  MCP Server Tools: {total_mcp_tools}")
        if progressive_discovery_enabled and sandbox_enabled:
            print(f"    ⚠️  Note: {total_mcp_tools} MCP tools are hidden from main list but executable via SDK")
            print(f"    Use lowercase format: <servername>_<tool_name> (e.g., allfeature_get_weather)")
        print(f"  Custom Tools: {len(custom_tools)}")
        print(f"  Sandbox Tools: {len(sandbox_tools)}")
        print(f"  Tools in Main List: {len(all_tools)}")
        if progressive_discovery_enabled and sandbox_enabled:
            print(f"  Total Executable Tools: {len(all_tools) + total_mcp_tools} (includes {total_mcp_tools} hidden MCP tools)")
        else:
            print(f"  Total Tools: {len(all_tools)}")
        print()
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point - runs async main."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

