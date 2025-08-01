"""YAML loader with environment variable expansion."""

import os
import re
import yaml
from typing import Any, Dict


def expand_env_vars(value: Any) -> Any:
    """Expand environment variables in a value."""
    if isinstance(value, str):
        # Replace ${VAR} with environment variable value
        pattern = re.compile(r'\$\{([^}]+)\}')
        
        def replacer(match):
            env_var = match.group(1)
            return os.getenv(env_var, match.group(0))
        
        return pattern.sub(replacer, value)
    elif isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [expand_env_vars(item) for item in value]
    else:
        return value


def load_yaml_with_env(file_path: str) -> Dict[str, Any]:
    """Load YAML file with environment variable expansion."""
    with open(file_path, 'r') as f:
        data = yaml.safe_load(f)
    
    # Recursively expand environment variables
    return expand_env_vars(data)