
import logging
from pathlib import Path
from typing import Dict, Any

# Import internal modules
from .registry_core import RegistryCore
from .registry_diff import RegistryDiff
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
        self.diff = RegistryDiff(self.core.registry_data)
        self.validator = RegistryValidator(self.core.registry_data)
    
    def add_package(self, repo_name: str, package_dir: Path, metadata_path: str = "hatch_metadata.json") -> bool:
        """
        Add a new package to the registry.
        
        Args:
            repo_name: Repository name
            package_dir: Path to the package directory
            metadata_path: Path to the metadata file
            
        Returns:
            bool: True if the package was added successfully
        """
        try:
            # Validate repository exists
            repo = self.core.find_repository(repo_name)
            if not repo:
                self.logger.error(f"Repository {repo_name} not found")
                return False
                
            # Validate package directory exists
            if not package_dir.exists() or not package_dir.is_dir():
                self.logger.error(f"Package directory does not exist or is not a directory: {package_dir}")
                return False
            
            # Validate package
            is_valid, results = self.validator.validate_package(package_dir)
            if not is_valid:
                self.logger.error("Package validation failed.")
                return False
                
            # Extract required metadata fields
            metadata = results.get("metadata")
            if not metadata:
                self.logger.error("No metadata found in validation results")
                return False
                
            package_name = metadata.get("name")
            if not package_name:
                self.logger.error("Package name not found in metadata")
                return False
                
            version = metadata.get("version")
            if not version:
                self.logger.error("Package version not found in metadata")
                return False
                
            # Check if package already exists
            existing_pkg = self.core.find_package(repo_name, package_name)
            if existing_pkg:
                self.logger.info(f"Package {package_name} already exists, adding version {version}")
                return self.update_package_registry(repo_name, package_name, package_dir, metadata_path)
                
            # Add the package
            package_metadata = {
                "name": package_name,
                "description": metadata.get("description", ""),
                "category": metadata.get("category", ""),
                "tags": metadata.get("tags", [])
            }
            
            # Add the package to the registry
            if not self.core.add_package(repo_name, package_metadata):
                self.logger.error(f"Failed to add package {package_name} to repository {repo_name}")
                return False
                
            # Add the first version
            version_added = self.update_package_registry(repo_name, package_name, package_dir, metadata_path, is_first_version=True)
            if not version_added:
                # If adding the version failed, remove the package we just added
                self.core.remove_package(repo_name, package_name)
                self.logger.error(f"Failed to add version {version} for package {package_name}, package not added")
                return False
                
            self.logger.info(f"Package {package_name} added to repository {repo_name}.")
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding package: {e}")
            return False
    
    def update_package_registry(self, repo_name: str, package_name: str,
                          package_path: Path, metadata_path: str = "hatch_metadata.json",
                          is_first_version: bool = False) -> bool:
        """
        Update the registry with a new package version.
        
        Args:
            repo_name: Repository name
            package_name: Package name
            package_path: Path to the package directory
            metadata_path: Path to the metadata file
            is_first_version: Whether this is the first version of the package
            
        Returns:
            bool: True if the registry was updated successfully
        """
        try:
            # Load metadata from the package directory
            metadata = self.core.load_metadata(package_path, metadata_path)
            if not metadata:
                self.logger.error(f"Failed to load metadata from {package_path}/{metadata_path}")
                return False
                
            # Get version from metadata
            version = metadata.get("version")
            if not version:
                self.logger.error("Package version not found in metadata")
                return False
                
            # Check if the version already exists
            if self.core.find_version(repo_name, package_name, version) and not is_first_version:
                self.logger.error(f"Version {version} of package {package_name} already exists")
                return False
                
            # Create pending update tuple for circular dependency detection
            pending_update = (package_name, metadata)
            
            # Validate the package
            is_valid, results = self.validator.validate_package(package_path, pending_update)
            if not is_valid:
                self.logger.error(f"Validation failed for package {package_name} version {version}")
                return False
                
            # Prepare version data
            version_data = self._prepare_version_data(repo_name, package_name, metadata, package_path, metadata_path, is_first_version)
            
            # Update the registry
            self.core.update_package_version(repo_name, package_name, version_data)
            self.logger.info(f"Updated registry for package {package_name} in repository {repo_name}.")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating package registry: {e}")
            return False
    
    def _prepare_version_data(self, repo_name: str, package_name: str, metadata: dict,
                      package_path: Path, metadata_path: Path, is_first_version: bool) -> Dict[str, Any]:
        """
        Prepare version data for storage in the registry.
        
        Args:
            repo_name: Repository name
            package_name: Package name
            metadata: Package metadata
            package_path: Path to the package
            metadata_path: Path to metadata file
            is_first_version: Whether this is the first version of the package
            
        Returns:
            Dictionary containing version data
        """
        import datetime
        
        # Initialize with base metadata that's the same for all versions
        version = metadata.get("version")
        artifacts = []  # TODO: Add actual artifacts
        
        version_data = {
            "version": version,
            "path": str(package_path),
            "metadata_path": str(metadata_path),
            "artifacts": artifacts,
            "added_date": datetime.datetime.now().isoformat()
        }
        
        # Get dependencies from the package metadata
        hatch_dependencies = metadata.get("hatch_dependencies", [])
        python_dependencies = metadata.get("python_dependencies", [])
        compatibility = metadata.get("compatibility", {})
        base_version = None
        
        # For differential storage, compute changes from base version
        if not is_first_version:
            pkg = self.core.find_package(repo_name, package_name)
            if pkg and pkg.get("versions"):
                base_version = pkg.get("latest_version")
                base_version_data = self.core.find_version(repo_name, package_name, base_version)
                
                if base_version_data:
                    # Load the full base version metadata to compute diffs
                    try:
                        base_metadata_path = Path(base_version_data.get("path")) / base_version_data.get("metadata_path", "")
                        
                        if base_metadata_path.exists():
                            with open(base_metadata_path, 'r') as f:
                                import json
                                base_metadata = json.load(f)
                            
                            # Compute diffs for dependencies
                            dependencies_added, dependencies_removed, dependencies_modified = self.diff.compute_dependency_diff(
                                base_metadata.get("hatch_dependencies", []),
                                metadata.get("hatch_dependencies", [])
                            )
                            
                            # Compute diffs for Python dependencies
                            python_dependencies_added, python_dependencies_removed, python_dependencies_modified = self.diff.compute_python_dependency_diff(
                                base_metadata.get("python_dependencies", []),
                                metadata.get("python_dependencies", [])
                            )
                            
                            # Compute diffs for compatibility
                            compatibility_changes = self.diff.compute_compatibility_diff(
                                base_metadata.get("compatibility", {}),
                                metadata.get("compatibility", {})
                            )
                        else:
                            # Fall back to non-differential storage if file doesn't exist
                            self.logger.warning(f"Base metadata file not found: {base_metadata_path}")
                            dependencies_added = hatch_dependencies
                            python_dependencies_added = python_dependencies
                            compatibility_changes = compatibility
                            dependencies_removed = []
                            dependencies_modified = []
                            python_dependencies_removed = []
                            python_dependencies_modified = []
                            
                    except Exception as e:
                        self.logger.error(f"Error computing diffs: {e}")
                        # Fall back to non-differential storage
                        dependencies_added = hatch_dependencies
                        python_dependencies_added = python_dependencies
                        compatibility_changes = compatibility
                        dependencies_removed = []
                        dependencies_modified = []
                        python_dependencies_removed = []
                        python_dependencies_modified = []
                else:
                    # Fallback if base version data is missing
                    dependencies_added = hatch_dependencies
                    python_dependencies_added = python_dependencies
                    compatibility_changes = compatibility
                    dependencies_removed = []
                    dependencies_modified = []
                    python_dependencies_removed = []
                    python_dependencies_modified = []
            else:
                # No previous versions exist
                dependencies_added = hatch_dependencies
                python_dependencies_added = python_dependencies
                compatibility_changes = compatibility
                dependencies_removed = []
                dependencies_modified = []
                python_dependencies_removed = []
                python_dependencies_modified = []
        else:
            # First version - store complete information
            dependencies_added = hatch_dependencies
            python_dependencies_added = python_dependencies
            compatibility_changes = compatibility
            dependencies_removed = []
            dependencies_modified = []
            python_dependencies_removed = []
            python_dependencies_modified = []
        
        # Add the base version reference
        if base_version:
            version_data["base_version"] = base_version
        
        # Add differential data - using "hatch_dependencies" key to match package_validator.py
        if dependencies_added:
            version_data["hatch_dependencies_added"] = dependencies_added
        if dependencies_removed:
            version_data["hatch_dependencies_removed"] = dependencies_removed
        if dependencies_modified:
            version_data["hatch_dependencies_modified"] = dependencies_modified
            
        if python_dependencies_added:
            version_data["python_dependencies_added"] = python_dependencies_added
        if python_dependencies_removed:
            version_data["python_dependencies_removed"] = python_dependencies_removed
        if python_dependencies_modified:
            version_data["python_dependencies_modified"] = python_dependencies_modified
            
        if compatibility_changes:
            version_data["compatibility_changes"] = compatibility_changes
        
        return version_data