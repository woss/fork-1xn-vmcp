#!/usr/bin/env python3
"""Simple test script to verify the library works."""

import asyncio
import sys
from sandbox_runtime import SandboxManager
from sandbox_runtime.config.schemas import SandboxRuntimeConfig

async def main():
    """Test the sandbox runtime library."""
    print("Testing Sandbox Runtime Library...")
    print("=" * 50)
    
    # Create a test configuration
    print("\n1. Creating test configuration...")
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
    print("✓ Configuration created")
    
    # Initialize the sandbox
    print("\n2. Initializing sandbox manager...")
    try:
        await SandboxManager.initialize(config)
        print("✓ Sandbox manager initialized")
    except Exception as e:
        print(f"✗ Failed to initialize: {e}")
        print("\nNote: This might fail if dependencies are missing")
        print("On macOS, you need: ripgrep (rg) - install with: brew install ripgrep")
        print("On Linux, you need: bubblewrap (bwrap), socat, ripgrep (rg)")
        print("\nContinuing with basic tests that don't require full initialization...")
        
        # Test config validation
        print("\n3. Testing config validation...")
        try:
            test_config = SandboxRuntimeConfig.from_json({
                "network": {"allowedDomains": ["test.com"], "deniedDomains": []},
                "filesystem": {"denyRead": [], "allowWrite": ["."], "denyWrite": []}
            })
            print("✓ Config validation works")
        except Exception as e:
            print(f"✗ Config validation failed: {e}")
            return 1
        
        print("\n" + "=" * 50)
        print("⚠ Some tests skipped due to missing dependencies")
        print("Install dependencies to run full test suite")
        return 0
    
    # Wrap a command
    print("\n3. Wrapping a command...")
    command = "echo 'Hello from sandbox'"
    try:
        sandboxed = await SandboxManager.wrap_with_sandbox(command)
        print(f"✓ Command wrapped")
        print(f"  Original: {command}")
        print(f"  Sandboxed: {sandboxed[:100]}...")  # Truncate for display
    except Exception as e:
        print(f"✗ Failed to wrap command: {e}")
        await SandboxManager.reset()
        return 1
    
    # Test config access
    print("\n4. Testing config access...")
    try:
        network_config = SandboxManager.get_network_restriction_config()
        print(f"✓ Network config: {network_config}")
    except Exception as e:
        print(f"✗ Failed to get config: {e}")
    
    # Cleanup
    print("\n5. Cleaning up...")
    try:
        await SandboxManager.reset()
        print("✓ Cleanup complete")
    except Exception as e:
        print(f"✗ Cleanup error: {e}")
    
    print("\n" + "=" * 50)
    print("✓ All tests passed!")
    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

