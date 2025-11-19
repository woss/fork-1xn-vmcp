# Setup and Testing Guide

## Quick Start with uv (Recommended)

`uv` is a fast Python package installer and resolver. It's much faster than pip!

### 1. Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or on macOS with Homebrew:
```bash
brew install uv
```

### 2. Create Virtual Environment and Install

```bash
cd sandbox-runtime-py

# Create virtual environment with uv
uv venv

# Activate the virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package in development mode
uv pip install -e .

# Install development dependencies
uv pip install -r requirements-dev.txt
```

### Alternative: One-liner with uv

```bash
# Create venv and install everything in one go
uv venv && source .venv/bin/activate && uv pip install -e ".[dev]"
```

## Quick Start with Standard Python

### 1. Install Dependencies

```bash
cd sandbox-runtime-py

# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package in development mode
pip install -e .

# Or install dependencies only
pip install -r requirements.txt
```

### 2. Install Development Dependencies (for testing)

```bash
pip install -r requirements-dev.txt
```

## Verify Installation

```bash
# Check if the CLI is available
srt --version

# Or run directly with Python
python -m sandbox_runtime.cli --version
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_config_validation.py
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Coverage

```bash
uv pip install pytest-cov  # or: pip install pytest-cov
pytest --cov=sandbox_runtime --cov-report=html
```

## Testing the CLI

### Basic Usage

```bash
# Run a simple command
srt echo "Hello, World!"

# With debug logging
srt --debug echo "Hello, World!"

# Run a command that needs network access (will be blocked without config)
srt curl https://example.com
```

### Create a Test Configuration

Create `~/.srt-settings.json`:

```json
{
  "network": {
    "allowedDomains": ["example.com", "*.github.com"],
    "deniedDomains": []
  },
  "filesystem": {
    "denyRead": ["~/.ssh"],
    "allowWrite": ["."],
    "denyWrite": []
  }
}
```

### Test Network Restrictions

```bash
# This should work (if example.com is in allowedDomains)
srt curl https://example.com

# This should be blocked
srt curl https://blocked-site.com
```

### Test Filesystem Restrictions

```bash
# This should work (current directory is allowed)
srt cat README.md

# This should be blocked (if ~/.ssh is in denyRead)
srt cat ~/.ssh/id_rsa
```

## Testing as a Library

Run the test script:

```bash
python test_library.py
```

Or create your own test:

```python
import asyncio
from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig

async def main():
    # Create a test configuration
    config = SandboxRuntimeConfig.from_json({
        "network": {
            "allowedDomains": ["example.com"],
            "deniedDomains": []
        },
        "filesystem": {
            "denyRead": [],
            "allowWrite": ["."],
            "denyWrite": []
        }
    })
    
    # Initialize the sandbox
    await SandboxManager.initialize(config)
    
    # Wrap a command
    command = "echo 'Hello from sandbox'"
    sandboxed = await SandboxManager.wrap_with_sandbox(command)
    print(f"Sandboxed command: {sandboxed}")
    
    # Cleanup
    await SandboxManager.reset()

if __name__ == "__main__":
    asyncio.run(main())
```

## Platform-Specific Testing

### macOS Testing

```bash
# Check dependencies
which rg  # Should show ripgrep path

# Test macOS sandbox
srt --debug echo "Testing macOS sandbox"
```

### Linux Testing

```bash
# Check dependencies
which bwrap  # Should show bubblewrap path
which socat  # Should show socat path
which rg     # Should show ripgrep path

# Test Linux sandbox
srt --debug echo "Testing Linux sandbox"
```

## Troubleshooting

### Import Errors

If you get import errors, make sure you're in the virtual environment and the package is installed:

```bash
# With uv
uv pip install -e .

# With pip
pip install -e .
```

### Missing Dependencies

Check platform-specific dependencies:

**macOS:**
```bash
brew install ripgrep
```

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install bubblewrap socat ripgrep

# Fedora/RHEL
sudo dnf install bubblewrap socat ripgrep
```

### Configuration Errors

Check your config file syntax:
```bash
python -c "import json; json.load(open('~/.srt-settings.json'))"
```

## Development Workflow

1. Make changes to the code
2. Run tests: `pytest`
3. Check types: `mypy sandbox_runtime` (if installed)
4. Format code: `black sandbox_runtime` (if installed)
5. Lint code: `ruff check sandbox_runtime` (if installed)
6. Test CLI: `srt --debug echo "test"`

## Using uv for Development

`uv` makes development faster:

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests
uv run pytest

# Run the CLI
uv run srt --version

# Run your test script
uv run python test_library.py
```
