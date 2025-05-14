import datetime
import logging
from pathlib import Path
from typing import Dict, Any, Tuple

# Import internal modules
from .registry_core import RegistryCore
from .registry_validator import RegistryValidator


class RegistryUpdateError(Exception):
    """Exception raised for registry update errors."""
    pass


class RegistryUpdater:
    """
    Updates the Hatch package registry with new packages and versions,
    orchestrating the core, diff, and validation modules.
    """
    
    def __init__(self, registry_path: Path):
        """
        Initialize the registry updater.
        
        Args:
            registry_path: Path to the registry JSON file
        """
        self.logger = logging.getLogger("hatch.registry.updater")
        self.core = RegistryCore(registry_path)
        self.validator = RegistryValidator(self.core.registry_data)
    
    def _add_new_package(self, repo_name: str, package_metadata: dict = None) -> bool:
        """
        Add a new package to the registry.
        
        Args:
            repo_name: Repository name
            package_metadata: Metadata for the package

        Returns:
            bool: True if the package was added successfully
        """
        try:
            # Add the package to the registry
            if not self.core.add_package(repo_name, package_metadata):
                self.logger.error(f"Failed to add package {package_metadata['name']} to repository {repo_name}")
                return False

            self.logger.info(f"Package {package_metadata['name']} added to repository {repo_name}.")
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding package: {e}")
            return False

    def _add_new_package_version(self, repo_name: str, package_metadata: dict) -> bool:
        """
        Private method to update the registry with a new package version.
        Called by validate_and_add_package after validation.
        
        Args:
            repo_name: Repository name
            package_metadata: Package metadata for the new version
            
        Returns:
            bool: True if the registry was updated successfully
        """
        try:                
            # Update the registry
            if not self.core.add_new_package_version(repo_name, package_metadata):
                self.logger.error(f"Failed to update registry for package {package_metadata['name']} in repository {repo_name}")
                return False
            
            self.logger.info(f"Updated registry for package {package_metadata['name']} in repository {repo_name}.")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating package registry: {e}")
            return False

    def validate_package(self, repo_name: str, package_dir: Path, metadata_path: str = "hatch_metadata.json") -> Tuple[bool, dict]:
        """
        Validate that a new package or package version can be added to the registry
        without actually adding it.
        
        Args:
            repo_name: Repository name
            package_dir: Path to the package directory
            metadata_path: Path to the metadata file
            
        Returns:
            Tuple[bool, dict]: (is_valid, validation results). Upon success, the results
            will contain package metadata under the "metadata" key.
        """
        try:
            # Validate repository exists
            repo = self.core.find_repository(repo_name)
            if not repo:
                self.logger.error(f"Repository {repo_name} not found")
                return False, {"valid": False, "errors": [f"Repository {repo_name} not found"]}
                
            # Validate package directory exists
            if not package_dir.exists() or not package_dir.is_dir():
                self.logger.error(f"Package directory does not exist or is not a directory: {package_dir}")
                return False, {"valid": False, "errors": [f"Package directory does not exist or is not a directory: {package_dir}"]}
            
            # Load metadata to get package name and version
            metadata = self.core.load_metadata(package_dir, metadata_path)
            if not metadata:
                self.logger.error(f"Failed to load metadata from {package_dir}/{metadata_path}")
                return False, {"valid": False, "errors": [f"Failed to load metadata from {package_dir}/{metadata_path}"]}
                
            package_name = metadata.get("name")
            if not package_name:
                self.logger.error("Package name not found in provided package metadata file")
                return False, {"valid": False, "errors": ["Package name not found in provided package metadata file"]}
                
            version = metadata.get("version")
            if not version:
                self.logger.error("Package version not found in provided package metadata file")
                return False, {"valid": False, "errors": ["Package version not found in provided package metadata file"]}
            
            # Check if package already exists
            existing_pkg = self.core.find_package(repo_name, package_name)
            existing_version = None
            if existing_pkg:
                existing_version = self.core.find_version(repo_name, package_name, version)
                if existing_version:
                    self.logger.error(f"Version {version} of package {package_name} already exists")
                    return False, {"valid": False, "errors": [f"Version {version} of package {package_name} already exists"]}
            
            # Create pending update tuple for circular dependency detection
            pending_update = (package_name, metadata)
            
            # Validate the package with the validator
            is_valid, results = self.validator.validate_package(package_dir, pending_update)
            if not is_valid:
                self.logger.error(f"Validation failed for package {package_name} version {version}")
                return False, results
                
            # Package is valid and can be added to the registry
            self.logger.info(f"Package {package_name} version {version} validation passed")
            
            # Return validation results with additional context
            results["is_new_package"] = not existing_pkg
            results["metadata"] = metadata
            return True, results
            
        except Exception as e:
            self.logger.error(f"Error validating package: {e}")
            return False, {"valid": False, "errors": [f"Error validating package: {str(e)}"]}
    
    def validate_and_add_package(self, repo_name: str, package_dir: Path, metadata_path: str = "hatch_metadata.json") -> Tuple[bool, dict]:
        """
        Validate a package and add it to the registry if validation succeeds.
        This is a convenience method that combines validation and addition.
        
        Args:
            repo_name: Repository name
            package_dir: Path to the package directory
            metadata_path: Path to the metadata file
            
        Returns:
            Tuple[bool, dict]: (success, results or error information)
        """
        # First validate the package
        is_valid, validation_results = self.validate_package(repo_name, package_dir, metadata_path)
        
        if not is_valid:
            return False, validation_results
            
        # Package is valid, now add it using the validation results
        is_new_package = validation_results.get("is_new_package", False)
        if is_new_package:            # Add as a new package
            added = self._add_new_package(
                repo_name,
                package_metadata=validation_results["metadata"]
            )
        else:            
            added = self._add_new_package_version(
                repo_name, 
                package_metadata=validation_results["metadata"]
            )
        
        return added, validation_results