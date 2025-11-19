"""
vMCP SDK CLI - Command line interface for vMCP operations.

This CLI is designed for use in sandbox environments for testing tools.
"""

import json
import sys

import typer
from rich.console import Console
from rich.table import Table

from ..active_vmcp import ActiveVMCPManager
from ..client import VMCPClient

app = typer.Typer(
    name="vmcp",
    help="vMCP SDK - Command line interface for Virtual MCP Servers",
    add_completion=False,
    invoke_without_command=True
)

console = Console()
_active_vmcp_manager = ActiveVMCPManager()


def _run_async(coro):
    """Helper to run async functions."""
    import asyncio
    return asyncio.run(coro)


def _list_vmcps():
    """Internal function to list all vMCPs."""
    try:
        client = VMCPClient()
        vmcps = _run_async(client.list_vmcps())

        if not vmcps:
            console.print("[yellow]No vMCPs found.[/yellow]")
            return

        table = Table(title="Available vMCPs", show_header=True, header_style="bold cyan")
        table.add_column("Name", style="cyan")
        table.add_column("ID", style="green")
        table.add_column("Description", style="white")
        table.add_column("Tools", justify="right", style="blue")

        for vmcp in vmcps:
            table.add_row(
                vmcp.get("name", ""),
                vmcp.get("id", ""),
                (vmcp.get("description", "") or "")[:50] + "..." if len(vmcp.get("description", "") or "") > 50 else (vmcp.get("description", "") or ""),
                str(vmcp.get("total_tools", 0))
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error listing vMCPs: {e}[/red]")
        sys.exit(1)


def _list_mcps_in_active_vmcp():
    """Internal function to list MCP servers in the active vMCP."""
    try:
        # Get active vmcp
        active_vmcp_name = _active_vmcp_manager.get_active_vmcp()
        if not active_vmcp_name:
            console.print("[yellow]No active vMCP set.[/yellow]")
            console.print("Use ActiveVMCPManager.set_active_vmcp() to set an active vMCP")
            return

        # Create client for the active vmcp
        client = VMCPClient(vmcp_name=active_vmcp_name)
        if not client.vmcp_id:
            console.print(f"[red]vMCP '{active_vmcp_name}' not found.[/red]")
            return

        # Load the vmcp config to get selected servers
        vmcp_config = client.manager.load_vmcp_config(client.vmcp_id)
        if not vmcp_config:
            console.print(f"[red]Could not load vMCP config for '{active_vmcp_name}'.[/red]")
            return

        # Get selected servers from config
        vmcp_config_dict = vmcp_config.vmcp_config if hasattr(vmcp_config, 'vmcp_config') else {}
        selected_servers = vmcp_config_dict.get('selected_servers', [])

        if not selected_servers:
            console.print(f"[yellow]No MCP servers found in active vMCP '{active_vmcp_name}'.[/yellow]")
            return

        table = Table(title=f"MCP Servers in '{active_vmcp_name}'", show_header=True, header_style="bold cyan")
        table.add_column("Name", style="cyan")
        table.add_column("Server ID", style="green")
        table.add_column("Transport", style="yellow")
        table.add_column("Status", style="white")
        table.add_column("URL/Command", style="blue")

        for server in selected_servers:
            if isinstance(server, dict):
                server_name = server.get("name", "Unknown")
                server_id = server.get("server_id", server.get("id", "Unknown"))
                transport = server.get("transport_type", "Unknown")
                status = server.get("status", "Unknown")
                url_or_cmd = server.get("url") or server.get("command") or "N/A"
                if isinstance(url_or_cmd, list):
                    url_or_cmd = " ".join(url_or_cmd)
                table.add_row(
                    server_name,
                    server_id,
                    transport,
                    status,
                    str(url_or_cmd)[:60] + "..." if len(str(url_or_cmd)) > 60 else str(url_or_cmd)
                )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error listing MCP servers: {e}[/red]")
        sys.exit(1)


@app.callback()
def main_callback(
    ctx: typer.Context,
    list_vmcps: bool = typer.Option(False, "--list-vmcps", help="List all available vMCPs"),
    list_mcps: bool = typer.Option(False, "--list-mcps", help="List MCP servers in the active vMCP")
):
    """
    vMCP SDK - Command line interface for Virtual MCP Servers.

    Example:
        vmcp-sdk --list-vmcps          # List all vMCPs
        vmcp-sdk --list-mcps           # List MCP servers in active vMCP
        vmcp-sdk <vmcp_name> list-tools
    """
    if list_vmcps:
        _list_vmcps()
        raise typer.Exit()
    if list_mcps:
        _list_mcps_in_active_vmcp()
        raise typer.Exit()


@app.command()
def list_tools(
    vmcp_name: str = typer.Argument(..., help="Name of the vMCP"),
):
    """
    List all tools available in a vMCP.
    
    Example:
        vmcp linear list-tools
        vmcp playwright list-tools
    """
    try:
        client = VMCPClient(vmcp_name=vmcp_name)
        tools = _run_async(client.list_tools())
        
        if not tools:
            console.print(f"[yellow]No tools found in vMCP '{vmcp_name}'.[/yellow]")
            return
        
        table = Table(title=f"Tools in {vmcp_name}", show_header=True, header_style="bold cyan")
        table.add_column("Name", style="cyan")
        table.add_column("Python Name", style="green")
        table.add_column("Description", style="white")
        
        from ..schema import normalize_name
        
        for tool in tools:
            tool_name = tool.get("name", "") if isinstance(tool, dict) else getattr(tool, "name", str(tool))
            python_name = normalize_name(tool_name)
            tool_desc = tool.get("description", "") if isinstance(tool, dict) else getattr(tool, "description", "")
            table.add_row(
                tool_name,
                python_name,
                (tool_desc or "")[:80] + "..." if len(tool_desc or "") > 80 else (tool_desc or "")
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing tools: {e}[/red]")
        sys.exit(1)


@app.command()
def list_prompts(
    vmcp_name: str = typer.Argument(..., help="Name of the vMCP"),
):
    """
    List all prompts available in a vMCP.
    
    Example:
        vmcp linear list-prompts
        vmcp playwright list-prompts
    """
    try:
        client = VMCPClient(vmcp_name=vmcp_name)
        prompts = _run_async(client.list_prompts())
        
        if not prompts:
            console.print(f"[yellow]No prompts found in vMCP '{vmcp_name}'.[/yellow]")
            return
        
        table = Table(title=f"Prompts in {vmcp_name}", show_header=True, header_style="bold cyan")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="white")
        
        for prompt in prompts:
            prompt_name = prompt.get("name", "") if isinstance(prompt, dict) else getattr(prompt, "name", str(prompt))
            prompt_desc = prompt.get("description", "") if isinstance(prompt, dict) else getattr(prompt, "description", "")
            table.add_row(
                prompt_name,
                (prompt_desc or "")[:80] + "..." if len(prompt_desc or "") > 80 else (prompt_desc or "")
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing prompts: {e}[/red]")
        sys.exit(1)


@app.command()
def list_resources(
    vmcp_name: str = typer.Argument(..., help="Name of the vMCP"),
):
    """
    List all resources available in a vMCP.
    
    Example:
        vmcp linear list-resources
        vmcp playwright list-resources
    """
    try:
        client = VMCPClient(vmcp_name=vmcp_name)
        resources = _run_async(client.list_resources())
        
        if not resources:
            console.print(f"[yellow]No resources found in vMCP '{vmcp_name}'.[/yellow]")
            return
        
        table = Table(title=f"Resources in {vmcp_name}", show_header=True, header_style="bold cyan")
        table.add_column("URI", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Description", style="white")
        
        for resource in resources:
            if isinstance(resource, dict):
                table.add_row(
                    resource.get("uri", ""),
                    resource.get("name", ""),
                    (resource.get("description", "") or "")[:60] + "..." if len(resource.get("description", "") or "") > 60 else (resource.get("description", "") or "")
                )
            else:
                table.add_row(
                    getattr(resource, "uri", ""),
                    getattr(resource, "name", ""),
                    (getattr(resource, "description", "") or "")[:60] + "..." if len(getattr(resource, "description", "") or "") > 60 else (getattr(resource, "description", "") or "")
                )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing resources: {e}[/red]")
        sys.exit(1)


@app.command()
def call_tool(
    vmcp_name: str = typer.Argument(..., help="Name of the vMCP"),
    tool_name: str = typer.Option(..., "--tool", "-t", help="Name of the tool to call"),
    payload: str = typer.Option(..., "--payload", "-p", help="JSON payload with tool arguments"),
):
    """
    Call a tool in a vMCP.
    
    Example:
        vmcp linear call-tool --tool search_issues --payload '{"query": "bug"}'
        vmcp playwright call-tool --tool take_screenshot --payload '{"url": "https://example.com"}'
    """
    try:
        # Parse payload
        try:
            arguments = json.loads(payload)
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON payload: {e}[/red]")
            sys.exit(1)
        
        # Call tool
        client = VMCPClient(vmcp_name=vmcp_name)
        
        # Use the typed function if available
        tool_func = client.get_tool_function(tool_name)
        if tool_func:
            result = tool_func(**arguments)
        else:
            # Fallback to direct call
            from vmcp.vmcps.models import VMCPToolCallRequest
            request = VMCPToolCallRequest(
                tool_name=tool_name,
                arguments=arguments
            )
            result = _run_async(client.manager.call_tool(
                request,
                connect_if_needed=True,
                return_metadata=False
            ))
        
        # Print result
        console.print("[green]Tool executed successfully![/green]")
        console.print(json.dumps(result, indent=2))
        
    except Exception as e:
        console.print(f"[red]Error calling tool: {e}[/red]")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    app()


if __name__ == "__main__":
    main()

