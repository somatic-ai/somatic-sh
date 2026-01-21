"""Configuration loading and validation"""

from pathlib import Path
from typing import Optional
import yaml
from loguru import logger

from .models import SomaticConfig


def load_config(config_path: Optional[str] = None) -> SomaticConfig:
    """Load and validate configuration from somatic.yml"""
    if config_path is None:
        config_path = Path.cwd() / "somatic.yml"
    else:
        config_path = Path(config_path)
    
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    logger.info(f"Loading configuration from {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        config = SomaticConfig(**config_data)
        logger.info("Configuration loaded and validated successfully")
        return config
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise
