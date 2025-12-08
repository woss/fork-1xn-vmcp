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

        sandbox_service = get_sandbox_service()
        sandbox_path = sandbox_service.get_sandbox_path(vmcp_id)
        full_script_path = sandbox_path / script_path

        if not full_script_path.exists():
            error_content = TextContent(
                type="text",
                text=f"Sandbox tool script not found: {script_path}. The tool file may have been deleted or moved.",
                annotations=None,
                meta=None
            )
            return CallToolResult(
                content=[error_content],
                structuredContent=None,
                isError=True
            )

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

        # Create wrapper script that initializes sandbox restrictions and calls main() with arguments
        # The sandbox runtime is installed in the sandbox's venv, so we can import it here
        sandbox_dir_str = str(sandbox_path)
        wrapper_code = f"""
import sys
import json
import os
import asyncio
from pathlib import Path

# Initialize sandbox restrictions BEFORE executing user code
# This is where the restrictions are applied!
try:
    from sandbox_runtime import SandboxManager
    from sandbox_runtime.config.schemas import SandboxRuntimeConfig
    
    SANDBOX_DIR = Path("{sandbox_dir_str}")
    
    # Configure sandbox restrictions
    allow_read_paths = [
        "{sandbox_dir_str}",
        "/usr/lib",           # System libraries
        "/System/Library",    # macOS system libraries
        "/Library/Frameworks", # macOS frameworks  
        "/usr/bin",           # System binaries
        "/bin",               # Core binaries
        "/lib",               # Core libraries
        "/lib64",             # 64-bit libraries
    ]
    
    sandbox_config = SandboxRuntimeConfig.from_json({{
        "network": {{
            "allowedDomains": [],  # Empty = allow all network (needed for MCP calls)
            "deniedDomains": []
        }},
        "filesystem": {{
            "allowRead": allow_read_paths,
            "allowWrite": ["{sandbox_dir_str}"],  # Only write to sandbox
            "denyWrite": []
        }}
    }})
    
    # Initialize the sandbox manager (sets up restrictions)
    asyncio.run(SandboxManager.initialize(sandbox_config))
    SANDBOX_INITIALIZED = True
except ImportError as e:
    # sandbox_runtime not available - run without restrictions
    print(f"Warning: sandbox_runtime not available, running without restrictions: {{e}}", file=sys.stderr)
    SANDBOX_INITIALIZED = False
except Exception as e:
    print(f"Warning: Failed to initialize sandbox: {{e}}", file=sys.stderr)
    SANDBOX_INITIALIZED = False

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
    print(json.dumps({{"success": True, "result": result, "sandbox_initialized": SANDBOX_INITIALIZED}}))
else:
    print(json.dumps({{"success": False, "error": "No main() function found"}}))
"""

        # Write wrapper to temp file in sandbox
        temp_wrapper.write_text(wrapper_code, encoding='utf-8')

        # Change to sandbox directory
        original_cwd = os.getcwd()
        os.chdir(str(sandbox_path))

        try:
            # Execute directly without additional sandboxing
            # Sandbox-discovered tools are already in the sandbox directory and trusted
            # Additional sandboxing can cause "Operation not permitted" errors on macOS
            command = f"{venv_python} {temp_wrapper.name}"

            # Execute
            process = await asyncio.create_subprocess_shell(
                command,
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

            # Check for sandbox violation patterns in stderr
            sandbox_violation_patterns = [
                "Operation not permitted",
                "sandbox violation",
                "deny",
                "EPERM"
            ]
            if any(pattern.lower() in stderr_str.lower() for pattern in sandbox_violation_patterns):
                stderr_str = f"⚠️ SANDBOX RESTRICTION: {stderr_str}"

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
        
        # Generate descriptive error message for LLM
        exc_type = type(e).__name__
        exc_str = str(e)
        
        if "ModuleNotFoundError" in exc_type:
            error_msg = f"Sandbox tool execution failed: Missing Python module. Error: {exc_str}. The tool may require additional dependencies to be installed in the sandbox environment."
        elif "PermissionError" in exc_type:
            error_msg = f"Sandbox tool execution failed: Permission denied. Error: {exc_str}. The tool may be trying to access files or resources outside its sandbox."
        elif "FileNotFoundError" in exc_type:
            error_msg = f"Sandbox tool execution failed: File not found. Error: {exc_str}. A required file may have been deleted or moved."
        elif "TimeoutError" in exc_type or "timeout" in exc_str.lower():
            error_msg = f"Sandbox tool execution timed out. Error: {exc_str}. The tool took too long to complete."
        elif "ConnectionError" in exc_type or "connection" in exc_str.lower():
            error_msg = f"Sandbox tool execution failed: Connection error. Error: {exc_str}. The tool may be trying to access a network resource that is unavailable."
        else:
            error_msg = f"Sandbox tool execution failed. Error type: {exc_type}. Details: {exc_str}"
        
        error_content = TextContent(
            type="text",
            text=error_msg,
            annotations=None,
            meta=None
        )
        return CallToolResult(
            content=[error_content],
            structuredContent=None,
            isError=True
        )

