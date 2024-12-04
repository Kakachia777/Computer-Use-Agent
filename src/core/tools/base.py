from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pathlib import Path
import logging

class BaseTool(ABC):
    """Base class for all tools with security controls"""
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self._logger = logging.getLogger(__name__)
        
    @abstractmethod
    async def execute(self, **params) -> Dict[str, Any]:
        """Execute the tool functionality"""
        pass
        
    def validate_path(self, path: Path) -> bool:
        """Ensure path is within allowed workspace"""
        try:
            return path.resolve().is_relative_to(self.workspace)
        except ValueError:
            return False
            
    def sanitize_input(self, value: str) -> str:
        """Sanitize user input"""
        # Implement input sanitization
        return value 