"""
Active vMCP state management.

Reads vmcp_id from sandbox config file (.vmcp-config.json) in the sandbox directory.
"""

import json
from pathlib import Path
from typing import Optional


class ActiveVMCPManager:
    """Manages the active vMCP state by reading from sandbox config."""
    
    SANDBOX_BASE = Path.home() / ".vmcp"
    
    def __init__(self, sandbox_path: Optional[Path] = None):
        """
        Initialize the active vMCP manager.
        
        Args:
            sandbox_path: Path to sandbox directory. If None, tries to detect from current directory.
        """
        self.sandbox_path = sandbox_path or self._detect_sandbox_path()
    
    def _detect_sandbox_path(self) -> Optional[Path]:
        """
        Detect sandbox path from current working directory.
        
        Returns:
            Sandbox path if detected, None otherwise
        """
        cwd = Path.cwd()
        # Check if we're in a sandbox directory (~/.vmcp/{vmcp_id})
        if str(cwd).startswith(str(self.SANDBOX_BASE)):
            return cwd
        return None
    
    def get_active_vmcp_id(self) -> Optional[str]:
        """
        Get the vmcp_id from sandbox config file.
        
        Returns:
            vmcp_id if found, None otherwise
        """
        if not self.sandbox_path:
            return None
        
        config_path = self.sandbox_path / ".vmcp-config.json"
        if not config_path.exists():
            return None
        
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                return data.get("vmcp_id")
        except (json.JSONDecodeError, KeyError, IOError):
            return None
    
    # Legacy methods for backward compatibility (deprecated)
    def get_active_vmcp(self) -> Optional[str]:
        """
        Get the currently active vMCP name (deprecated - use get_active_vmcp_id).
        
        Returns:
            Active vMCP name or None if not set
        """
        vmcp_id = self.get_active_vmcp_id()
        if not vmcp_id:
            return None
        # Try to resolve vmcp_id to name (for backward compatibility)
        # This is a simplified version - in practice, you'd query the database
        return vmcp_id
    
    def set_active_vmcp(self, vmcp_name: str) -> None:
        """
        Set the active vMCP name (deprecated - config is now auto-detected from sandbox).
        
        Args:
            vmcp_name: Name of the vMCP to set as active
        """
        # No-op - config is now read from sandbox directory
        pass
    
    def clear_active_vmcp(self) -> None:
        """Clear the active vMCP (deprecated - config is now auto-detected from sandbox)."""
        # No-op - config is now read from sandbox directory
        pass

