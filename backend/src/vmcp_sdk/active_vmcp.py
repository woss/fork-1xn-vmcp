"""
Active vMCP state management.

Manages the currently active vMCP stored in .active-vmcp.json
"""

import json
from pathlib import Path
from typing import Optional


class ActiveVMCPManager:
    """Manages the active vMCP state."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the active vMCP manager.
        
        Args:
            config_path: Path to .active-vmcp.json file.
                        Defaults to .active-vmcp.json in current directory.
        """
        if config_path is None:
            # Use ~/.vmcp/.active-vmcp.json as default
            vmcp_dir = Path.home() / ".vmcp"
            vmcp_dir.mkdir(parents=True, exist_ok=True)
            config_path = vmcp_dir / ".active-vmcp.json"
        self.config_path = config_path
    
    def get_active_vmcp(self) -> Optional[str]:
        """
        Get the currently active vMCP name.
        
        Returns:
            Active vMCP name or None if not set
        """
        if not self.config_path.exists():
            return None
        
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
                return data.get("vmcp_name")
        except (json.JSONDecodeError, KeyError, IOError):
            return None
    
    def set_active_vmcp(self, vmcp_name: str) -> None:
        """
        Set the active vMCP name.
        
        Args:
            vmcp_name: Name of the vMCP to set as active
        """
        data = {"vmcp_name": vmcp_name}
        with open(self.config_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def clear_active_vmcp(self) -> None:
        """Clear the active vMCP."""
        if self.config_path.exists():
            self.config_path.unlink()

