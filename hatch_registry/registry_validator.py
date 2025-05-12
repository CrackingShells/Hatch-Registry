#!/usr/bin/env python3
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import logging
import json

# Import Hatch modules
from hatch_validator import HatchPackageValidator

class RegistryValidationError(Exception):
    """Exception for package validation errors."""
    pass

class RegistryValidator:
    """Package validation functionality for registry operations."""
    
    def __init__(self, registry_data: Dict[str, Any] = None):
        """
        Initialize the registry validator.
        
        Args:
            registry_data: Optional registry data for validation context
        """
        self.logger = logging.getLogger("hatch.registry.validator")
        self.registry_data = registry_data
    
    def validate_package(self, package_dir: Path, pending_update: Optional[Tuple[str, Dict]] = None) -> Tuple[bool, dict]:
        """
        Validate a package against the Hatch package requirements.
        
        Args:
            package_dir: Path to the package directory
            pending_update: Optional tuple of (package_name, metadata) for circular dependency detection
            
        Returns:
            Tuple of (is_valid, results)
        """
        self.logger.debug(f"Validating package at: {package_dir}")
        
        try:
            # Initialize validator with registry data for dependency resolution
            validator = HatchPackageValidator(
                allow_local_dependencies=False,
                registry_data=self.registry_data)
            
            # Run the validation
            is_valid, results = validator.validate_package(package_dir, pending_update)
            
            # Check if validation passed
            if is_valid:
                self.logger.info(f"Package validation successful: {package_dir}")
                return True, results
            else:
                self.logger.error(f"Package validation failed: {package_dir}")
                self._log_validation_errors(results, "Validation failed")
                return False, results
                
        except Exception as e:
            self.logger.error(f"Error during package validation: {e}")
            return False, {"valid": False, "errors": [str(e)], "metadata": None}
    
    def _log_validation_errors(self, results: dict, message: str) -> None:
        """
        Log validation errors in a structured format.
        
        Args:
            results: Validation results dictionary
            message: Message to include with the errors
        """
        self.logger.error(f"{message}")
        
        if "errors" in results and results["errors"]:
            for i, error in enumerate(results["errors"]):
                self.logger.error(f"  Error {i+1}: {error}")
                
        if "dependency_errors" in results and results["dependency_errors"]:
            for i, error in enumerate(results["dependency_errors"]):
                self.logger.error(f"  Dependency Error {i+1}: {error}")
                
        if "metadata" in results and results["metadata"]:
            self.logger.debug(f"Package metadata: {json.dumps(results['metadata'], indent=2)}")
