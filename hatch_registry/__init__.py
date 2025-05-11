"""
Hatch-Registry package

This package provides a registry for Hatch packages, handling package validation,
dependency resolution, and differential storage of package versions.
"""

__version__ = "0.1.0"

# Import main components
from .registry_core import RegistryCore, RegistryCoreError
from .registry_diff import RegistryDiff, RegistryDiffError  
from .registry_validator import RegistryValidator, RegistryValidationError
from .registry_updater import RegistryUpdater, RegistryUpdateError
from .registry_cli import main

__all__ = [
    'RegistryCore', 'RegistryCoreError',
    'RegistryDiff', 'RegistryDiffError',
    'RegistryValidator', 'RegistryValidationError',
    'RegistryUpdater', 'RegistryUpdateError',
    'main',
]