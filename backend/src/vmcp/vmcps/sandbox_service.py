"""
Sandbox Service for vMCP

Manages per-vMCP sandbox environments with isolated Python virtual environments.
Each sandbox is stored at ~/.vmcp/{vmcp_id}/ with its own uv virtual environment.
"""

import os
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
from vmcp.utilities.logging import get_logger

logger = get_logger(__name__)


class SandboxService:
    """Service for managing per-vMCP sandbox environments."""
    
    SANDBOX_BASE = Path.home() / ".vmcp"
    
    # Setup prompt for progressive discovery mode (with CLI)
    SETUP_PROMPT_PROGRESSIVE_DISCOVERY = """You are a coding agent with access to a sandboxed execution environment and the vMCP SDK for interacting with Virtual MCP Servers.

================================================================================
SANDBOX ENVIRONMENT
================================================================================

IMPORTANT: All bash commands and Python code execution MUST be done through the provided tools:
- execute_bash: Use this tool for ALL bash/shell commands
- execute_python: Use this tool for ALL Python code execution

The sandbox environment:
- Executes commands in ~/.vmcp/{vmcp_id}
- Applies filesystem restrictions (blocks access to ~/.ssh, ~/.aws, etc.)
- Applies network restrictions (no network access by default)
- Provides isolation from the host system

When you need to:
- Run shell commands → Use execute_bash tool
- Execute Python code → Use execute_python tool
- Create files → They will be created in ~/.vmcp/{vmcp_id}
- Read files → Only files in the sandbox directory are accessible

Do NOT attempt to execute bash or python commands directly. Always use the provided tools.

================================================================================
vMCP SDK ARCHITECTURE
================================================================================

The vMCP SDK (Virtual Model Context Protocol SDK) is a lightweight Python library that provides a simple, Pythonic interface to interact with vMCPs (Virtual MCP Servers) and their underlying MCP (Model Context Protocol) servers.

KEY CONCEPTS:

1. vMCP (Virtual MCP Server):
   - A virtual configuration that aggregates multiple MCP servers
   - Provides a unified interface to access tools, prompts, and resources from multiple MCP servers
   - Each vMCP has a unique name (e.g., "1xndemo", "linear", "github")

2. MCP (Model Context Protocol) Server:
   - Individual servers that expose tools, prompts, and resources
   - Examples: Linear, GitHub, Slack, custom servers
   - Multiple MCP servers can be combined into a single vMCP

3. SDK Components:
   - VMCPClient: Core client for interacting with vMCPs
   - VMCPProxy: Dynamic proxy for accessing vMCPs by name
   - ActiveVMCPManager: Manages the currently active vMCP
   - Tools are automatically converted to typed Python functions

================================================================================
INSTALLATION & SETUP
================================================================================

To use the vMCP SDK and CLI in the sandbox:

1. Install the SDK (if not already installed):
   ```python
   # Use execute_python to run:
   import subprocess
   import sys
   subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", "/path/to/oss/backend"])
   ```

2. Set active vMCP (optional, for convenience):
   ```python
   from vmcp_sdk.active_vmcp import ActiveVMCPManager
   ActiveVMCPManager().set_active_vmcp("1xndemo")
   ```

================================================================================
EXPLORATION STRATEGY: CLI FOR DISCOVERY, SDK FOR SCRIPTS
================================================================================

RECOMMENDED WORKFLOW:
1. Use the CLI (vmcp-sdk) for EXPLORATION and DISCOVERY
2. Use the SDK (vmcp_sdk) for PROGRAMMATIC WORKFLOWS and SCRIPTS

WHY THIS APPROACH:
- CLI is perfect for quick exploration, listing tools, and understanding structure
- SDK is better for creating reusable scripts, combining tools, and automation
- CLI provides formatted, human-readable output
- SDK provides programmatic access with typed functions

USING THE CLI FOR EXPLORATION:

The CLI tool `vmcp-sdk` is available for exploring tools in the current sandbox's vMCP.
The vMCP is automatically detected from the sandbox configuration.

1. List tools in the current vMCP:
   ```bash
   # Use execute_bash to run:
   vmcp-sdk list-tools
   ```

2. List prompts in the current vMCP:
   ```bash
   vmcp-sdk list-prompts
   ```

3. List resources in the current vMCP:
   ```bash
   vmcp-sdk list-resources
   ```

4. Call a tool directly (for testing):
   ```bash
   vmcp-sdk call-tool --tool all_feature_add_numbers --payload '{"a": 5, "b": 3}'
   ```

CLI OUTPUT FORMAT:
- Tools are displayed in a formatted table with:
  - Original tool name
  - Normalized Python name (for SDK usage)
  - Description
  - Parameters and types

EXAMPLE EXPLORATION WORKFLOW:
```bash
# Step 1: Explore tools in the current vMCP
vmcp-sdk list-tools

# Step 2: Test a tool via CLI
vmcp-sdk call-tool --tool all_feature_get_weather --payload '{"city": "Sydney"}'

# Step 3: Once you understand the tools, create a script using the SDK
```

================================================================================
USING THE SDK - BASIC PATTERNS (FOR SCRIPTS)
================================================================================

The SDK automatically works with the vMCP associated with the current sandbox.
The vMCP is detected from .vmcp-config.json in the sandbox directory.

1. Import the SDK:
   ```python
   import vmcp_sdk
   ```

2. Access the current vMCP:
   ```python
   # The SDK automatically uses the vMCP from the sandbox config
   # For vMCP names starting with numbers or special characters, use getattr:
   demo = getattr(vmcp_sdk, "1xndemo")
   
   # For regular names, direct access works:
   linear = vmcp_sdk.linear  # if "linear" is the current vMCP
   ```

3. Explore tools in the current vMCP (programmatically):
   ```python
   # List all tools
   tools = vmcp_sdk.list_tools()
   for tool in tools:
       print(f"Tool: {tool.get('name')}")
       print(f"  Description: {tool.get('description')}")
       print(f"  Parameters: {tool.get('inputSchema', {}).get('properties', {})}")
   ```

4. List prompts and resources:
   ```python
   prompts = vmcp_sdk.list_prompts()
   resources = vmcp_sdk.list_resources()
   ```

5. Call tools (tools are typed Python functions!):
   ```python
   # Tools are automatically converted to Python functions
   # Function names are normalized (e.g., "AllFeature_get_weather" → "all_feature_get_weather")
   result = demo.all_feature_get_weather(city="Sydney")
   
   # Results are dictionaries with structured content
   if isinstance(result, dict):
       structured = result.get("structuredContent", {})
       text_content = result.get("content", [])
   ```

================================================================================
TOOL EXECUTION PATTERNS
================================================================================

1. Understanding Tool Results:
   - Tools return dictionaries with:
     - "content": List of text/content items
     - "structuredContent": Structured data (if available)
     - "isError": Boolean indicating if there was an error
     - "meta": Metadata about the execution

2. Error Handling:
   ```python
   try:
       result = demo.all_feature_get_weather(city="Sydney")
       if result.get("isError"):
           print(f"Error: {result.get('content')}")
       else:
           print(f"Success: {result.get('structuredContent')}")
   except Exception as e:
       print(f"Exception: {e}")
   ```

3. Extracting Results:
   ```python
   result = demo.all_feature_add_numbers(a=5, b=3)
   
   # Method 1: Get structured content
   structured = result.get("structuredContent", {})
   if structured:
       sum_value = structured.get("result")
   
   # Method 2: Get text content
   content = result.get("content", [])
   if content and isinstance(content[0], dict):
       text = content[0].get("text", "")
   ```

================================================================================
CREATING REUSABLE WORKFLOW SCRIPTS
================================================================================

You can create Python scripts that combine multiple tools into workflows:

```python
#!/usr/bin/env python3
\"\"\"
Example workflow combining multiple tools
\"\"\"
import sys
from pathlib import Path

# Add SDK to path if needed
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import vmcp_sdk

def weather_workflow(city: str):
    \"\"\"Get location and weather for a city.\"\"\"
    demo = getattr(vmcp_sdk, "1xndemo")
    
    # Step 1: Get location
    location = demo.all_feature_get_location(city=city)
    print(f"Location: {location}")
    
    # Step 2: Get weather
    weather = demo.all_feature_get_weather(city=city)
    print(f"Weather: {weather}")
    
    return {"location": location, "weather": weather}

if __name__ == "__main__":
    city = sys.argv[1] if len(sys.argv) > 1 else "Sydney"
    weather_workflow(city)
```

BEST PRACTICES FOR WORKFLOWS:
1. Always handle errors gracefully
2. Extract and validate results before using them
3. Use structured content when available
4. Create reusable functions that can be called from other scripts
5. Document your workflows with docstrings
6. Save workflow scripts in the sandbox directory for reuse

================================================================================
EXPLORING TOOLS - CLI vs SDK
================================================================================

OPTION 1: Use CLI for quick exploration (RECOMMENDED for discovery):
```bash
# Quick overview of all tools
vmcp-sdk list-tools

# See formatted output with names, descriptions, and parameters
# This is faster and more readable for initial exploration
```

OPTION 2: Use SDK for programmatic exploration (for scripts):
```python
import vmcp_sdk
import inspect

tools = vmcp_sdk.list_tools()

for tool in tools:
    tool_name = tool.get("name", "")
    normalized_name = tool_name.replace("-", "_").lower()
    
    # Access the tool function via the SDK
    demo = getattr(vmcp_sdk, "1xndemo")  # Use current vMCP name
    try:
        tool_func = getattr(demo, normalized_name)
        sig = inspect.signature(tool_func)
        print(f"{tool_name}: {sig}")
    except AttributeError:
        print(f"{tool_name}: (not accessible as function)")
```

RECOMMENDED WORKFLOW:
1. Use CLI first: `vmcp-sdk list-tools` to see all tools quickly
2. Test a tool via CLI: `vmcp-sdk call-tool --tool <name> --payload '{...}'`
3. Once you understand the tools, create SDK scripts for automation

================================================================================
WORKFLOW EXAMPLES
================================================================================

1. Math Operations Workflow:
   ```python
   demo = getattr(vmcp_sdk, "1xndemo")
   result1 = demo.all_feature_add_numbers(a=15, b=27)
   result2 = demo.all_feature_add(a=10, b=20)
   ```

2. Weather Information Pipeline:
   ```python
   demo = getattr(vmcp_sdk, "1xndemo")
   location = demo.all_feature_get_location(city="New York")
   weather = demo.all_feature_get_weather(city="New York")
   ```

3. Data Processing:
   ```python
   demo = getattr(vmcp_sdk, "1xndemo")
   time_result = demo.all_feature_get_current_time(timezone_name="UTC")
   data_result = demo.all_feature_process_data(data="sample_data")
   ```

================================================================================
IMPORTANT NOTES FOR CODING AGENTS
================================================================================

1. Always use execute_python for Python code execution
2. Always use execute_bash for shell commands
3. Use CLI (vmcp-sdk) for EXPLORATION - quick discovery of vMCPs and tools
4. Use SDK (vmcp_sdk) for SCRIPTS - programmatic workflows and automation
5. The SDK must be installed in the environment where you're running code
6. Tool names are normalized: "AllFeature_get_weather" → "all_feature_get_weather"
7. For vMCP names starting with numbers, use getattr(vmcp_sdk, "1xndemo")
8. Tools are lazy-loaded - they're created when first accessed
9. Results are dictionaries - always check structure before accessing
10. Create reusable scripts in ~/.vmcp/{vmcp_id} for future use
11. Test tools individually before combining them into workflows
12. Start with CLI exploration, then build SDK scripts based on what you discover

================================================================================
TROUBLESHOOTING
================================================================================

If you encounter issues:

1. SDK/CLI not found:
   - Ensure SDK is installed: `pip install -e /path/to/oss/backend`
   - Check Python path includes the SDK location
   - Verify `vmcp-sdk` command is in PATH

2. vMCP not found:
   - Ensure you're in a sandbox directory with .vmcp-config.json
   - Verify the sandbox is properly configured with a vMCP ID

3. Tool not accessible:
   - Use CLI to see exact names: `vmcp-sdk list-tools`
   - Check tool name normalization (camelCase → snake_case)
   - List tools programmatically: `vmcp_sdk.list_tools()` to see exact names
   - Use getattr for dynamic access: `getattr(demo, "tool_name")`

4. Tool execution errors:
   - Test via CLI first: `vmcp-sdk call-tool --tool <name> --payload '{...}'`
   - Check tool parameters match the schema
   - Verify required parameters are provided
   - Check result.get("isError") for error details

5. CLI vs SDK confusion:
   - Remember: CLI for exploration, SDK for scripts
   - If you need quick info → use CLI
   - If you need automation → use SDK

================================================================================

Remember: You are a coding agent. 

WORKFLOW RECOMMENDATION:
1. Use execute_bash to run CLI commands for EXPLORATION:
   - `vmcp-sdk list-tools` - Explore tools in the current vMCP
   - `vmcp-sdk call-tool --tool <name> --payload '{...}'` - Test tools

2. Use execute_python to run SDK code for SCRIPTS:
   - Import vmcp_sdk and create programmatic workflows
   - Combine multiple tools into reusable scripts
   - Save scripts in ~/.vmcp/{vmcp_id} for future use

The CLI is your exploration tool, the SDK is your automation tool. Use both effectively!
"""

    # Setup prompt for SDK-only mode (without CLI)
    SETUP_PROMPT_SDK_ONLY = """You are a coding agent with access to a sandboxed execution environment and the vMCP SDK for interacting with Virtual MCP Servers.

================================================================================
SANDBOX ENVIRONMENT
================================================================================

IMPORTANT: All bash commands and Python code execution MUST be done through the provided tools:
- execute_bash: Use this tool for ALL bash/shell commands
- execute_python: Use this tool for ALL Python code execution

The sandbox environment:
- Executes commands in ~/.vmcp/{vmcp_id}
- Applies filesystem restrictions (blocks access to ~/.ssh, ~/.aws, etc.)
- Applies network restrictions (no network access by default)
- Provides isolation from the host system

When you need to:
- Run shell commands → Use execute_bash tool
- Execute Python code → Use execute_python tool
- Create files → They will be created in ~/.vmcp/{vmcp_id}
- Read files → Only files in the sandbox directory are accessible

Do NOT attempt to execute bash or python commands directly. Always use the provided tools.

================================================================================
vMCP SDK ARCHITECTURE
================================================================================

The vMCP SDK (Virtual Model Context Protocol SDK) is a lightweight Python library that provides a simple, Pythonic interface to interact with vMCPs (Virtual MCP Servers) and their underlying MCP (Model Context Protocol) servers.

KEY CONCEPTS:

1. vMCP (Virtual MCP Server):
   - A virtual configuration that aggregates multiple MCP servers
   - Provides a unified interface to access tools, prompts, and resources from multiple MCP servers
   - Each vMCP has a unique name (e.g., "1xndemo", "linear", "github")

2. MCP (Model Context Protocol) Server:
   - Individual servers that expose tools, prompts, and resources
   - Examples: Linear, GitHub, Slack, custom servers
   - Multiple MCP servers can be combined into a single vMCP

3. SDK Components:
   - VMCPClient: Core client for interacting with vMCPs
   - VMCPProxy: Dynamic proxy for accessing vMCPs by name
   - ActiveVMCPManager: Manages the currently active vMCP
   - Tools are automatically converted to typed Python functions

================================================================================
INSTALLATION & SETUP
================================================================================

To use the vMCP SDK in the sandbox:

1. Install the SDK (if not already installed):
   ```python
   # Use execute_python to run:
   import subprocess
   import sys
   subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", "/path/to/oss/backend"])
   ```

2. Set active vMCP (optional, for convenience):
   ```python
   from vmcp_sdk.active_vmcp import ActiveVMCPManager
   ActiveVMCPManager().set_active_vmcp("1xndemo")
   ```

================================================================================
USING THE SDK - BASIC PATTERNS
================================================================================

The SDK automatically works with the vMCP associated with the current sandbox.
The vMCP is detected from .vmcp-config.json in the sandbox directory.

1. Import the SDK:
   ```python
   import vmcp_sdk
   ```

2. Access the current vMCP:
   ```python
   # The SDK automatically uses the vMCP from the sandbox config
   # For vMCP names starting with numbers or special characters, use getattr:
   demo = getattr(vmcp_sdk, "1xndemo")
   
   # For regular names, direct access works:
   linear = vmcp_sdk.linear  # if "linear" is the current vMCP
   ```

3. Explore tools in the current vMCP:
   ```python
   # List all tools
   tools = vmcp_sdk.list_tools()
   for tool in tools:
       print(f"Tool: {tool.get('name')}")
       print(f"  Description: {tool.get('description')}")
       print(f"  Parameters: {tool.get('inputSchema', {}).get('properties', {})}")
   ```

4. List prompts and resources:
   ```python
   prompts = vmcp_sdk.list_prompts()
   resources = vmcp_sdk.list_resources()
   ```

6. Call tools (tools are typed Python functions!):
   ```python
   demo = getattr(vmcp_sdk, "1xndemo")
   
   # Tools are automatically converted to Python functions
   # Function names are normalized (e.g., "AllFeature_get_weather" → "all_feature_get_weather")
   result = demo.all_feature_get_weather(city="Sydney")
   
   # Results are dictionaries with structured content
   if isinstance(result, dict):
       structured = result.get("structuredContent", {})
       text_content = result.get("content", [])
   ```

================================================================================
TOOL EXECUTION PATTERNS
================================================================================

1. Understanding Tool Results:
   - Tools return dictionaries with:
     - "content": List of text/content items
     - "structuredContent": Structured data (if available)
     - "isError": Boolean indicating if there was an error
     - "meta": Metadata about the execution

2. Error Handling:
   ```python
   try:
       result = demo.all_feature_get_weather(city="Sydney")
       if result.get("isError"):
           print(f"Error: {result.get('content')}")
       else:
           print(f"Success: {result.get('structuredContent')}")
   except Exception as e:
       print(f"Exception: {e}")
   ```

3. Extracting Results:
   ```python
   result = demo.all_feature_add_numbers(a=5, b=3)
   
   # Method 1: Get structured content
   structured = result.get("structuredContent", {})
   if structured:
       sum_value = structured.get("result")
   
   # Method 2: Get text content
   content = result.get("content", [])
   if content and isinstance(content[0], dict):
       text = content[0].get("text", "")
   ```

================================================================================
CREATING REUSABLE WORKFLOW SCRIPTS
================================================================================

You can create Python scripts that combine multiple tools into workflows:

```python
#!/usr/bin/env python3
\"\"\"
Example workflow combining multiple tools
\"\"\"
import sys
from pathlib import Path

# Add SDK to path if needed
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import vmcp_sdk

def weather_workflow(city: str):
    \"\"\"Get location and weather for a city.\"\"\"
    demo = getattr(vmcp_sdk, "1xndemo")
    
    # Step 1: Get location
    location = demo.all_feature_get_location(city=city)
    print(f"Location: {location}")
    
    # Step 2: Get weather
    weather = demo.all_feature_get_weather(city=city)
    print(f"Weather: {weather}")
    
    return {"location": location, "weather": weather}

if __name__ == "__main__":
    city = sys.argv[1] if len(sys.argv) > 1 else "Sydney"
    weather_workflow(city)
```

BEST PRACTICES FOR WORKFLOWS:
1. Always handle errors gracefully
2. Extract and validate results before using them
3. Use structured content when available
4. Create reusable functions that can be called from other scripts
5. Document your workflows with docstrings
6. Save workflow scripts in the sandbox directory for reuse

================================================================================
WORKFLOW EXAMPLES
================================================================================

1. Math Operations Workflow:
   ```python
   demo = getattr(vmcp_sdk, "1xndemo")
   result1 = demo.all_feature_add_numbers(a=15, b=27)
   result2 = demo.all_feature_add(a=10, b=20)
   ```

2. Weather Information Pipeline:
   ```python
   demo = getattr(vmcp_sdk, "1xndemo")
   location = demo.all_feature_get_location(city="New York")
   weather = demo.all_feature_get_weather(city="New York")
   ```

3. Data Processing:
   ```python
   demo = getattr(vmcp_sdk, "1xndemo")
   time_result = demo.all_feature_get_current_time(timezone_name="UTC")
   data_result = demo.all_feature_process_data(data="sample_data")
   ```

================================================================================
IMPORTANT NOTES FOR CODING AGENTS
================================================================================

1. Always use execute_python for Python code execution
2. Always use execute_bash for shell commands
3. Use the SDK (vmcp_sdk) for programmatic workflows and automation
4. The SDK must be installed in the environment where you're running code
5. Tool names are normalized: "AllFeature_get_weather" → "all_feature_get_weather"
6. For vMCP names starting with numbers, use getattr(vmcp_sdk, "1xndemo")
7. Tools are lazy-loaded - they're created when first accessed
8. Results are dictionaries - always check structure before accessing
9. Create reusable scripts in ~/.vmcp/{vmcp_id} for future use
10. Test tools individually before combining them into workflows

================================================================================
TROUBLESHOOTING
================================================================================

If you encounter issues:

1. SDK not found:
   - Ensure SDK is installed: `pip install -e /path/to/oss/backend`
   - Check Python path includes the SDK location

2. vMCP not found:
   - Ensure you're in a sandbox directory with .vmcp-config.json
   - Verify the sandbox is properly configured with a vMCP ID

3. Tool not accessible:
   - Check tool name normalization (camelCase → snake_case)
   - List tools programmatically: `vmcp_sdk.list_tools()` to see exact names
   - Use getattr for dynamic access: `getattr(demo, "tool_name")`

4. Tool execution errors:
   - Check tool parameters match the schema
   - Verify required parameters are provided
   - Check result.get("isError") for error details

================================================================================

Remember: You are a coding agent. 

Use execute_python to run SDK code for programmatic workflows:
- Import vmcp_sdk and create workflows
- Combine multiple tools into reusable scripts
- Save scripts in ~/.vmcp/{vmcp_id} for future use
"""

    
    def __init__(self):
        """Initialize the sandbox service."""
        self.SANDBOX_BASE.mkdir(parents=True, exist_ok=True)
    
    def get_sandbox_path(self, vmcp_id: str) -> Path:
        """
        Get the sandbox directory path for a vMCP.
        
        Args:
            vmcp_id: The vMCP ID
            
        Returns:
            Path to the sandbox directory
        """
        # Sanitize vmcp_id for filesystem safety
        safe_id = self._sanitize_vmcp_id(vmcp_id)
        return self.SANDBOX_BASE / safe_id
    
    def _sanitize_vmcp_id(self, vmcp_id: str) -> str:
        """
        Sanitize vmcp_id for use in filesystem paths.
        
        Args:
            vmcp_id: The vMCP ID
            
        Returns:
            Sanitized ID safe for filesystem
        """
        # Remove or replace unsafe characters
        safe = vmcp_id.replace("/", "_").replace("\\", "_")
        safe = safe.replace("..", "_").replace("~", "_")
        # Remove any remaining problematic characters
        safe = "".join(c for c in safe if c.isalnum() or c in "._-")
        return safe or "default"
    
    def sandbox_exists(self, vmcp_id: str) -> bool:
        """
        Check if sandbox directory exists.
        
        Args:
            vmcp_id: The vMCP ID
            
        Returns:
            True if sandbox directory exists
        """
        sandbox_path = self.get_sandbox_path(vmcp_id)
        return sandbox_path.exists() and sandbox_path.is_dir()
    
    def venv_exists(self, vmcp_id: str) -> bool:
        """
        Check if virtual environment exists in sandbox.
        
        Args:
            vmcp_id: The vMCP ID
            
        Returns:
            True if venv exists
        """
        sandbox_path = self.get_sandbox_path(vmcp_id)
        venv_path = sandbox_path / ".venv"
        return venv_path.exists() and venv_path.is_dir()
    
    def is_enabled(self, vmcp_id: str, vmcp_config: Optional[Any] = None) -> bool:
        """
        Check if sandbox is enabled.
        
        Only checks the metadata flag (sandbox_enabled in vMCP metadata).
        Does not check filesystem state.
        
        Args:
            vmcp_id: The vMCP ID
            vmcp_config: Optional VMCPConfig object to check metadata (avoids extra DB call)
            
        Returns:
            True if sandbox_enabled flag is True in metadata, False otherwise
        """
        # Check metadata if config provided
        if vmcp_config is not None:
            metadata = getattr(vmcp_config, 'metadata', {}) or {}
            if isinstance(metadata, dict):
                sandbox_enabled = metadata.get('sandbox_enabled')
                return sandbox_enabled is True
        
        # If no config provided, default to False
        return False
    
    def _find_uv_command(self) -> Optional[str]:
        """
        Find the uv command to use.
        
        Returns:
            Path to uv command or None
        """
        # Check system PATH
        if shutil.which("uv"):
            return "uv"
        # Check ~/.local/bin/uv
        local_uv = Path.home() / ".local" / "bin" / "uv"
        if local_uv.exists():
            return str(local_uv)
        return None
    
    def _get_project_root(self) -> Path:
        """
        Get the project root directory.
        
        Returns:
            Path to project root
        """
        # Assume we're in oss/backend/src/vmcp/vmcps/
        # Go up to oss/backend/
        current = Path(__file__).resolve()
        # oss/backend/src/vmcp/vmcps/sandbox_service.py
        # -> oss/backend/
        return current.parent.parent.parent.parent
    
    def _create_sandbox_config(self, sandbox_path: Path, vmcp_id: str) -> None:
        """
        Create sandbox config file with vmcp_id.
        
        Args:
            sandbox_path: Path to sandbox directory
            vmcp_id: The vMCP ID to store
        """
        import json
        config_path = sandbox_path / ".vmcp-config.json"
        config_data = {
            "vmcp_id": vmcp_id
        }
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        logger.info(f"Created sandbox config file: {config_path}")
    
    def get_sandbox_vmcp_id(self, sandbox_path: Optional[Path] = None) -> Optional[str]:
        """
        Get vmcp_id from sandbox config file.
        
        Args:
            sandbox_path: Path to sandbox directory. If None, tries to detect from current directory.
            
        Returns:
            vmcp_id if found, None otherwise
        """
        import json
        
        if sandbox_path is None:
            # Try to detect from current working directory
            cwd = Path.cwd()
            # Check if we're in a sandbox directory (~/.vmcp/{vmcp_id})
            if str(cwd).startswith(str(self.SANDBOX_BASE)):
                sandbox_path = cwd
            else:
                return None
        
        config_path = sandbox_path / ".vmcp-config.json"
        if not config_path.exists():
            return None
        
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
                return config_data.get("vmcp_id")
        except (json.JSONDecodeError, KeyError, IOError) as e:
            logger.warning(f"Error reading sandbox config: {e}")
            return None
    
    def create_sandbox(self, vmcp_id: str) -> bool:
        """
        Create sandbox directory and uv virtual environment.
        Install required packages following Makefile pattern.
        
        Args:
            vmcp_id: The vMCP ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            sandbox_path = self.get_sandbox_path(vmcp_id)
            sandbox_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created sandbox directory: {sandbox_path}")
            
            venv_path = sandbox_path / ".venv"
            
            # Create virtual environment
            uv_cmd = self._find_uv_command()
            if uv_cmd:
                logger.info(f"Using uv to create venv: {uv_cmd}")
                result = subprocess.run(
                    [uv_cmd, "venv", str(venv_path)],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode != 0:
                    logger.error(f"Failed to create venv with uv: {result.stderr}")
                    return False
            else:
                logger.info("Using python3 -m venv (uv not found)")
                result = subprocess.run(
                    ["python3", "-m", "venv", str(venv_path)],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode != 0:
                    logger.error(f"Failed to create venv: {result.stderr}")
                    return False
            
            logger.info(f"Created virtual environment: {venv_path}")
            
            # Get project root
            project_root = self._get_project_root()
            venv_python = venv_path / "bin" / "python"
            if not venv_python.exists():
                # Try Windows path
                venv_python = venv_path / "Scripts" / "python.exe"
            
            if not venv_python.exists():
                logger.error(f"Python executable not found in venv: {venv_path}")
                return False
            
            # Install sandbox-runtime-py
            sandbox_runtime_path = project_root / "src" / "sandbox-runtime-py"
            if not sandbox_runtime_path.exists():
                logger.error(f"sandbox-runtime-py not found at: {sandbox_runtime_path}")
                return False
            
            logger.info(f"Installing sandbox-runtime-py from {sandbox_runtime_path}")
            if uv_cmd:
                result = subprocess.run(
                    [uv_cmd, "pip", "install", "-e", str(sandbox_runtime_path), "--python", str(venv_python)],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            else:
                result = subprocess.run(
                    [str(venv_python), "-m", "pip", "install", "-e", str(sandbox_runtime_path)],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            
            if result.returncode != 0:
                logger.error(f"Failed to install sandbox-runtime-py: {result.stderr}")
                return False
            
            logger.info("Installed sandbox-runtime-py")
            
            # Install vmcp package
            logger.info(f"Installing vmcp package from {project_root}")
            if uv_cmd:
                result = subprocess.run(
                    [uv_cmd, "pip", "install", "-e", str(project_root), "--python", str(venv_python)],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            else:
                result = subprocess.run(
                    [str(venv_python), "-m", "pip", "install", "-e", str(project_root)],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            
            if result.returncode != 0:
                logger.error(f"Failed to install vmcp: {result.stderr}")
                return False
            
            logger.info("Installed vmcp package")
            
            # Create sandbox config file with vmcp_id
            self._create_sandbox_config(sandbox_path, vmcp_id)
            
            logger.info(f"✅ Sandbox created successfully: {sandbox_path}")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("Timeout creating sandbox")
            return False
        except Exception as e:
            logger.error(f"Error creating sandbox: {e}", exc_info=True)
            return False
    
    def _create_venv_with_packages(self, venv_path: Path, sandbox_path: Path, vmcp_id: Optional[str] = None) -> bool:
        """
        Create virtual environment and install required packages.
        
        Args:
            venv_path: Path to the venv directory
            sandbox_path: Path to the sandbox directory
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create virtual environment
            uv_cmd = self._find_uv_command()
            if uv_cmd:
                logger.info(f"Using uv to create venv: {uv_cmd}")
                result = subprocess.run(
                    [uv_cmd, "venv", str(venv_path)],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode != 0:
                    logger.error(f"Failed to create venv with uv: {result.stderr}")
                    return False
            else:
                logger.info("Using python3 -m venv (uv not found)")
                result = subprocess.run(
                    ["python3", "-m", "venv", str(venv_path)],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode != 0:
                    logger.error(f"Failed to create venv: {result.stderr}")
                    return False
            
            logger.info(f"Created virtual environment: {venv_path}")
            
            # Get project root
            project_root = self._get_project_root()
            venv_python = venv_path / "bin" / "python"
            if not venv_python.exists():
                # Try Windows path
                venv_python = venv_path / "Scripts" / "python.exe"
            
            if not venv_python.exists():
                logger.error(f"Python executable not found in venv: {venv_path}")
                return False
            
            # Install sandbox-runtime-py
            sandbox_runtime_path = project_root / "src" / "sandbox-runtime-py"
            if not sandbox_runtime_path.exists():
                logger.error(f"sandbox-runtime-py not found at: {sandbox_runtime_path}")
                return False
            
            logger.info(f"Installing sandbox-runtime-py from {sandbox_runtime_path}")
            if uv_cmd:
                result = subprocess.run(
                    [uv_cmd, "pip", "install", "-e", str(sandbox_runtime_path), "--python", str(venv_python)],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            else:
                result = subprocess.run(
                    [str(venv_python), "-m", "pip", "install", "-e", str(sandbox_runtime_path)],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            
            if result.returncode != 0:
                logger.error(f"Failed to install sandbox-runtime-py: {result.stderr}")
                return False
            
            logger.info("Installed sandbox-runtime-py")
            
            # Install vmcp package
            logger.info(f"Installing vmcp package from {project_root}")
            if uv_cmd:
                result = subprocess.run(
                    [uv_cmd, "pip", "install", "-e", str(project_root), "--python", str(venv_python)],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            else:
                result = subprocess.run(
                    [str(venv_python), "-m", "pip", "install", "-e", str(project_root)],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            
            if result.returncode != 0:
                logger.error(f"Failed to install vmcp: {result.stderr}")
                return False
            
            logger.info("Installed vmcp package")
            
            # Create sandbox config file with vmcp_id if it doesn't exist
            if vmcp_id is None:
                # Extract vmcp_id from sandbox_path (it's the directory name)
                vmcp_id = sandbox_path.name
            config_path = sandbox_path / ".vmcp-config.json"
            if not config_path.exists():
                self._create_sandbox_config(sandbox_path, vmcp_id)
            
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("Timeout creating venv with packages")
            return False
        except Exception as e:
            logger.error(f"Error creating venv with packages: {e}", exc_info=True)
            return False
    
    def delete_sandbox(self, vmcp_id: str) -> bool:
        """
        Delete the sandbox directory and all its contents.
        
        Args:
            vmcp_id: The vMCP ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            sandbox_path = self.get_sandbox_path(vmcp_id)
            if sandbox_path.exists():
                shutil.rmtree(sandbox_path)
                logger.info(f"Deleted sandbox directory: {sandbox_path}")
                return True
            else:
                logger.info(f"Sandbox directory does not exist: {sandbox_path}")
                return True  # Consider it successful if it doesn't exist
        except Exception as e:
            logger.error(f"Error deleting sandbox for {vmcp_id}: {e}", exc_info=True)
            return False
    
    def get_sandbox_tools(self, vmcp_id: str) -> List[Dict[str, Any]]:
        """
        Get sandbox tool definitions to inject into vMCP.
        
        Args:
            vmcp_id: The vMCP ID
            
        Returns:
            List of tool definitions
        """
        sandbox_path = str(self.get_sandbox_path(vmcp_id))
        
        return [
            {
                "name": "execute_bash",
                "description": "TO RUN BASH TOOLS ALWAYS USE THIS TOOL. DO NOT EXECUTE BASH COMMANDS DIRECTLY. Execute a bash command in a sandboxed environment.",
                "text": f"The command will be executed in a sandboxed environment. The sandbox directory appears as /root/ to the LLM (e.g., 'pwd' returns /root). The actual sandbox is located at {sandbox_path} with filesystem and network restrictions applied. The sandbox prevents access to sensitive directories like ~/.ssh, ~/.aws, and restricts network access.",
                "tool_type": "python",
                "code": f"""
import asyncio
import os
import subprocess
from pathlib import Path
from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig

SANDBOX_DIR = Path("{sandbox_path}")

async def execute_bash(command: str, timeout: int = 30):
    \"\"\"
    Execute a bash command in a sandboxed environment.
    
    Args:
        command: The bash command to execute (e.g., "ls -la", "echo 'hello'")
        timeout: Maximum execution time in seconds (default: 30)
        
    Returns:
        A dictionary containing:
        - stdout: Standard output from the command
        - stderr: Standard error output (may include sandbox violation info)
        - returncode: Exit code of the command (0 = success)
        - success: Boolean indicating if command succeeded
    \"\"\"
    # Initialize sandbox config
    sandbox_config = SandboxRuntimeConfig.from_json({{
        "network": {{
            "allowedDomains": [],
            "deniedDomains": []
        }},
        "filesystem": {{
            "denyRead": [
                "~/.ssh",
                "~/.aws",
                "~/.kube",
                "~/.config/gcloud"
            ],
            "allowWrite": [
                str(SANDBOX_DIR),
                "."
            ],
            "denyWrite": [
                ".env",
                "*.key",
                "*.pem"
            ]
        }}
    }})
    
    await SandboxManager.initialize(sandbox_config)
    
    # Change to sandbox directory
    original_cwd = os.getcwd()
    os.chdir(str(SANDBOX_DIR))
    
    try:
        # Wrap command with sandbox restrictions
        # Mount sandbox directory as /root so it appears as /root/ to the LLM
        sandboxed_command = await SandboxManager.wrap_with_sandbox(
            command,
            bin_shell="bash",
            root_mount_path=str(SANDBOX_DIR),
            root_mount_target="/root"
        )
        
        # Execute the sandboxed command
        # Note: cwd is still SANDBOX_DIR, but inside the sandbox it appears as /root
        process = await asyncio.create_subprocess_shell(
            sandboxed_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(SANDBOX_DIR)
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {{
                "stdout": "",
                "stderr": f"Command timed out after {{timeout}} seconds",
                "returncode": -1,
                "success": False
            }}
        
        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")
        
        # Annotate stderr with sandbox violations if any
        stderr_str = SandboxManager.annotate_stderr_with_sandbox_failures(
            command,
            stderr_str
        )
        
        return {{
            "stdout": stdout_str,
            "stderr": stderr_str,
            "returncode": process.returncode or 0,
            "success": process.returncode == 0,
            "sandbox_dir": "/root"  # Show /root instead of actual path
        }}
    except Exception as e:
        return {{
            "stdout": "",
            "stderr": f"Error executing command: {{str(e)}}",
            "returncode": -1,
            "success": False
        }}
    finally:
        os.chdir(original_cwd)

def main(command: str, timeout: int = 30):
    \"\"\"
    Synchronous wrapper for execute_bash.
    This is called by the Python tool executor.
    \"\"\"
    return asyncio.run(execute_bash(command, timeout))
""",
                "variables": [
                    {
                        "name": "command",
                        "description": "The bash command to execute",
                        "required": True,
                        "type": "str"
                    },
                    {
                        "name": "timeout",
                        "description": "Maximum execution time in seconds",
                        "required": False,
                        "type": "int"
                    }
                ],
                "environment_variables": [],
                "tool_calls": []
            },
            {
                "name": "execute_python",
                "description": "Execute Python code in a sandboxed environment.",
                "text": f"The Python code will be executed in a sandboxed environment. The sandbox directory appears as /root/ to the LLM (e.g., 'os.getcwd()' returns /root). The actual sandbox is located at {sandbox_path} with filesystem and network restrictions applied. The sandbox prevents access to sensitive directories and restricts network access.",
                "tool_type": "python",
                "code": f"""
import asyncio
import os
import subprocess
from pathlib import Path
from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig

SANDBOX_DIR = Path("{sandbox_path}")

async def execute_python(code: str, timeout: int = 30):
    \"\"\"
    Execute Python code in a sandboxed environment.
    
    Args:
        code: The Python code to execute (e.g., "print('hello')", "import os; print(os.getcwd())")
        timeout: Maximum execution time in seconds (default: 30)
        
    Returns:
        A dictionary containing:
        - stdout: Standard output from the code execution
        - stderr: Standard error output (may include sandbox violation info)
        - returncode: Exit code (0 = success)
        - success: Boolean indicating if execution succeeded
    \"\"\"
    # Initialize sandbox config
    sandbox_config = SandboxRuntimeConfig.from_json({{
        "network": {{
            "allowedDomains": [],
            "deniedDomains": []
        }},
        "filesystem": {{
            "denyRead": [
                "~/.ssh",
                "~/.aws",
                "~/.kube",
                "~/.config/gcloud"
            ],
            "allowWrite": [
                str(SANDBOX_DIR),
                "."
            ],
            "denyWrite": [
                ".env",
                "*.key",
                "*.pem"
            ]
        }}
    }})
    
    await SandboxManager.initialize(sandbox_config)
    
    # Write code to a temporary file in the sandbox
    temp_file = SANDBOX_DIR / "temp_execution.py"
    temp_file.write_text(code, encoding="utf-8")
    
    # Change to sandbox directory
    original_cwd = os.getcwd()
    os.chdir(str(SANDBOX_DIR))
    
    try:
        # Get Python executable from venv
        venv_python = SANDBOX_DIR / ".venv" / "bin" / "python"
        if not venv_python.exists():
            venv_python = SANDBOX_DIR / ".venv" / "Scripts" / "python.exe"
        if not venv_python.exists():
            venv_python = "python3"
        
        # Wrap command with sandbox restrictions
        # Mount sandbox directory as /root so it appears as /root/ to the LLM
        command = f"{{venv_python}} {{temp_file.name}}"
        sandboxed_command = await SandboxManager.wrap_with_sandbox(
            command,
            bin_shell="bash",
            root_mount_path=str(SANDBOX_DIR),
            root_mount_target="/root"
        )
        
        # Execute the sandboxed command
        # Note: cwd is still SANDBOX_DIR, but inside the sandbox it appears as /root
        process = await asyncio.create_subprocess_shell(
            sandboxed_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(SANDBOX_DIR)
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {{
                "stdout": "",
                "stderr": f"Command timed out after {{timeout}} seconds",
                "returncode": -1,
                "success": False
            }}
        
        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")
        
        # Annotate stderr with sandbox violations if any
        stderr_str = SandboxManager.annotate_stderr_with_sandbox_failures(
            command,
            stderr_str
        )
        
        return {{
            "stdout": stdout_str,
            "stderr": stderr_str,
            "returncode": process.returncode or 0,
            "success": process.returncode == 0,
            "sandbox_dir": "/root"  # Show /root instead of actual path
        }}
    except Exception as e:
        return {{
            "stdout": "",
            "stderr": f"Error executing code: {{str(e)}}",
            "returncode": -1,
            "success": False
        }}
    finally:
        os.chdir(original_cwd)
        # Clean up temp file
        try:
            temp_file.unlink()
        except Exception:
            pass

def main(code: str, timeout: int = 30):
    \"\"\"
    Synchronous wrapper for execute_python.
    This is called by the Python tool executor.
    \"\"\"
    return asyncio.run(execute_python(code, timeout))
""",
                "variables": [
                    {
                        "name": "code",
                        "description": "The Python code to execute",
                        "required": True,
                        "type": "str"
                    },
                    {
                        "name": "timeout",
                        "description": "Maximum execution time in seconds",
                        "required": False,
                        "type": "int"
                    }
                ],
                "environment_variables": [],
                "tool_calls": []
            }
        ]
    
    def get_sandbox_prompt(self, vmcp_id: str, vmcp_config=None) -> str:
        """
        Get sandbox setup prompt to inject into vMCP.
        
        Returns different prompts based on progressive discovery setting:
        - If progressive discovery is enabled: Returns prompt with CLI instructions
        - If progressive discovery is disabled: Returns SDK-only prompt
        
        Args:
            vmcp_id: The vMCP ID
            vmcp_config: Optional vMCP config to check progressive discovery flag
            
        Returns:
            Setup prompt text
        """
        # Check if progressive discovery is enabled
        progressive_discovery_enabled = False
        if vmcp_config:
            metadata = getattr(vmcp_config, 'metadata', {}) or {}
            if isinstance(metadata, dict):
                progressive_discovery_enabled = metadata.get('progressive_discovery_enabled', False) is True
        
        # Return appropriate prompt
        if progressive_discovery_enabled:
            prompt = self.SETUP_PROMPT_PROGRESSIVE_DISCOVERY
        else:
            prompt = self.SETUP_PROMPT_SDK_ONLY
        
        return prompt.replace("{vmcp_id}", vmcp_id)


# Singleton instance
_sandbox_service: Optional[SandboxService] = None


def get_sandbox_service() -> SandboxService:
    """Get the singleton sandbox service instance."""
    global _sandbox_service
    if _sandbox_service is None:
        _sandbox_service = SandboxService()
    return _sandbox_service

