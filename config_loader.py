"""
Config Loader Module
====================
Shared configuration loading and logging setup for the stock monitor system.
Consolidates duplicated load_config() and logging setup from multiple modules.
"""

import os
import logging
import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Load .env file so email credentials and API keys are available
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(SCRIPT_DIR, '.env'))
except ImportError:
    pass


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file. Defaults to config.yaml in the
                     same directory as this module.

    Returns:
        Parsed configuration dictionary.
    """
    if config_path is None:
        config_path = os.path.join(SCRIPT_DIR, 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def setup_logging() -> None:
    """Configure logging for stock monitor modules.

    Sets up both file and console handlers with a consistent format.
    Safe to call multiple times -- basicConfig is a no-op after the first call.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(SCRIPT_DIR, 'stock_monitor.log')),
            logging.StreamHandler()
        ]
    )
