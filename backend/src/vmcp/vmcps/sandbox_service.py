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

IMPORTANT: All bash commands and Python code execution MUST be done through the provided tools.
You have access to the execute_bash tool:

1. execute_bash: Execute bash/shell commands in the sandbox

SANDBOX LOCATION:
- All operations execute in: ~/.vmcp/{vmcp_id}
- Working directory: ~/.vmcp/{vmcp_id} (appears as /root/ inside sandbox)
- Files created/modified are stored in this directory

SANDBOX RESTRICTIONS:
- Filesystem: Blocks access to ~/.ssh, ~/.aws, ~/.kube, ~/.config/gcloud
- Network: No network access by default
- Isolation: Complete isolation from the host system

USING execute_bash TOOL:

The execute_bash tool runs any bash/shell command in the sandbox. Use it for ALL file operations and shell commands.

Common operations:
- List files: execute_bash(command="ls -la")
- Create directory: execute_bash(command="mkdir -p mydir")
- Copy files: execute_bash(command="cp source.txt dest.txt")
- Move/rename: execute_bash(command="mv old.txt new.txt")
- Remove files: execute_bash(command="rm file.txt")
- Create files: execute_bash(command="echo 'content' > file.txt")
- View files: execute_bash(command="cat file.txt")
- Find files: execute_bash(command="find . -name '*.py'")
- Check Python version: execute_bash(command=".venv/bin/python --version")
- Install packages: execute_bash(command=".venv/bin/pip install package_name")
- Install packages with extras: execute_bash(command=".venv/bin/pip install 'httpx[socks]'")
- Run Python code: execute_bash(command=".venv/bin/python -c \"print('Hello')\"")
- Run Python scripts: execute_bash(command=".venv/bin/python script.py")

INSTALLING MISSING PACKAGES:
If you encounter ImportError or missing package errors, install the required packages:

1. Basic package installation:
   execute_bash(command=".venv/bin/pip install package_name")

2. Install package with extras (for optional dependencies):
   execute_bash(command=".venv/bin/pip install 'httpx[socks]'")
   execute_bash(command=".venv/bin/pip install 'requests[security]'")

3. Install multiple packages:
   execute_bash(command=".venv/bin/pip install package1 package2 package3")

4. Install from requirements file:
   execute_bash(command=".venv/bin/pip install -r requirements.txt")

5. Common examples:
   - Missing socksio: execute_bash(command=".venv/bin/pip install 'httpx[socks]'")
   - Missing requests: execute_bash(command=".venv/bin/pip install requests")
   - Missing pandas: execute_bash(command=".venv/bin/pip install pandas")

IMPORTANT: Always install missing packages when you see ImportError or "package is not installed" errors.
The sandbox has network access for package installation via pip.

Examples:
Use execute_bash like this:
# Create a directory
execute_bash(command="mkdir -p scripts")

# Copy a file
execute_bash(command="cp template.py script.py")

# List all Python files
execute_bash(command="find . -name '*.py' -type f")

# Check if a file exists
execute_bash(command="test -f script.py && echo 'exists' || echo 'not found'")

# Install a missing package (when you see ImportError)
execute_bash(command=".venv/bin/pip install 'httpx[socks]'")

# Run Python code inline
execute_bash(command=".venv/bin/python -c \"print('Hello, World!')\"")

# Run a Python script
execute_bash(command=".venv/bin/python script.py")

CREATING DYNAMIC TOOLS:
You can create new tools on the fly by saving Python scripts to the `vmcp_tools/` directory. These tools are automatically discovered and made available via the SDK.

1. Create a Python script in `vmcp_tools/`:
   - Must have a `main()` function with type hints for arguments
   - Must have a docstring describing what the tool does
   - Example:
     execute_bash(command="mkdir -p vmcp_tools")
     execute_bash(command="cat > vmcp_tools/my_tool.py << 'EOF'
     def main(name: str, count: int = 1):
         \"\"\"Greet a person multiple times.\"\"\"
         return f'Hello {name}! ' * count
     EOF")

2. Verify the tool is available:
   - Run `vmcp_sdk.list_tools()` to see the new tool (it will appear as `sandbox_tool_my_tool`)
   - Or use CLI: `vmcp-sdk list-tools`

3. Use the tool:
   - Call it like any other SDK tool: `vmcp_sdk.sandbox_tool_my_tool(name="World", count=3)`

WORKFLOW PATTERNS:

1. Create Python script file, then run it:
   # Create script
   execute_bash(command="cat > script.py << 'EOF'\\nimport vmcp_sdk\\nresult = vmcp_sdk.some_tool()\\nprint(result)\\nEOF")
   
   # Run script
   execute_bash(command=".venv/bin/python script.py")

CRITICAL RULES:
- NEVER try to execute bash or python commands directly
- ALWAYS use execute_bash for shell commands
- For Python code, create a script file and run it with execute_bash: execute_bash(command=".venv/bin/python script.py")
- The sandbox Python is at .venv/bin/python
- All file operations must go through execute_bash
- Files are created in ~/.vmcp/{vmcp_id}

================================================================================
vMCP SDK ARCHITECTURE
================================================================================

The vMCP SDK (Virtual Model Context Protocol SDK) is a lightweight Python library that provides a simple, Pythonic interface to interact with vMCPs (Virtual MCP Servers) and their underlying MCP (Model Context Protocol) servers.

KEY CONCEPTS:

1. vMCP (Virtual MCP Server):
   - A virtual configuration that aggregates multiple MCP servers
   - Provides a unified interface to access tools, prompts, and resources from multiple MCP servers
   - Each vMCP has a unique ID (e.g., "1xndemo", "linear", "github")

2. MCP (Model Context Protocol) Server:
   - Individual servers that expose tools, prompts, and resources
   - Examples: Linear, GitHub, Slack, custom servers
   - Multiple MCP servers can be combined into a single vMCP

3. SDK Components:
   - VMCPClient: Core client for interacting with vMCPs
   - Tools are automatically converted to typed Python functions
   - The vMCP is automatically detected from .vmcp-config.json in the sandbox directory

================================================================================
AUTOMATIC vMCP DETECTION
================================================================================

IMPORTANT: The vMCP is automatically detected from the sandbox configuration file (.vmcp-config.json).
You do NOT need to specify the vMCP name or ID anywhere - it's automatically read from the sandbox.

The sandbox directory contains a .vmcp-config.json file with the vmcp_id for this sandbox.
Both the SDK and CLI automatically use this configuration.

================================================================================
INSTALLATION & SETUP
================================================================================

The SDK and CLI are pre-installed in the sandbox virtual environment.
No additional installation is needed - just import and use!

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
The vMCP is automatically detected from .vmcp-config.json in the sandbox directory.

1. List tools in the current vMCP:
   ```bash
   # Use execute_bash to run:
   vmcp-sdk list-tools
   ```

2. REFRESHING TOOL LIST:
   Whenever you create a new dynamic tool, you MUST run `vmcp-sdk list-tools` to refresh the tool registry.
   This ensures the new tool is immediately available for use.

   ```bash
   # Create tool
   # ... (tool creation code) ...
   
   # Refresh tool list (CRITICAL STEP)
   vmcp-sdk list-tools
   ```

3. List prompts in the current vMCP:
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
The vMCP is automatically detected from .vmcp-config.json in the sandbox directory.
You do NOT need to specify the vMCP name or ID - it's handled automatically.

1. Import the SDK:
   ```python
   import vmcp_sdk
   ```

2. Explore tools in the current vMCP (programmatically):
   ```python
   # List all tools
   tools = vmcp_sdk.list_tools()
   for tool in tools:
       print(f"Tool: {tool.get('name')}")
       print(f"  Description: {tool.get('description')}")
       print(f"  Parameters: {tool.get('inputSchema', {}).get('properties', {})}")
   ```

3. List prompts and resources:
   ```python
   prompts = vmcp_sdk.list_prompts()
   resources = vmcp_sdk.list_resources()
   ```

4. Call tools (tools are typed Python functions accessed directly on the module!):
   ```python
   # Tools are automatically converted to Python functions
   # Function names are normalized (e.g., "AllFeature_get_weather" → "all_feature_get_weather")
   # Access tools directly on the vmcp_sdk module - no need to access by vMCP name
   result = vmcp_sdk.all_feature_get_weather(city="Sydney")
   
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
       result = vmcp_sdk.all_feature_get_weather(city="Sydney")
       if result.get("isError"):
           print(f"Error: {result.get('content')}")
       else:
           print(f"Success: {result.get('structuredContent')}")
   except Exception as e:
       print(f"Exception: {e}")
   ```

3. Extracting Results:
   ```python
   result = vmcp_sdk.all_feature_add_numbers(a=5, b=3)
   
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

import vmcp_sdk

def weather_workflow(city: str):
    \"\"\"Get location and weather for a city.\"\"\"
    # Tools are accessed directly on vmcp_sdk module
    # No need to specify vMCP name - it's auto-detected from sandbox config
    
    # Step 1: Get location
    location = vmcp_sdk.all_feature_get_location(city=city)
    print(f"Location: {location}")
    
    # Step 2: Get weather
    weather = vmcp_sdk.all_feature_get_weather(city=city)
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
    
    # Access the tool function directly on vmcp_sdk module
    try:
        tool_func = getattr(vmcp_sdk, normalized_name)
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
   result1 = vmcp_sdk.all_feature_add_numbers(a=15, b=27)
   result2 = vmcp_sdk.all_feature_add(a=10, b=20)
   ```

2. Weather Information Pipeline:
   ```python
   location = vmcp_sdk.all_feature_get_location(city="New York")
   weather = vmcp_sdk.all_feature_get_weather(city="New York")
   ```

3. Data Processing:
   ```python
   time_result = vmcp_sdk.all_feature_get_current_time(timezone_name="UTC")
   data_result = vmcp_sdk.all_feature_process_data(data="sample_data")
   ```

================================================================================
IMPORTANT NOTES FOR CODING AGENTS
================================================================================

1. Always use execute_bash for shell commands and Python execution
3. Use CLI (vmcp-sdk) for EXPLORATION - quick discovery of tools
4. Use SDK (vmcp_sdk) for SCRIPTS - programmatic workflows and automation
5. The SDK and CLI are pre-installed in the sandbox - no installation needed
6. Tool names are normalized: "AllFeature_get_weather" → "all_feature_get_weather"
7. Access tools directly on vmcp_sdk module - no need to specify vMCP name
8. The vMCP is automatically detected from .vmcp-config.json in the sandbox
9. Tools are lazy-loaded - they're created when first accessed
10. Results are dictionaries - always check structure before accessing
11. Create reusable scripts in ~/.vmcp/{vmcp_id} for future use
12. Test tools individually before combining them into workflows
13. Start with CLI exploration, then build SDK scripts based on what you discover

================================================================================
TROUBLESHOOTING
================================================================================

If you encounter issues:

1. Missing packages / ImportError:
   - If you see "package is not installed" or ImportError, install the missing package
   - Example: execute_bash(command=".venv/bin/pip install 'httpx[socks]'")
   - Example: execute_bash(command=".venv/bin/pip install requests")
   - Always check error messages for the exact package name needed
   - Common packages: httpx[socks], requests, pandas, numpy, etc.

2. SDK/CLI not found:
   - The SDK and CLI are pre-installed in the sandbox virtual environment
   - If issues persist, check that you're using the sandbox's Python interpreter
   - Verify `vmcp-sdk` command is available in the sandbox PATH

3. vMCP not found:
   - Ensure you're in a sandbox directory with .vmcp-config.json
   - Verify the sandbox is properly configured with a vmcp_id
   - The vMCP is automatically detected - no need to specify it manually

4. Tool not accessible:
   - Use CLI to see exact names: `vmcp-sdk list-tools`
   - Check tool name normalization (camelCase → snake_case)
   - List tools programmatically: `vmcp_sdk.list_tools()` to see exact names
   - Access tools directly on vmcp_sdk: `vmcp_sdk.tool_name()` or `getattr(vmcp_sdk, "tool_name")`

5. Tool execution errors:
   - Test via CLI first: `vmcp-sdk call-tool --tool <name> --payload '{...}'`
   - Check tool parameters match the schema
   - Verify required parameters are provided
   - Check result.get("isError") for error details
   - If error mentions missing package, install it first

6. CLI vs SDK confusion:
   - Remember: CLI for exploration, SDK for scripts
   - If you need quick info → use CLI
   - If you need automation → use SDK

================================================================================

Remember: You are a coding agent. 

WORKFLOW RECOMMENDATION:
1. Use execute_bash to run CLI commands for EXPLORATION:
   - `vmcp-sdk list-tools` - Explore tools in the current vMCP
   - `vmcp-sdk call-tool --tool <name> --payload '{...}'` - Test tools

2. Use execute_bash to run Python scripts for SDK automation:
   - Create Python scripts with vmcp_sdk imports
   - Run scripts with: execute_bash(command=".venv/bin/python script.py")
   - Combine multiple tools into reusable scripts
   - Save scripts in ~/.vmcp/{vmcp_id} for future use

The CLI is your exploration tool, the SDK is your automation tool. Use both effectively!
"""

    # Setup prompt for SDK-only mode (without CLI)
    SETUP_PROMPT_SDK_ONLY = """You are a coding agent with access to a sandboxed execution environment and the vMCP SDK for interacting with Virtual MCP Servers.

================================================================================
SANDBOX ENVIRONMENT
================================================================================

IMPORTANT: All bash commands and Python code execution MUST be done through the provided tools.
You have access to the execute_bash tool:

1. execute_bash: Execute bash/shell commands in the sandbox

SANDBOX LOCATION:
- All operations execute in: ~/.vmcp/{vmcp_id}
- Working directory: ~/.vmcp/{vmcp_id} (appears as /root/ inside sandbox)
- Files created/modified are stored in this directory

SANDBOX RESTRICTIONS:
- Filesystem: Blocks access to ~/.ssh, ~/.aws, ~/.kube, ~/.config/gcloud
- Network: No network access by default
- Isolation: Complete isolation from the host system

USING execute_bash TOOL:

The execute_bash tool runs any bash/shell command in the sandbox. Use it for ALL file operations and shell commands.

Common operations:
- List files: execute_bash(command="ls -la")
- Create directory: execute_bash(command="mkdir -p mydir")
- Copy files: execute_bash(command="cp source.txt dest.txt")
- Move/rename: execute_bash(command="mv old.txt new.txt")
- Remove files: execute_bash(command="rm file.txt")
- Create files: execute_bash(command="echo 'content' > file.txt")
- View files: execute_bash(command="cat file.txt")
- Find files: execute_bash(command="find . -name '*.py'")
- Check Python version: execute_bash(command=".venv/bin/python --version")
- Install packages: execute_bash(command=".venv/bin/pip install package_name")
- Install packages with extras: execute_bash(command=".venv/bin/pip install 'httpx[socks]'")
- Run Python code: execute_bash(command=".venv/bin/python -c \"print('Hello')\"")
- Run Python scripts: execute_bash(command=".venv/bin/python script.py")

INSTALLING MISSING PACKAGES:
If you encounter ImportError or missing package errors, install the required packages:

1. Basic package installation:
   execute_bash(command=".venv/bin/pip install package_name")

2. Install package with extras (for optional dependencies):
   execute_bash(command=".venv/bin/pip install 'httpx[socks]'")
   execute_bash(command=".venv/bin/pip install 'requests[security]'")

3. Install multiple packages:
   execute_bash(command=".venv/bin/pip install package1 package2 package3")

4. Install from requirements file:
   execute_bash(command=".venv/bin/pip install -r requirements.txt")

5. Common examples:
   - Missing socksio: execute_bash(command=".venv/bin/pip install 'httpx[socks]'")
   - Missing requests: execute_bash(command=".venv/bin/pip install requests")
   - Missing pandas: execute_bash(command=".venv/bin/pip install pandas")

IMPORTANT: Always install missing packages when you see ImportError or "package is not installed" errors.
The sandbox has network access for package installation via pip.

Examples:
Use execute_bash like this:
# Create a directory
execute_bash(command="mkdir -p scripts")

# Copy a file
execute_bash(command="cp template.py script.py")

# List all Python files
execute_bash(command="find . -name '*.py' -type f")

# Check if a file exists
execute_bash(command="test -f script.py && echo 'exists' || echo 'not found'")

# Install a missing package (when you see ImportError)
execute_bash(command=".venv/bin/pip install 'httpx[socks]'")

# Run Python code inline
execute_bash(command=".venv/bin/python -c \"print('Hello, World!')\"")

# Run a Python script
execute_bash(command=".venv/bin/python script.py")

CREATING DYNAMIC TOOLS:
You can create new tools on the fly by saving Python scripts to the `vmcp_tools/` directory. These tools are automatically discovered and made available via the SDK.

1. Create a Python script in `vmcp_tools/`:
   - Must have a `main()` function with type hints for arguments
   - Must have a docstring describing what the tool does
   - Example:
     execute_bash(command="mkdir -p vmcp_tools")
     execute_bash(command="cat > vmcp_tools/my_tool.py << 'EOF'
     def main(name: str, count: int = 1):
         \"\"\"Greet a person multiple times.\"\"\"
         return f'Hello {name}! ' * count
     EOF")

2. Verify the tool is available:
   - Run `vmcp_sdk.list_tools()` to see the new tool (it will appear as `sandbox_tool_my_tool`)
   - Or use CLI: `vmcp-sdk list-tools`

3. Use the tool:
   - Call it like any other SDK tool: `vmcp_sdk.sandbox_tool_my_tool(name="World", count=3)`

WORKFLOW PATTERNS:

1. Create Python script file, then run it:
   # Create script
   execute_bash(command="cat > script.py << 'EOF'\\nimport vmcp_sdk\\nresult = vmcp_sdk.some_tool()\\nprint(result)\\nEOF")
   
   # Run script
   execute_bash(command=".venv/bin/python script.py")

CRITICAL RULES:
- NEVER try to execute bash or python commands directly
- ALWAYS use execute_bash for shell commands
- For Python code, create a script file and run it with execute_bash: execute_bash(command=".venv/bin/python script.py")
- The sandbox Python is at .venv/bin/python
- All file operations must go through execute_bash
- Files are created in ~/.vmcp/{vmcp_id}

================================================================================
vMCP SDK ARCHITECTURE
================================================================================

The vMCP SDK (Virtual Model Context Protocol SDK) is a lightweight Python library that provides a simple, Pythonic interface to interact with vMCPs (Virtual MCP Servers) and their underlying MCP (Model Context Protocol) servers.

KEY CONCEPTS:

1. vMCP (Virtual MCP Server):
   - A virtual configuration that aggregates multiple MCP servers
   - Provides a unified interface to access tools, prompts, and resources from multiple MCP servers
   - Each vMCP has a unique ID (e.g., "1xndemo", "linear", "github")

2. MCP (Model Context Protocol) Server:
   - Individual servers that expose tools, prompts, and resources
   - Examples: Linear, GitHub, Slack, custom servers
   - Multiple MCP servers can be combined into a single vMCP

3. SDK Components:
   - VMCPClient: Core client for interacting with vMCPs
   - Tools are automatically converted to typed Python functions
   - The vMCP is automatically detected from .vmcp-config.json in the sandbox directory

================================================================================
AUTOMATIC vMCP DETECTION
================================================================================

IMPORTANT: The vMCP is automatically detected from the sandbox configuration file (.vmcp-config.json).
You do NOT need to specify the vMCP name or ID anywhere - it's automatically read from the sandbox.

The sandbox directory contains a .vmcp-config.json file with the vmcp_id for this sandbox.
The SDK automatically uses this configuration.

================================================================================
INSTALLATION & SETUP
================================================================================

The SDK is pre-installed in the sandbox virtual environment.
No additional installation is needed - just import and use!

================================================================================
USING THE SDK - BASIC PATTERNS
================================================================================

The SDK automatically works with the vMCP associated with the current sandbox.
The vMCP is automatically detected from .vmcp-config.json in the sandbox directory.
You do NOT need to specify the vMCP name or ID - it's handled automatically.

1. Import the SDK:
   ```python
   import vmcp_sdk
   ```

2. Explore tools in the current vMCP:
   ```python
   # List all tools
   tools = vmcp_sdk.list_tools()
   for tool in tools:
       print(f"Tool: {tool.get('name')}")
       print(f"  Description: {tool.get('description')}")
       print(f"  Parameters: {tool.get('inputSchema', {}).get('properties', {})}")
   ```

3. List prompts and resources:
   ```python
   prompts = vmcp_sdk.list_prompts()
   resources = vmcp_sdk.list_resources()
   ```

4. Call tools (tools are typed Python functions accessed directly on the module!):
   ```python
   # Tools are automatically converted to Python functions
   # Function names are normalized (e.g., "AllFeature_get_weather" → "all_feature_get_weather")
   # Access tools directly on the vmcp_sdk module - no need to access by vMCP name
   result = vmcp_sdk.all_feature_get_weather(city="Sydney")
   
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
       result = vmcp_sdk.all_feature_get_weather(city="Sydney")
       if result.get("isError"):
           print(f"Error: {result.get('content')}")
       else:
           print(f"Success: {result.get('structuredContent')}")
   except Exception as e:
       print(f"Exception: {e}")
   ```

3. Extracting Results:
   ```python
   result = vmcp_sdk.all_feature_add_numbers(a=5, b=3)
   
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

import vmcp_sdk

def weather_workflow(city: str):
    \"\"\"Get location and weather for a city.\"\"\"
    # Tools are accessed directly on vmcp_sdk module
    # No need to specify vMCP name - it's auto-detected from sandbox config
    
    # Step 1: Get location
    location = vmcp_sdk.all_feature_get_location(city=city)
    print(f"Location: {location}")
    
    # Step 2: Get weather
    weather = vmcp_sdk.all_feature_get_weather(city=city)
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
   result1 = vmcp_sdk.all_feature_add_numbers(a=15, b=27)
   result2 = vmcp_sdk.all_feature_add(a=10, b=20)
   ```

2. Weather Information Pipeline:
   ```python
   location = vmcp_sdk.all_feature_get_location(city="New York")
   weather = vmcp_sdk.all_feature_get_weather(city="New York")
   ```

3. Data Processing:
   ```python
   time_result = vmcp_sdk.all_feature_get_current_time(timezone_name="UTC")
   data_result = vmcp_sdk.all_feature_process_data(data="sample_data")
   ```

================================================================================
IMPORTANT NOTES FOR CODING AGENTS
================================================================================

1. Always use execute_bash for shell commands and Python execution
3. Use the SDK (vmcp_sdk) for programmatic workflows and automation
4. The SDK is pre-installed in the sandbox - no installation needed
5. Tool names are normalized: "AllFeature_get_weather" → "all_feature_get_weather"
6. Access tools directly on vmcp_sdk module - no need to specify vMCP name
7. The vMCP is automatically detected from .vmcp-config.json in the sandbox
8. Tools are lazy-loaded - they're created when first accessed
9. Results are dictionaries - always check structure before accessing
10. Create reusable scripts in ~/.vmcp/{vmcp_id} for future use
11. Test tools individually before combining them into workflows

================================================================================
TROUBLESHOOTING
================================================================================

If you encounter issues:

1. Missing packages / ImportError:
   - If you see "package is not installed" or ImportError, install the missing package
   - Example: execute_bash(command=".venv/bin/pip install 'httpx[socks]'")
   - Example: execute_bash(command=".venv/bin/pip install requests")
   - Always check error messages for the exact package name needed
   - Common packages: httpx[socks], requests, pandas, numpy, etc.

2. SDK not found:
   - The SDK is pre-installed in the sandbox virtual environment
   - If issues persist, check that you're using the sandbox's Python interpreter

3. vMCP not found:
   - Ensure you're in a sandbox directory with .vmcp-config.json
   - Verify the sandbox is properly configured with a vmcp_id
   - The vMCP is automatically detected - no need to specify it manually

4. Tool not accessible:
   - Check tool name normalization (camelCase → snake_case)
   - List tools programmatically: `vmcp_sdk.list_tools()` to see exact names
   - Access tools directly on vmcp_sdk: `vmcp_sdk.tool_name()` or `getattr(vmcp_sdk, "tool_name")`

5. Tool execution errors:
   - Check tool parameters match the schema
   - Verify required parameters are provided
   - Check result.get("isError") for error details
   - If error mentions missing package, install it first

================================================================================

Remember: You are a coding agent. 

Use execute_bash to run Python scripts for SDK automation:
- Create Python scripts with vmcp_sdk imports
- Run scripts with: execute_bash(command=".venv/bin/python script.py")
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
    
    # Default packages to install in all sandboxes
    DEFAULT_SANDBOX_PACKAGES = [
        # HTTP/Network
        "httpx[socks]",      # For SOCKS proxy support in MCP clients
        "requests",          # Common HTTP library
        "aiohttp",           # Async HTTP client/server

        # Data Processing
        "pandas",            # Data manipulation and analysis
        "numpy",             # Numerical computing

        # Web Scraping & Parsing
        "beautifulsoup4",    # HTML/XML parsing
        "lxml",              # Fast XML/HTML parser

        # Data Formats
        "pyyaml",            # YAML parsing
        "python-dotenv",     # Environment variable management

        # Utilities
        "pydantic",          # Data validation using Python type annotations
        "jinja2",            # Templating engine
        "markdown",          # Markdown processing
        "pillow",            # Image processing
        "openpyxl",          # Excel file reading/writing
    ]

    def _ensure_pip_installed(self, venv_python: Path) -> bool:
        """
        Ensure pip is installed in the virtual environment.
        
        Args:
            venv_python: Path to the Python executable in the venv
            
        Returns:
            True if pip is available, False otherwise
        """
        try:
            # Check if pip is already available
            result = subprocess.run(
                [str(venv_python), "-m", "pip", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.debug("pip is already available in venv")
                return True
            
            # If pip is not available, install it using ensurepip
            logger.info("Installing pip in virtual environment")
            result = subprocess.run(
                [str(venv_python), "-m", "ensurepip", "--upgrade"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to install pip: {result.stderr}")
                return False
            
            logger.info("Successfully installed pip in virtual environment")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("Timeout installing pip")
            return False
        except Exception as e:
            logger.error(f"Error ensuring pip is installed: {e}", exc_info=True)
            return False

    def _install_default_packages(self, venv_python: Path, uv_cmd: Optional[str] = None) -> bool:
        """
        Install default packages in the sandbox virtual environment.
        
        Args:
            venv_python: Path to the Python executable in the venv
            uv_cmd: Optional uv command path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.DEFAULT_SANDBOX_PACKAGES:
                return True
            
            logger.info(f"Installing default packages: {', '.join(self.DEFAULT_SANDBOX_PACKAGES)}")
            
            if uv_cmd:
                result = subprocess.run(
                    [uv_cmd, "pip", "install"] + self.DEFAULT_SANDBOX_PACKAGES + ["--python", str(venv_python)],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            else:
                result = subprocess.run(
                    [str(venv_python), "-m", "pip", "install"] + self.DEFAULT_SANDBOX_PACKAGES,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            
            if result.returncode != 0:
                logger.error(f"Failed to install default packages: {result.stderr}")
                return False
            
            logger.info("Installed default packages")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("Timeout installing default packages")
            return False
        except Exception as e:
            logger.error(f"Error installing default packages: {e}", exc_info=True)
            return False
    
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
            
            # Ensure pip is installed in the virtual environment
            if not self._ensure_pip_installed(venv_python):
                logger.error("Failed to ensure pip is installed in venv")
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
            
            # Install default packages
            if not self._install_default_packages(venv_python, uv_cmd):
                logger.warning("Failed to install default packages, but continuing...")
            
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
            
            # Ensure pip is installed in the virtual environment
            if not self._ensure_pip_installed(venv_python):
                logger.error("Failed to ensure pip is installed in venv")
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
            
            # Install default packages
            if not self._install_default_packages(venv_python, uv_cmd):
                logger.warning("Failed to install default packages, but continuing...")
            
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
            if not sandbox_path.exists():
                logger.info(f"Sandbox directory does not exist: {sandbox_path}")
                return True  # Consider it successful if it doesn't exist
            
            logger.info(f"Deleting sandbox directory: {sandbox_path}")
            
            # Use shutil.rmtree with error handling for locked files
            # On Windows, files might be locked, so we use onerror handler
            def handle_remove_readonly(func, path, exc):
                """
                Handle permission errors when deleting files.
                On Windows, files might be read-only.
                """
                import stat
                if func in (os.unlink, os.remove) and os.path.exists(path):
                    # Change file permissions to allow deletion
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                elif func == os.rmdir:
                    # Try to remove directory again
                    try:
                        os.rmdir(path)
                    except OSError:
                        pass
            
            # Delete the directory tree
            shutil.rmtree(sandbox_path, onerror=handle_remove_readonly)
            
            # Verify deletion
            if sandbox_path.exists():
                logger.warning(f"Sandbox directory still exists after deletion attempt: {sandbox_path}")
                # Try one more time with force
                try:
                    import stat
                    # Make all files writable
                    for root, dirs, files in os.walk(sandbox_path):
                        for d in dirs:
                            os.chmod(os.path.join(root, d), stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
                        for f in files:
                            os.chmod(os.path.join(root, f), stat.S_IWRITE | stat.S_IREAD)
                    shutil.rmtree(sandbox_path, onerror=handle_remove_readonly)
                except Exception as e2:
                    logger.error(f"Failed to force delete sandbox directory: {e2}")
                    return False
            
            # Final verification
            if sandbox_path.exists():
                logger.error(f"Failed to delete sandbox directory: {sandbox_path} still exists")
                return False
            
            logger.info(f"Successfully deleted sandbox directory: {sandbox_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting sandbox for {vmcp_id}: {e}", exc_info=True)
            return False
    
    def _get_execute_python_tool(self, sandbox_path_str: str) -> Dict[str, Any]:
        """
        Get execute_python tool definition (not surfaced, but kept for reference).
        
        Args:
            sandbox_path_str: String path to sandbox directory
            
        Returns:
            Tool definition dictionary
        """
        return {
            "name": "execute_python",
            "description": "Execute Python code in a sandboxed environment.",
            "text": f"The Python code will be executed in a sandboxed environment. The sandbox directory appears as /root/ to the LLM (e.g., 'os.getcwd()' returns /root). The actual sandbox is located at {sandbox_path_str} with filesystem and network restrictions applied. The sandbox prevents access to sensitive directories and restricts network access.",
            "tool_type": "python",
            "code": f"""
import asyncio
import os
import subprocess
from pathlib import Path
from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig

SANDBOX_DIR = Path("{sandbox_path_str}")

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
    # Use deny-by-default (whitelist) approach - only allow sandbox directory + minimal system paths
    # This matches the Seatbelt profile pattern: (deny default) then allow specific paths
    sandbox_dir_str = str(SANDBOX_DIR)
    
    # Allow reads only from:
    # 1. The sandbox directory itself
    # 2. Minimal system paths needed for the process to run
    allow_read_paths = [
        sandbox_dir_str,
        "/usr/lib",           # System libraries (Linux/macOS)
        "/System/Library",    # macOS system libraries
        "/Library/Frameworks", # macOS frameworks
        "/usr/bin",           # System binaries (needed for Python, etc.)
        "/bin",               # Core system binaries
        "/lib",               # Core system libraries
        "/lib64",             # 64-bit libraries (Linux)
    ]
    
    sandbox_config = SandboxRuntimeConfig.from_json({{
        "network": {{
            "allowedDomains": [],
            "deniedDomains": []
        }},
        "filesystem": {{
            "allowRead": allow_read_paths,
            "allowWrite": [
                sandbox_dir_str
            ],
            "denyWrite": []
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
            bin_shell="bash"
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

    def get_sandbox_tools(self, vmcp_id: str) -> List[Dict[str, Any]]:
        """
        Get sandbox tool definitions to inject into vMCP.
        Includes base tools (execute_bash) and dynamically discovered tools.
        Note: execute_python tool is kept in _get_execute_python_tool() but not surfaced.
        
        Args:
            vmcp_id: The vMCP ID
            
        Returns:
            List of tool definitions
        """
        sandbox_path = self.get_sandbox_path(vmcp_id)
        sandbox_path_str = str(sandbox_path)
        
        # Base sandbox tools (execute_python is not included but kept in _get_execute_python_tool())
        base_tools = [
            {
                "name": "execute_bash",
                "description": "TO RUN BASH TOOLS ALWAYS USE THIS TOOL. DO NOT EXECUTE BASH COMMANDS DIRECTLY. Execute a bash command in a sandboxed environment.",
                "text": f"The command will be executed in a sandboxed environment. The sandbox directory appears as /root/ to the LLM (e.g., 'pwd' returns /root). The actual sandbox is located at {sandbox_path_str} with filesystem and network restrictions applied. The sandbox prevents access to sensitive directories like ~/.ssh, ~/.aws, and restricts network access.",
                "tool_type": "python",
                "code": f"""
import asyncio
import os
import subprocess
from pathlib import Path
from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig

SANDBOX_DIR = Path("{sandbox_path_str}")

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
    # Use deny-by-default (whitelist) approach - only allow sandbox directory + minimal system paths
    # This matches the Seatbelt profile pattern: (deny default) then allow specific paths
    sandbox_dir_str = str(SANDBOX_DIR)
    
    # Allow reads only from:
    # 1. The sandbox directory itself
    # 2. Minimal system paths needed for the process to run
    allow_read_paths = [
        sandbox_dir_str,
        "/usr/lib",           # System libraries (Linux/macOS)
        "/System/Library",    # macOS system libraries
        "/Library/Frameworks", # macOS frameworks
        "/usr/bin",           # System binaries (needed for Python, etc.)
        "/bin",               # Core system binaries
        "/lib",               # Core system libraries
        "/lib64",             # 64-bit libraries (Linux)
    ]
    
    sandbox_config = SandboxRuntimeConfig.from_json({{
        "network": {{
            "allowedDomains": [],
            "deniedDomains": []
        }},
        "filesystem": {{
            "allowRead": allow_read_paths,
            "allowWrite": [
                sandbox_dir_str
            ],
            "denyWrite": []
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
            bin_shell="bash"
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
            }
        ]
        
        # Discover dynamic tools from vmcp_tools/ directory
        try:
            registry = SandboxToolRegistry(sandbox_path, vmcp_id)
            discovered_tools = registry.discover_tools()
            base_tools.extend(discovered_tools)
            logger.debug(f"Discovered {len(discovered_tools)} tools from sandbox for {vmcp_id}")
        except Exception as e:
            logger.warning(f"Failed to discover sandbox tools for {vmcp_id}: {e}")
        
        return base_tools
    
    def get_sandbox_prompt(self, vmcp_id: str, vmcp_config=None) -> str:
        """
        Get sandbox setup prompt to inject into vMCP.
        
        Returns different prompts based on configuration:
        - If progressive discovery is enabled: Returns prompt with CLI instructions
        - Otherwise: Returns SDK-only prompt
        
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
        
        # Select prompt based on progressive discovery setting
        if progressive_discovery_enabled:
            prompt = self.SETUP_PROMPT_SDK_ONLY #to self.SETUP_PROMPT_PROGRESSIVE_DISCOVERY
        else:
            prompt = self.SETUP_PROMPT_SDK_ONLY
        
        return prompt.replace("{vmcp_id}", vmcp_id)


class SandboxToolRegistry:
    """
    Discovers and manages Python scripts from sandbox as dynamic tools.
    Tools are stored in vmcp_tools/ directory and discovered on-demand.
    """
    
    def __init__(self, sandbox_path: Path, vmcp_id: str):
        self.sandbox_path = sandbox_path
        self.vmcp_id = vmcp_id
        self.tools_dir = sandbox_path / "vmcp_tools"
        self.registry_file = sandbox_path / "vmcp_tool_registry.json"
    
    def ensure_tools_directory(self) -> None:
        """Create tools directory if it doesn't exist."""
        self.tools_dir.mkdir(parents=True, exist_ok=True)
    
    def discover_tools(self) -> List[Dict[str, Any]]:
        """
        Scan vmcp_tools/ directory for Python scripts and convert to tool definitions.
        
        Returns:
            List of tool definition dictionaries compatible with custom_tools format
        """
        self.ensure_tools_directory()
        tools = []
        
        # Load registry for metadata (name, description overrides)
        registry = self._load_registry()
        
        # Scan for Python scripts
        for script_file in sorted(self.tools_dir.glob("*.py")):
            tool_def = self._parse_script_as_tool(script_file, registry)
            if tool_def:
                tools.append(tool_def)
        
        return tools
    
    def _load_registry(self) -> Dict[str, Any]:
        """Load tool registry JSON file with metadata."""
        if not self.registry_file.exists():
            return {}
        
        try:
            import json
            with open(self.registry_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load tool registry: {e}")
            return {}
    
    def _save_registry(self, registry: Dict[str, Any]) -> None:
        """Save tool registry JSON file."""
        import json
        with open(self.registry_file, 'w') as f:
            json.dump(registry, f, indent=2)
    
    def _parse_script_as_tool(
        self, 
        script_path: Path, 
        registry: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Parse Python script to extract tool definition.
        
        Looks for:
        - main() function with type hints for parameters
        - Docstring for description
        - Registry metadata for name/description overrides
        
        Returns:
            Tool definition dict or None if script is invalid
        """
        try:
            import ast
            
            # Read script content
            script_content = script_path.read_text(encoding='utf-8')
            
            # Parse AST to find main function
            tree = ast.parse(script_content)
            
            main_func = None
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == 'main':
                    main_func = node
                    break
            
            if not main_func:
                logger.debug(f"No main() function found in {script_path.name}")
                return None
            
            # Extract function signature
            tool_name = script_path.stem  # filename without .py
            description = ast.get_docstring(main_func) or f"Tool: {tool_name}"
            
            # Check registry for overrides
            if tool_name in registry:
                if 'name' in registry[tool_name]:
                    tool_name = registry[tool_name]['name']
                if 'description' in registry[tool_name]:
                    description = registry[tool_name]['description']
            
            # Extract parameters from function signature
            variables = []
            required_params = []
            
            for arg in main_func.args.args:
                if arg.arg == 'self':
                    continue
                
                param_name = arg.arg
                param_type = 'str'  # default
                
                # Extract type hint if available
                if arg.annotation:
                    if isinstance(arg.annotation, ast.Name):
                        type_name = arg.annotation.id
                        type_mapping = {
                            'str': 'str',
                            'int': 'int',
                            'float': 'float',
                            'bool': 'bool',
                            'list': 'list',
                            'dict': 'dict'
                        }
                        param_type = type_mapping.get(type_name, 'str')
                
                # Check if has default (optional parameter)
                has_default = len(main_func.args.defaults) > 0 and \
                             len(main_func.args.args) - len(main_func.args.defaults) <= \
                             main_func.args.args.index(arg)
                
                if not has_default:
                    required_params.append(param_name)
                
                variables.append({
                    'name': param_name,
                    'description': f"Parameter: {param_name}",
                    'type': param_type,
                    'required': not has_default
                })
            
            # Create tool definition
            # Read full script content for code field
            tool_def = {
                'name': f"sandbox_tool_{tool_name}",
                'description': description,
                'tool_type': 'python',
                'code': script_content,  # Full script content
                'variables': variables,
                'environment_variables': [],
                'tool_calls': [],
                'meta': {
                    'source': 'sandbox_discovered',
                    'script_path': str(script_path.relative_to(self.sandbox_path)),
                    'vmcp_id': self.vmcp_id
                }
            }
            
            return tool_def
            
        except Exception as e:
            logger.warning(f"Failed to parse script {script_path}: {e}")
            return None
    
    def register_tool_metadata(
        self, 
        tool_name: str, 
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> bool:
        """
        Register metadata for a tool (name/description overrides).
        Updates vmcp_tool_registry.json.
        """
        registry = self._load_registry()
        
        if tool_name not in registry:
            registry[tool_name] = {}
        
        if name:
            registry[tool_name]['name'] = name
        if description:
            registry[tool_name]['description'] = description
        
        self._save_registry(registry)
        return True


class WorkflowManager:
    """
    Manages scheduled workflows in sandbox.
    Workflows are Python scripts stored in vmcp_workflows/ directory.
    Schedule is stored in vmcp_workflow_schedule.json.
    """
    
    def __init__(self, sandbox_path: Path, vmcp_id: str):
        self.sandbox_path = sandbox_path
        self.vmcp_id = vmcp_id
        self.workflows_dir = sandbox_path / "vmcp_workflows"
        self.schedule_file = sandbox_path / "vmcp_workflow_schedule.json"
    
    def ensure_workflows_directory(self) -> None:
        """Create workflows directory if it doesn't exist."""
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
    
    def register_workflow(
        self,
        script_path: str,
        schedule: str,
        workflow_name: Optional[str] = None,
        enabled: bool = True
    ) -> bool:
        """
        Register a workflow script with schedule.
        
        Args:
            script_path: Path to Python script (relative to sandbox or absolute)
            schedule: Schedule expression - "once", "hourly", "daily", or cron expression
            workflow_name: Optional name for workflow (defaults to script filename)
            enabled: Whether workflow is enabled
        
        Returns:
            True if successful
        """
        self.ensure_workflows_directory()
        
        # Resolve script path
        script_file = Path(script_path)
        if not script_file.is_absolute():
            script_file = self.sandbox_path / script_path
        
        if not script_file.exists():
            raise FileNotFoundError(f"Workflow script not found: {script_path}")
        
        # Copy script to workflows directory
        workflow_filename = script_file.name
        target_path = self.workflows_dir / workflow_filename
        
        import shutil
        shutil.copy2(script_file, target_path)
        
        # Use provided name or derive from filename
        if not workflow_name:
            workflow_name = script_file.stem
        
        # Load schedule
        schedule_data = self._load_schedule()
        
        # Add/update workflow in schedule
        workflow_id = f"{self.vmcp_id}_{workflow_name}"
        from datetime import datetime
        schedule_data[workflow_id] = {
            'vmcp_id': self.vmcp_id,
            'workflow_name': workflow_name,
            'script_path': str(target_path.relative_to(self.sandbox_path)),
            'schedule': schedule,
            'enabled': enabled,
            'created_at': datetime.now().isoformat(),
            'last_run': None,
            'next_run': None
        }
        
        self._save_schedule(schedule_data)
        logger.info(f"Registered workflow: {workflow_name} with schedule: {schedule}")
        return True
    
    def list_workflows(self) -> List[Dict[str, Any]]:
        """List all registered workflows."""
        schedule_data = self._load_schedule()
        
        # Filter workflows for this vmcp_id
        workflows = []
        for _workflow_id, workflow_data in schedule_data.items():
            if workflow_data.get('vmcp_id') == self.vmcp_id:
                workflows.append(workflow_data)
        
        return workflows
    
    def _load_schedule(self) -> Dict[str, Any]:
        """Load workflow schedule JSON file."""
        if not self.schedule_file.exists():
            return {}
        
        try:
            import json
            with open(self.schedule_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load workflow schedule: {e}")
            return {}
    
    def _save_schedule(self, schedule: Dict[str, Any]) -> None:
        """Save workflow schedule JSON file."""
        import json
        with open(self.schedule_file, 'w') as f:
            json.dump(schedule, f, indent=2)


# Singleton instance
_sandbox_service: Optional[SandboxService] = None


def get_sandbox_service() -> SandboxService:
    """Get the singleton sandbox service instance."""
    global _sandbox_service
    if _sandbox_service is None:
        _sandbox_service = SandboxService()
    return _sandbox_service

