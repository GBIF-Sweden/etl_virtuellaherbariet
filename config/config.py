import logging

import yaml


class ConfigError(Exception):
    """Raised when configuration loading or validation fails."""
