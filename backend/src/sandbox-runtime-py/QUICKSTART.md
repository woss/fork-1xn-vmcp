# Quick Start Guide

## Setup with uv (Fastest Method)

```bash
cd sandbox-runtime-py

# Create virtual environment and install
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Verify Installation

```bash
# Check CLI version
srt --version

# Run tests
pytest

# Test the library
python test_library.py
```

## Basic Usage

### 1. Simple Command

```bash
srt echo "Hello, World!"
```

### 2. With Debug Logging

```bash
srt --debug echo "Hello, World!"
```

### 3. Create Configuration

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

### 4. Test Network Restrictions

```bash
# Allowed domain
srt curl https://example.com

# Blocked domain (will show error)
srt curl https://blocked-site.com
```

### 5. Test Filesystem Restrictions

```bash
# Allowed path
srt cat README.md

# Blocked path (if configured)
srt cat ~/.ssh/id_rsa
```

## Using as a Library

```python
import asyncio
from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig

async def main():
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
    
    await SandboxManager.initialize(config)
    sandboxed = await SandboxManager.wrap_with_sandbox("echo 'test'")
    print(sandboxed)
    await SandboxManager.reset()

asyncio.run(main())
```

## Platform Requirements

### macOS
- `ripgrep` (rg): `brew install ripgrep`

### Linux
- `bubblewrap` (bwrap): `apt-get install bubblewrap` or `dnf install bubblewrap`
- `socat`: `apt-get install socat` or `dnf install socat`
- `ripgrep` (rg): `apt-get install ripgrep` or `dnf install ripgrep`

## Troubleshooting

**Import errors?** Make sure virtual environment is activated:
```bash
source .venv/bin/activate
```

**Missing dependencies?** Install platform-specific tools (see above)

**Config errors?** Check JSON syntax:
```bash
python -c "import json; json.load(open('~/.srt-settings.json'))"
```

