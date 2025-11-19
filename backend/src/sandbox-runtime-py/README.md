# Anthropic Sandbox Runtime (srt) - Python

A lightweight sandboxing tool for enforcing filesystem and network restrictions on arbitrary processes at the OS level, without requiring a container.

`srt` uses native OS sandboxing primitives (`sandbox-exec` on macOS, `bubblewrap` on Linux) and proxy-based network filtering. It can be used to sandbox the behaviour of AI agents, local MCP servers, bash commands and arbitrary processes.

> **Beta Research Preview**
>
> The Sandbox Runtime is a research preview developed for [Claude Code](https://www.claude.com/product/claude-code) to enable safer AI agents. It's being made available as an early open source preview to help the broader ecosystem build more secure agentic systems. As this is an early research preview, APIs and configuration formats may evolve. We welcome feedback and contributions to make AI agents safer by default!

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/anthropic-experimental/sandbox-runtime.git
cd sandbox-runtime-py

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e .

# Or install dependencies only
pip install -r requirements.txt
```

### Using uv (Recommended)

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
cd sandbox-runtime-py
uv venv
source .venv/bin/activate
uv pip install -e .
```

### From PyPI (when published)

```bash
pip install sandbox-runtime
```

## Requirements

- Python 3.10 or higher
- Platform-specific dependencies:
  - **macOS**: `ripgrep` (rg) - Install via Homebrew: `brew install ripgrep`
  - **Linux**: 
    - `bubblewrap` (bwrap) - `apt-get install bubblewrap` or `dnf install bubblewrap`
    - `socat` - `apt-get install socat` or `dnf install socat`
    - `ripgrep` (rg) - `apt-get install ripgrep` or `dnf install ripgrep`

## Basic Usage

### As a CLI Tool

```bash
# Network restrictions
$ srt "curl anthropic.com"
Running: curl anthropic.com
<html>...</html>  # Request succeeds

$ srt "curl example.com"
Running: curl example.com
Connection blocked by network allowlist  # Request blocked

# Filesystem restrictions
$ srt "cat README.md"
Running: cat README.md
# Anthropic Sandb...  # Current directory access allowed

$ srt "cat ~/.ssh/id_rsa"
Running: cat ~/.ssh/id_rsa
cat: /Users/ollie/.ssh/id_rsa: Operation not permitted  # Specific file blocked
```

### As a Python SDK

```python
import asyncio
import subprocess
from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig

async def main():
    # Define your sandbox configuration
    config = SandboxRuntimeConfig.from_json({
        "network": {
            "allowedDomains": ["example.com", "api.github.com"],
            "deniedDomains": []
        },
        "filesystem": {
            "denyRead": ["~/.ssh"],
            "allowWrite": [".", "/tmp"],
            "denyWrite": [".env"]
        }
    })

    # Initialize the sandbox (starts proxy servers, etc.)
    await SandboxManager.initialize(config)
    
    try:
        # Wrap a command with sandbox restrictions
        sandboxed_command = await SandboxManager.wrap_with_sandbox("curl https://example.com")
        
        # Execute the sandboxed command
        result = subprocess.run(sandboxed_command, shell=True, capture_output=True, text=True)
        print(result.stdout)
    finally:
        # Cleanup when done (optional, happens automatically on process exit)
        await SandboxManager.reset()

asyncio.run(main())
```

## Overview

This package provides a standalone sandbox implementation that can be used as both a CLI tool and a library. It's designed with a **secure-by-default** philosophy tailored for common developer use cases: processes start with minimal access, and you explicitly poke only the holes you need.

**Key capabilities:**

- **Network restrictions**: Control which hosts/domains can be accessed via HTTP/HTTPS and other protocols
- **Filesystem restrictions**: Control which files/directories can be read/written
- **Unix socket restrictions**: Control access to local IPC sockets
- **Violation monitoring**: On macOS, tap into the system's sandbox violation log store for real-time alerts

### Example Use Case: Sandboxing AI Coding Agents

A key use case is sandboxing AI coding agents to restrict their capabilities while allowing them to execute code, create files, and run commands safely. See the [Example Coding Agents](#example-coding-agents) section below for complete working examples.

## Usage

### CLI Usage

The `srt` command (Anthropic Sandbox Runtime) wraps any command with security boundaries:

```bash
# Run a command in the sandbox
srt echo "hello world"

# With debug logging
srt --debug curl https://example.com

# Specify custom settings file
srt --settings /path/to/srt-settings.json python script.py

# Run Python script in sandbox
srt "python my_script.py"
```

### SDK Usage

#### Basic Example

```python
import asyncio
from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig

async def main():
    config = SandboxRuntimeConfig.from_json({
        "network": {
            "allowedDomains": ["github.com", "*.github.com"],
            "deniedDomains": []
        },
        "filesystem": {
            "denyRead": [],
            "allowWrite": ["."],
            "denyWrite": []
        }
    })
    
    await SandboxManager.initialize(config)
    
    # Execute sandboxed command
    command = await SandboxManager.wrap_with_sandbox("python script.py")
    # ... execute command ...
    
    await SandboxManager.reset()

asyncio.run(main())
```

#### Advanced Example with Custom Config

```python
import asyncio
import subprocess
from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig

async def execute_sandboxed(command: str, custom_config: dict = None):
    """Execute a command in a sandbox with optional custom config."""
    # Base configuration
    base_config = SandboxRuntimeConfig.from_json({
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
    
    await SandboxManager.initialize(base_config)
    
    try:
        # Use custom config if provided, otherwise use base config
        if custom_config:
            wrapped = await SandboxManager.wrap_with_sandbox(
                command,
                None,  # bin_shell
                custom_config
            )
        else:
            wrapped = await SandboxManager.wrap_with_sandbox(command)
        
        result = subprocess.run(
            wrapped,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    finally:
        await SandboxManager.reset()

# Usage
result = asyncio.run(execute_sandboxed("python my_script.py"))
print(result["stdout"])
```

## Example Coding Agents

We've created example coding agents that demonstrate how to use the Python Sandbox Runtime SDK to build secure AI agents. These examples are located in the `../coding-agents/` directory (outside the sandbox-runtime-py folder).

### Available Examples

1. **Simple Python Agent** (`simple_python_agent.py`)
   - Basic agent that can execute Python code and bash commands
   - Creates files and runs scripts in a sandboxed environment
   - Perfect for learning the SDK basics

2. **Interactive Coding Agent** (`interactive_coding_agent.py`)
   - Interactive agent with a command loop
   - Supports multiple commands: execute Python, run bash, create files
   - Real-time feedback and error handling

3. **Advanced Coding Agent** (`advanced_coding_agent.py`)
   - Full-featured agent with file management
   - Code execution with syntax checking
   - Project scaffolding capabilities
   - Comprehensive error handling

### Running the Examples

```bash
# Navigate to the examples directory
cd ../coding-agents

# Run the simple agent
python simple_python_agent.py

# Run the interactive agent
python interactive_coding_agent.py

# Run the advanced agent
python advanced_coding_agent.py
```

### Example: Simple Python Agent

```python
import asyncio
from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig

async def run_python_code(code: str):
    """Execute Python code in a sandboxed environment."""
    config = SandboxRuntimeConfig.from_json({
        "network": {
            "allowedDomains": ["github.com", "*.github.com"],
            "deniedDomains": []
        },
        "filesystem": {
            "denyRead": [],
            "allowWrite": ["."],
            "denyWrite": []
        }
    })
    
    await SandboxManager.initialize(config)
    
    try:
        # Write code to temporary file
        with open("temp_script.py", "w") as f:
            f.write(code)
        
        # Execute in sandbox
        command = await SandboxManager.wrap_with_sandbox("python temp_script.py")
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        return result.stdout
    finally:
        await SandboxManager.reset()

# Usage
output = asyncio.run(run_python_code("print('Hello from sandbox!')"))
print(output)
```

See the `../coding-agents/` directory for complete, working examples.

## Configuration

### Settings File Location

By default, the sandbox runtime looks for configuration at `~/.srt-settings.json`. You can specify a custom path using the `--settings` flag:

```bash
srt --settings /path/to/srt-settings.json <command>
```

### Complete Configuration Example

```json
{
  "network": {
    "allowedDomains": [
      "github.com",
      "*.github.com",
      "lfs.github.com",
      "api.github.com",
      "npmjs.org",
      "*.npmjs.org"
    ],
    "deniedDomains": [
      "malicious.com"
    ],
    "allowUnixSockets": ["/var/run/docker.sock"],
    "allowLocalBinding": false
  },
  "filesystem": {
    "denyRead": [
      "~/.ssh"
    ],
    "allowWrite": [
      ".",
      "src/",
      "test/",
      "/tmp"
    ],
    "denyWrite": [
      ".env",
      "config/production.json"
    ]
  },
  "ignoreViolations": {
    "*": ["/usr/bin", "/System"],
    "git push": ["/usr/bin/nc"],
    "npm": ["/private/tmp"]
  },
  "enableWeakerNestedSandbox": false
}
```

### Configuration Options

#### Network Configuration

Uses an **allow-only pattern** - all network access is denied by default.

- `network.allowedDomains` - Array of allowed domains (supports wildcards like `*.example.com`). Empty array = no network access.
- `network.deniedDomains` - Array of denied domains (checked first, takes precedence over allowedDomains)
- `network.allowUnixSockets` - Array of Unix socket paths that can be accessed (macOS only)
- `network.allowLocalBinding` - Allow binding to local ports (boolean, default: false)

#### Filesystem Configuration

Uses two different patterns:

**Read restrictions** (deny-only pattern) - all reads allowed by default:
- `filesystem.denyRead` - Array of paths to deny read access. Empty array = full read access.

**Write restrictions** (allow-only pattern) - all writes denied by default:
- `filesystem.allowWrite` - Array of paths to allow write access. Empty array = no write access.
- `filesystem.denyWrite` - Array of paths to deny write access within allowed paths (takes precedence over allowWrite)

**Path Syntax (macOS):**

Paths support git-style glob patterns on macOS, similar to `.gitignore` syntax:

- `*` - Matches any characters except `/` (e.g., `*.ts` matches `foo.ts` but not `foo/bar.ts`)
- `**` - Matches any characters including `/` (e.g., `src/**/*.ts` matches all `.ts` files in `src/`)
- `?` - Matches any single character except `/` (e.g., `file?.txt` matches `file1.txt`)
- `[abc]` - Matches any character in the set (e.g., `file[0-9].txt` matches `file3.txt`)

**Path Syntax (Linux):**

Linux currently does not support glob matching. Use literal paths only.

**All platforms:**
- Paths can be absolute (e.g., `/home/user/.ssh`) or relative to the current working directory (e.g., `./src`)
- `~` expands to the user's home directory

### Common Configuration Recipes

**Allow GitHub access** (all necessary endpoints):
```json
{
  "network": {
    "allowedDomains": [
      "github.com",
      "*.github.com",
      "lfs.github.com",
      "api.github.com"
    ],
    "deniedDomains": []
  },
  "filesystem": {
    "denyRead": [],
    "allowWrite": ["."],
    "denyWrite": []
  }
}
```

**Restrict to specific directories:**
```json
{
  "network": {
    "allowedDomains": [],
    "deniedDomains": []
  },
  "filesystem": {
    "denyRead": ["~/.ssh"],
    "allowWrite": [".", "src/", "test/"],
    "denyWrite": [".env", "secrets/"]
  }
}
```

**For AI Coding Agents:**
```json
{
  "network": {
    "allowedDomains": [
      "github.com",
      "*.github.com",
      "pypi.org",
      "*.pypi.org"
    ],
    "deniedDomains": []
  },
  "filesystem": {
    "denyRead": ["~/.ssh", "~/.aws", "~/.kube"],
    "allowWrite": [".", "src/", "tests/", "/tmp"],
    "denyWrite": [".env", ".secrets", "*.key"]
  }
}
```

## How It Works

The sandbox uses OS-level primitives to enforce restrictions that apply to the entire process tree:

- **macOS**: Uses `sandbox-exec` with dynamically generated [Seatbelt profiles](https://reverse.put.as/wp-content/uploads/2011/09/Apple-Sandbox-Guide-v1.0.pdf)
- **Linux**: Uses [bubblewrap](https://github.com/containers/bubblewrap) for containerization with network namespace isolation

### Dual Isolation Model

Both filesystem and network isolation are required for effective sandboxing. Without file isolation, a compromised process could exfiltrate SSH keys or other sensitive files. Without network isolation, a process could escape the sandbox and gain unrestricted network access.

**Filesystem Isolation** enforces read and write restrictions:

- **Read** (deny-only pattern): By default, read access is allowed everywhere. You can deny specific paths (e.g., `~/.ssh`). An empty deny list means full read access.
- **Write** (allow-only pattern): By default, write access is denied everywhere. You must explicitly allow paths (e.g., `.`, `/tmp`). An empty allow list means no write access.

**Network Isolation** (allow-only pattern): By default, all network access is denied. You must explicitly allow domains. An empty allowedDomains list means no network access. Network traffic is routed through proxy servers running on the host.

For more details on sandboxing in Claude Code, see:
- [Claude Code Sandboxing Documentation](https://docs.claude.com/en/docs/claude-code/sandboxing)
- [Beyond Permission Prompts: Making Claude Code More Secure and Autonomous](https://www.anthropic.com/engineering/claude-code-sandboxing)

## Architecture

```
sandbox_runtime/
├── __init__.py              # Library exports
├── cli.py                    # CLI entrypoint (srt command)
├── config/                   # Configuration schemas
│   └── schemas.py           # Pydantic models for validation
├── network/                  # Network proxy implementation
│   ├── http_proxy.py        # HTTP/HTTPS proxy for network filtering
│   ├── socks_proxy.py       # SOCKS5 proxy for network filtering
│   └── bridge.py           # Linux network bridge setup
├── sandbox/                  # Sandbox implementation
│   ├── manager.py           # Main sandbox manager
│   ├── violation_store.py   # Violation tracking
│   ├── utils.py             # Shared sandbox utilities
│   ├── linux_utils.py       # Linux bubblewrap sandboxing
│   ├── macos_utils.py       # macOS sandbox-exec sandboxing
│   └── seccomp.py           # Linux seccomp filter handling
└── utils/                    # Shared utilities
    ├── debug.py             # Debug logging
    ├── platform.py          # Platform detection
    └── ripgrep.py           # Ripgrep utility functions
```

## Development

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run specific test file
pytest tests/test_config_validation.py -v

# Type checking
mypy sandbox_runtime

# Lint code
ruff check sandbox_runtime

# Format code
black sandbox_runtime
```

## Platform Support

- **macOS**: Uses `sandbox-exec` with custom profiles (no additional dependencies beyond `ripgrep`)
- **Linux**: Uses `bubblewrap` (bwrap) for containerization
- **Windows**: Not yet supported

### Platform-Specific Dependencies

**Linux requires:**
- `bubblewrap` - Container runtime
  - Ubuntu/Debian: `apt-get install bubblewrap`
  - Fedora: `dnf install bubblewrap`
  - Arch: `pacman -S bubblewrap`
- `socat` - Socket relay for proxy bridging
  - Ubuntu/Debian: `apt-get install socat`
  - Fedora: `dnf install socat`
  - Arch: `pacman -S socat`
- `ripgrep` - Fast search tool for deny path detection
  - Ubuntu/Debian: `apt-get install ripgrep`
  - Fedora: `dnf install ripgrep`
  - Arch: `pacman -S ripgrep`

**macOS requires:**
- `ripgrep` - Fast search tool for deny path detection
  - Install via Homebrew: `brew install ripgrep`
  - Or download from: https://github.com/BurntSushi/ripgrep/releases

## Security Limitations

* Network Sandboxing Limitations: The network filtering system operates by restricting the domains that processes are allowed to connect to. It does not otherwise inspect the traffic passing through the proxy and users are responsible for ensuring they only allow trusted domains in their policy.

⚠️ **Warning**: Users should be aware of potential risks that come from allowing broad domains like `github.com` that may allow for data exfiltration. Also, in some cases it may be possible to bypass the network filtering through [domain fronting](https://en.wikipedia.org/wiki/Domain_fronting).

* Privilege Escalation via Unix Sockets: The `allowUnixSockets` configuration can inadvertently grant access to powerful system services that could lead to sandbox bypasses. For example, if it is used to allow access to `/var/run/docker.sock` this would effectively grant access to the host system through exploiting the docker socket. Users are encouraged to carefully consider any unix sockets that they allow through the sandbox.

* Filesystem Permission Escalation: Overly broad filesystem write permissions can enable privilege escalation attacks. Allowing writes to directories containing executables in `$PATH`, system configuration directories, or user shell configuration files (`.bashrc`, `.zshrc`) can lead to code execution in different security contexts when other users or system processes access these files.

* Linux Sandbox Strength: The Linux implementation provides strong filesystem and network isolation but includes an `enableWeakerNestedSandbox` mode that enables it to work inside of Docker environments without privileged namespaces. This option considerably weakens security and should only be used in cases where additional isolation is otherwise enforced.

## Migration from TypeScript

This is a Python port of the original TypeScript implementation. The API and configuration format remain compatible, but the implementation language has changed from TypeScript/Node.js to Python.

Key differences:
- Installation: Use `pip` instead of `npm`
- Library usage: Use Python async/await patterns instead of JavaScript promises
- CLI: Same interface, implemented with `click` instead of `commander`
- Configuration: Same JSON format, validated with Pydantic instead of Zod

## License

Apache-2.0
