import os
from typing import List, Dict, Any, Optional
import json


class HardwareConfig:
    """Configuration for hardware validation and management."""
    
    DEFAULT_VALID_SUFFIXES = [
        "4000Ada", "L40", "A100", "A100S", "H100N", "H100S", "H200"
    ]
    
    @classmethod
    def get_valid_hardware_suffixes(cls) -> List[str]:
        """Get valid hardware suffixes from environment or config file.
        
        Returns:
            List of valid hardware suffixes
        """
        env_suffixes = os.getenv("OPENWEIGHTS_VALID_HARDWARE_SUFFIXES")
        if env_suffixes:
            try:
                return json.loads(env_suffixes)
            except json.JSONDecodeError:
                return [suffix.strip() for suffix in env_suffixes.split(",") if suffix.strip()]
        
        config_path = os.getenv("OPENWEIGHTS_HARDWARE_CONFIG_PATH", "hardware_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    return config.get("valid_hardware_suffixes", cls.DEFAULT_VALID_SUFFIXES)
            except (json.JSONDecodeError, IOError):
                pass
        
        return cls.DEFAULT_VALID_SUFFIXES
    
    @classmethod
    def validate_hardware_entry(cls, hardware: str, valid_suffixes: Optional[List[str]] = None) -> bool:
        """Validate a single hardware configuration entry.
        
        Args:
            hardware: Hardware configuration string to validate
            valid_suffixes: Optional list of valid suffixes, defaults to configured values
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(hardware, str) or not hardware.strip():
            return False
            
        if valid_suffixes is None:
            valid_suffixes = cls.get_valid_hardware_suffixes()
            
        return any(hardware.endswith(suffix) for suffix in valid_suffixes)
    
    @classmethod
    def get_hardware_info(cls) -> Dict[str, Any]:
        """Get comprehensive hardware configuration information.
        
        Returns:
            Dictionary with hardware configuration details
        """
        return {
            "valid_suffixes": cls.get_valid_hardware_suffixes(),
            "config_source": cls._get_config_source(),
            "validation_rules": {
                "must_end_with_valid_suffix": True,
                "must_be_non_empty_string": True
            }
        }
    
    @classmethod
    def _get_config_source(cls) -> str:
        """Determine the source of the current configuration."""
        if os.getenv("OPENWEIGHTS_VALID_HARDWARE_SUFFIXES"):
            return "environment_variable"
        
        config_path = os.getenv("OPENWEIGHTS_HARDWARE_CONFIG_PATH", "hardware_config.json")
        if os.path.exists(config_path):
            return f"config_file:{config_path}"
            
        return "default_values"
