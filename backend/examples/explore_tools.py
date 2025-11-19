#!/usr/bin/env python3
"""
Tool Explorer Script

This script explores available tools in a vMCP and shows their signatures.

Run with: python examples/explore_tools.py
"""

import sys
import inspect
from pathlib import Path

# Add src to path to import vmcp_sdk
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import vmcp_sdk


def explore_tools(vmcp_name: str = "1xndemo"):
    """
    Explore tools in a vMCP and show their signatures.

    Args:
        vmcp_name: Name of the vMCP to explore
    """
    print(f"🔍 Exploring Tools in '{vmcp_name}'")
    print("=" * 80)

    # Access the vmcp
    if vmcp_name[0].isdigit():
        vmcp = getattr(vmcp_sdk, vmcp_name)
    else:
        vmcp = getattr(vmcp_sdk, vmcp_name)

    # List all tools
    print("\n📋 Listing all tools...")
    tools = vmcp.list_tools()
    print(f"   Found {len(tools)} tools\n")

    # Show first 10 tools with their details
    print("Tool Details (first 10):")
    print("-" * 80)

    for i, tool in enumerate(tools[:10], 1):
        tool_name = tool.get("name", "Unknown")
        python_name = tool.get("name", "Unknown").replace("-", "_").lower()
        description = tool.get("description", "No description")
        input_schema = tool.get("inputSchema", {})

        print(f"\n{i}. {tool_name}")
        print(f"   Python name: {python_name}")
        print(f"   Description: {description[:70]}...")

        # Show input schema
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])

        if properties:
            print(f"   Parameters:")
            for param_name, param_schema in list(properties.items())[:5]:  # Show first 5
                param_type = param_schema.get("type", "unknown")
                is_required = param_name in required
                req_marker = " (required)" if is_required else " (optional)"
                print(f"     - {param_name}: {param_type}{req_marker}")

            if len(properties) > 5:
                print(f"     ... and {len(properties) - 5} more parameters")

    print("\n" + "=" * 80)
    print(f"✅ Explored {len(tools)} tools in '{vmcp_name}'")

    # Try to access a tool function directly
    print("\n🧪 Testing direct tool access...")
    try:
        # Try to get a tool function
        add_tool = getattr(vmcp, "all_feature_add_numbers", None)
        if add_tool:
            print("   ✓ Successfully accessed 'all_feature_add_numbers'")
            # Show function signature
            sig = inspect.signature(add_tool)
            print(f"   Signature: {sig}")
        else:
            print("   ⚠️  Could not access tool function")
    except Exception as e:
        print(f"   ⚠️  Error accessing tool: {e}")


if __name__ == "__main__":
    vmcp_name = sys.argv[1] if len(sys.argv) > 1 else "1xndemo"
    explore_tools(vmcp_name)

