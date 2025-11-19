# vMCP SDK Example Workflows

This directory contains example scripts demonstrating how to use the vMCP SDK to combine multiple tools into workflows.

## Prerequisites

1. Install the SDK in editable mode:
   ```bash
   cd /path/to/oss/backend
   uv pip install -e .
   ```

2. Set the active vMCP (optional):
   ```python
   from vmcp_sdk.active_vmcp import ActiveVMCPManager
   ActiveVMCPManager().set_active_vmcp("1xndemo")
   ```

## Example Scripts

### 1. `explore_tools.py` - Tool Explorer

Explores available tools in a vMCP and shows their signatures.

```bash
python examples/explore_tools.py [vmcp_name]
```

**Example:**
```bash
python examples/explore_tools.py 1xndemo
```

### 2. `weather_workflow.py` - Weather Information Pipeline

Combines location and weather tools to get complete weather information.

```bash
python examples/weather_workflow.py [city_name]
```

**Example:**
```bash
python examples/weather_workflow.py Sydney
python examples/weather_workflow.py "New York"
```

**Workflow:**
1. Gets location coordinates for a city
2. Gets weather information for that location
3. Generates a summary

### 3. `math_workflow.py` - Mathematical Operations

Demonstrates combining multiple math tools.

```bash
python examples/math_workflow.py
```

**Workflow:**
1. Adds two numbers using `add_numbers` tool
2. Uses alternative `add` tool
3. Calculates average of multiple numbers

### 4. `data_processing_workflow.py` - Data Processing Pipeline

Combines time, data processing, and creative generation tools.

```bash
python examples/data_processing_workflow.py
```

**Workflow:**
1. Gets current time in a timezone
2. Processes data with logging
3. Generates a creative poem

## Using the SDK in Your Own Scripts

### Basic Usage

```python
import vmcp_sdk

# Access a vMCP (for names starting with numbers, use getattr)
demo = getattr(vmcp_sdk, "1xndemo")

# List tools
tools = demo.list_tools()

# Call a tool (tools are typed functions!)
result = demo.all_feature_add_numbers(a=5, b=3)
print(result)
```

### Combining Multiple Tools

```python
import vmcp_sdk

demo = getattr(vmcp_sdk, "1xndemo")

# Step 1: Get location
location = demo.all_feature_get_location(city="Sydney")

# Step 2: Get weather using the location
weather = demo.all_feature_get_weather(city="Sydney")

# Step 3: Process results
print(f"Weather in Sydney: {weather}")
```

### Error Handling

```python
import vmcp_sdk

try:
    demo = getattr(vmcp_sdk, "1xndemo")
    result = demo.all_feature_get_weather(city="Sydney")
    print(result)
except Exception as e:
    print(f"Error: {e}")
```

## Running Examples

All examples can be run directly:

```bash
# From the backend directory
cd /path/to/oss/backend

# Run with Python
python examples/explore_tools.py
python examples/weather_workflow.py
python examples/math_workflow.py
python examples/data_processing_workflow.py

# Or with uv
uv run python examples/explore_tools.py
uv run python examples/weather_workflow.py
```

## Notes

- Tools are automatically converted to typed Python functions
- Function names are normalized (e.g., `AllFeature_get_weather` → `all_feature_get_weather`)
- Results include both text content and structured data
- All tools are async internally but exposed as sync functions

