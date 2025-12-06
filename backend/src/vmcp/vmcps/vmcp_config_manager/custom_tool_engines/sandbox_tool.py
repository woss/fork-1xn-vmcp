#!/usr/bin/env python3
"""
Sandbox Tool Engine
===================

Execution engine for sandbox-discovered Python tools.
These tools are Python scripts stored in vmcp_tools/ directory and executed
in the sandbox environment using SandboxManager.
"""

import asyncio
import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from mcp.types import TextContent, PromptMessage, GetPromptResult, CallToolResult

logger = logging.getLogger("1xN_vMCP_SANDBOX_TOOL")


async def execute_sandbox_discovered_tool(
    vmcp_id: str,
    script_path: str,
    arguments: Dict[str, Any],
    environment_variables: Dict[str, Any],
    tool_as_prompt: bool = False
) -> CallToolResult:
    """
    Execute a sandbox-discovered tool script in the sandbox environment.
    Uses SandboxManager for isolation and sandbox's venv Python.

    Args:
        vmcp_id: The vMCP ID
        script_path: Relative path to the script from sandbox root
        arguments: Tool arguments dictionary
        environment_variables: Environment variables dictionary
        tool_as_prompt: Whether to return as prompt result

    Returns:
        CallToolResult or GetPromptResult
    """
    try:
        from vmcp.vmcps.sandbox_service import get_sandbox_service
        from sandbox_runtime import SandboxManager
        from sandbox_runtime.config.schemas import SandboxRuntimeConfig

        sandbox_service = get_sandbox_service()
        sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
        full_script_path = sandbox_path / script_path

        if not full_script_path.exists():
            error_content = TextContent(
                type="text",
                text=f"Tool script not found: {script_path}",
                annotations=None,
                meta=None
            )
            return CallToolResult(
                content=[error_content],
                structuredContent=None,
                isError=True
            )

        # Initialize sandbox config (same as execute_python tool)
        sandbox_dir_str = str(sandbox_path)
        allow_read_paths = [
            sandbox_dir_str,
            "/usr/lib",
            "/System/Library",
            "/Library/Frameworks",
            "/usr/bin",
            "/bin",
            "/lib",
            "/lib64",
        ]

        sandbox_config = SandboxRuntimeConfig.from_json({
            "network": {
                "allowedDomains": [],
                "deniedDomains": []
            },
            "filesystem": {
                "allowRead": allow_read_paths,
                "allowWrite": [sandbox_dir_str],
                "denyWrite": []
            }
        })

        await SandboxManager.initialize(sandbox_config)

        # Get venv Python
        venv_python = sandbox_path / ".venv" / "bin" / "python"
        if not venv_python.exists():
            venv_python = sandbox_path / ".venv" / "Scripts" / "python.exe"
        if not venv_python.exists():
            venv_python = "python3"

        # Write arguments to JSON file for safe passing
        args_file = sandbox_path / "temp_tool_args.json"
        temp_wrapper = sandbox_path / "temp_tool_wrapper.py"

        with open(args_file, 'w') as f:
            json.dump(arguments, f)

        # Create wrapper script that calls main() with arguments
        wrapper_code = f"""
import sys
import json
import os
from pathlib import Path

sys.path.insert(0, '{str(sandbox_path)}')

# Load arguments from JSON file
args_file = Path('{args_file}')
with open(args_file, 'r') as f:
    arguments = json.load(f)

# Import and execute the tool script
script_path = Path('{full_script_path}')
exec(compile(script_path.read_text(), str(script_path), 'exec'), globals())

# Call main function with arguments
if 'main' in globals() and callable(main):
    import inspect
    sig = inspect.signature(main)
    param_names = list(sig.parameters.keys())
    
    # Filter arguments to match function signature
    filtered_args = {{k: v for k, v in arguments.items() if k in param_names}}
    
    result = main(**filtered_args)
    print(json.dumps({{"success": True, "result": result}}))
else:
    print(json.dumps({{"success": False, "error": "No main() function found"}}))
"""

        # Write wrapper to temp file in sandbox
        temp_wrapper.write_text(wrapper_code, encoding='utf-8')

        # Change to sandbox directory
        original_cwd = os.getcwd()
        os.chdir(str(sandbox_path))

        try:
            # Wrap command with sandbox restrictions
            command = f"{venv_python} {temp_wrapper.name}"
            sandboxed_command = await SandboxManager.wrap_with_sandbox(
                command,
                bin_shell="bash"
            )

            # Execute
            process = await asyncio.create_subprocess_shell(
                sandboxed_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(sandbox_path)
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=60
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text="Tool execution timed out after 60 seconds",
                        annotations=None,
                        meta=None
                    )],
                    structuredContent=None,
                    isError=True
                )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            # Annotate stderr with sandbox violations
            stderr_str = SandboxManager.annotate_stderr_with_sandbox_failures(
                command,
                stderr_str
            )

            # Parse result
            try:
                result_data = json.loads(stdout_str.strip())
                if result_data.get('success', False):
                    result_text = json.dumps(result_data.get('result', ''), indent=2)
                    is_error = False
                else:
                    result_text = f"Error: {result_data.get('error', 'Unknown error')}"
                    is_error = True
            except json.JSONDecodeError:
                result_text = stdout_str if stdout_str else stderr_str
                is_error = process.returncode != 0

            if stderr_str and not is_error:
                result_text = f"{result_text}\n\nStderr: {stderr_str}"

            text_content = TextContent(
                type="text",
                text=result_text,
                annotations=None,
                meta=None
            )

            if tool_as_prompt:
                prompt_message = PromptMessage(
                    role="user",
                    content=text_content
                )
                return GetPromptResult(
                    description="Sandbox tool execution result",
                    messages=[prompt_message]
                )

            return CallToolResult(
                content=[text_content],
                structuredContent=None,
                isError=is_error
            )

        finally:
            os.chdir(original_cwd)
            try:
                temp_wrapper.unlink()
            except Exception:
                pass
            try:
                args_file.unlink()
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Error executing sandbox tool: {e}", exc_info=True)
        error_content = TextContent(
            type="text",
            text=f"Error executing sandbox tool: {str(e)}",
            annotations=None,
            meta=None
        )
        return CallToolResult(
            content=[error_content],
            structuredContent=None,
            isError=True
        )

