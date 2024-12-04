from typing import Any, Dict, Optional
import yaml
import os
from pathlib import Path

class ConfigManager:
    """Manages configuration settings with YAML support."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.load_config()
        
    def load_config(self):
        """Load configuration from YAML file."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = self._get_default_config()
            self.save_config()
            
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration settings."""
        return {
            'performance': {
                'action_timeout': 10,
                'max_retries': 3,
                'batch_size': 50
            },
            'security': {
                'validate_actions': True,
                'blocked_commands': ['rm -rf', 'format', 'del /f']
            },
            'monitoring': {
                'enabled': True,
                'log_level': 'INFO',
                'metrics_retention_days': 7
            },
            'cost_management': {
                'daily_budget': None,
                'cost_tracking': True
            }
        } 