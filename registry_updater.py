#!/usr/bin/env python3
import os
import sys
import json
import logging
import datetime  # Make sure to import the datetime module properly
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Import Hatch modules
from hatch_validator import HatchPackageValidator, DependencyResolver


class RegistryUpdateError(Exception):
    """Exception raised for registry update errors."""
    pass


class RegistryUpdater:
    """
    Updates the Hatch package registry with new packages and versions,
    using differential storage for version metadata.
    """
    
    def __init__(self, registry_path: Path):
        """
        Initialize the registry updater.
        
        Args:
            registry_path: Path to the registry JSON file
        """
        self.logger = logging.getLogger("hatch.registry_updater")
        self.registry_path = registry_path
        self.registry_data = self._load_registry()
        
    def _load_registry(self) -> dict:
        """
        Load the registry data from file.
        
        Returns:
            dict: Registry data
        """
        if not self.registry_path.exists():
            # Create a new registry file if it doesn't exist
            self.logger.info(f"Creating new registry at {self.registry_path}")
            registry_data = {
                "registry_schema_version": "1.0.0",
                "last_updated": datetime.datetime.now().isoformat(),
                "repositories": [],
                "stats": {
                    "total_packages": 0,
                    "total_versions": 0,
                    "total_artifacts": 0
                }
            }
            self._save_registry(registry_data)
            return registry_data
            
        try:
            with open(self.registry_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load registry: {e}")
            raise
    
    def _save_registry(self, data: dict = None) -> bool:
        """
        Save registry data to file.
        
        Args:
            data: Registry data to save. If None, uses self.registry_data
            
        Returns:
            bool: True if successful
        """
        if data is None:
            data = self.registry_data
            
        # Update the timestamp
        data["last_updated"] = datetime.datetime.now().isoformat()
        
        try:
            # Ensure parent directory exists
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.registry_path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"Failed to save registry: {e}")
            return False
    
    def add_repository(self, name: str, url: str) -> bool:
        """
        Add a new repository to the registry.
        
        Args:
            name: Repository name
            url: Repository URL
            
        Returns:
            bool: True if the repository was added, False if it already exists
        """
        # Check if repository already exists
        for repo in self.registry_data.get("repositories", []):
            if repo["name"] == name:
                self.logger.info(f"Repository {name} already exists in registry")
                return False
        
        # Add the repository
        repository = {
            "name": name,
            "url": url,
            "packages": [],
            "last_indexed": datetime.datetime.now().isoformat()
        }
        
        self.registry_data.setdefault("repositories", []).append(repository)
        self._save_registry()
        
        self.logger.info(f"Added repository {name} to registry")
        return True
    
    def find_repository(self, repo_name: str) -> Optional[dict]:
        """
        Find a repository in the registry by name.
        
        Args:
            repo_name: Repository name
            
        Returns:
            dict: Repository data or None if not found
        """
        for repo in self.registry_data.get("repositories", []):
            if repo["name"] == repo_name:
                return repo
        return None
    
    def find_package(self, repo_name: str, package_name: str) -> Optional[dict]:
        """
        Find a package in a repository.
        
        Args:
            repo_name: Repository name
            package_name: Package name
            
        Returns:
            dict: Package data or None if not found
        """
        repo = self.find_repository(repo_name)
        if repo:
            for pkg in repo.get("packages", []):
                if pkg["name"] == package_name:
                    return pkg
        return None
    
    def find_version(self, repo_name: str, package_name: str, version: str) -> Optional[dict]:
        """
        Find a specific version of a package.
        
        Args:
            repo_name: Repository name
            package_name: Package name
            version: Version string
            
        Returns:
            dict: Version data or None if not found
        """
        pkg = self.find_package(repo_name, package_name)
        if pkg:
            for ver in pkg.get("versions", []):
                if ver["version"] == version:
                    return ver
        return None
    
    def _compute_generic_diff(self, old_items: List[Dict[str, Any]], 
                             new_items: List[Dict[str, Any]],
                             key_field: str = "name",
                             diff_fields: List[str] = None) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
        """
        Generic method to compute differences between lists of dictionaries.
        
        Args:
            old_items: List of old items (dictionaries)
            new_items: List of new items (dictionaries)
            key_field: The dictionary key to use for identifying items
            diff_fields: List of fields to check for differences
            
        Returns:
            Tuple of (added_items, removed_items, modified_items)
        """
        if diff_fields is None:
            diff_fields = []
            
        # Create dictionaries for comparison
        old_dict = {item[key_field]: item for item in old_items}
        new_dict = {item[key_field]: item for item in new_items}
        
        # Find added items
        added_keys = set(new_dict.keys()) - set(old_dict.keys())
        added = [new_dict[key] for key in added_keys]
        
        # Find removed items
        removed_keys = set(old_dict.keys()) - set(new_dict.keys())
        removed = list(removed_keys)
        
        # Find modified items
        modified = []
        for key in set(old_dict.keys()) & set(new_dict.keys()):
            old_item = old_dict[key]
            new_item = new_dict[key]
            
            # Check if any fields are different
            is_modified = False
            if diff_fields:
                for field in diff_fields:
                    if field in old_item and field in new_item:
                        if old_item[field] != new_item[field]:
                            is_modified = True
                            break
                    elif field in old_item or field in new_item:
                        is_modified = True
                        break
            else:
                # If no fields specified, compare entire dictionaries
                is_modified = old_item != new_item
                
            if is_modified:
                modified.append(new_item)
                
        return added, removed, modified
    
    def compute_dependency_diff(self, old_deps: List[Dict[str, str]], 
                              new_deps: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], List[str], List[Dict[str, str]]]:
        """
        Compute the difference between two sets of dependencies.
        
        Args:
            old_deps: List of old dependencies [{"name": "pkg", "version_constraint": ">=1.0"}, ...]
            new_deps: List of new dependencies
            
        Returns:
            Tuple of (added_deps, removed_deps, modified_deps)
        """
        return self._compute_generic_diff(old_deps, new_deps, key_field="name", diff_fields=["version_constraint"])
    
    def compute_python_dependency_diff(self, old_deps: List[Dict[str, Any]], 
                                     new_deps: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
        """
        Compute the difference between two sets of Python dependencies.
        
        Args:
            old_deps: List of old Python dependencies
            new_deps: List of new Python dependencies
            
        Returns:
            Tuple of (added_deps, removed_deps, modified_deps)
        """
        return self._compute_generic_diff(old_deps, new_deps, key_field="name", 
                                        diff_fields=["version_constraint", "package_manager"])
    
    def compute_compatibility_diff(self, old_compat: Dict[str, str], 
                                 new_compat: Dict[str, str]) -> Dict[str, str]:
        """
        Compute the difference between compatibility information.
        
        Args:
            old_compat: Old compatibility data
            new_compat: New compatibility data
            
        Returns:
            Dict of changed compatibility constraints
        """
        changes = {}
        
        for key in ["hatchling", "python"]:
            old_val = old_compat.get(key, "")
            new_val = new_compat.get(key, "")
            
            if old_val != new_val:
                changes[key] = new_val
                
        return changes
    
    def add_package(self, repo_name: str, package_dir: Path, metadata_path: str = "hatch_metadata.json") -> bool:
        """
        Add a new package to the registry.
        
        Args:
            repo_name: Repository name
            package_dir: Path to the package directory
            metadata_path: Relative path to the metadata file
            
        Returns:
            bool: True if the package was added successfully
        """
        repo = self.find_repository(repo_name)
        if not repo:
            self.logger.error(f"Repository {repo_name} not found")
            return False
        
        is_valid, results, metadata = self._validate_package(package_dir)
        
        if not is_valid:
            return False
            
        # Extract required metadata fields
        package_name = metadata.get("name")
        version = metadata.get("version")
        
        # Check if package already exists
        existing_pkg = self.find_package(repo_name, package_name)
        if existing_pkg:
            self.logger.info(f"Package {package_name} already exists, adding version {version}")
            return self.add_package_version(repo_name, package_name, metadata, str(package_dir), metadata_path)
        
        # Create new package entry
        package = {
            "name": package_name,
            "description": metadata.get("description", ""),
            "category": metadata.get("category", ""),
            "tags": metadata.get("tags", []),
            "versions": [],
            "latest_version": version
        }
        
        # Add the package to the repository
        repo["packages"].append(package)
        
        # Add the first version (no differential, contains all data)
        self.add_package_version(repo_name, package_name, metadata, str(package_dir), metadata_path, is_first_version=True)
        
        # Update stats
        self.registry_data["stats"]["total_packages"] += 1
        
        self._save_registry()
        self.logger.info(f"Added package {package_name} to repository {repo_name}")
        
        return True
    
    def add_package_version(self, repo_name: str, package_name: str, metadata: dict, 
                          package_path: str, metadata_path: str = "hatch_metadata.json",
                          is_first_version: bool = False) -> bool:
        """
        Add a new version of an existing package using differential storage.
        
        Args:
            repo_name: Repository name
            package_name: Package name
            metadata: Package metadata
            package_path: Path to the package
            metadata_path: Relative path to the metadata file
            is_first_version: If True, this is the first version of the package
            
        Returns:
            bool: True if the version was added successfully
        """
        pkg = self.find_package(repo_name, package_name)
        if not pkg:
            self.logger.error(f"Package {package_name} not found in repository {repo_name}")
            return False
        
        version = metadata.get("version")
        if not version:
            self.logger.error("Missing version in metadata")
            return False
            
        # Check if version already exists
        if self.find_version(repo_name, package_name, version):
            self.logger.warning(f"Version {version} of package {package_name} already exists")
            return False
            
        # Perform additional validation on the package version
        package_dir = Path(package_path)
        if not package_dir.exists() or not package_dir.is_dir():
            self.logger.error(f"Package directory does not exist: {package_path}")
            return False
            
        is_valid, results, metadata = self._validate_package(package_dir)
        
        if not is_valid:
            return False
        
        # Verify that the version in metadata matches the version provided
        if metadata.get("version") != version:
            self.logger.error(f"Version mismatch: {metadata.get('version')} in metadata vs {version} provided")
            return False
            
        # Check for circular dependencies when updating the registry
        if not self._check_circular_dependencies(package_name, version):
            return False

        # Prepare version data
        version_data = self._prepare_version_data(repo_name, package_name, metadata, package_path, metadata_path, is_first_version)
        
        # Add the version to the package
        pkg["versions"].append(version_data)
        
        # Update latest version
        pkg["latest_version"] = version
        
        # Update stats
        self.registry_data["stats"]["total_versions"] += 1
        self.registry_data["stats"]["total_artifacts"] += len(version_data["artifacts"])
        
        self._save_registry()
        self.logger.info(f"Added version {version} to package {package_name}")
        
        return True
    
    def _prepare_version_data(self, repo_name: str, package_name: str, metadata: dict,
                           package_path: str, metadata_path: str, is_first_version: bool) -> Dict[str, Any]:
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
        # Initialize with base metadata that's the same for all versions
        version = metadata.get("version")
        artifacts = []  # TODO: Add actual artifacts
        
        version_data = {
            "version": version,
            "path": package_path,
            "metadata_path": metadata_path,
            "artifacts": artifacts,
            "added_date": datetime.datetime.now().isoformat()
        }
        
        # Get dependencies for the package
        dependencies_added = metadata.get("dependencies", [])
        dependencies_removed = []
        dependencies_modified = []
        
        python_dependencies_added = metadata.get("python_dependencies", [])
        python_dependencies_removed = []
        python_dependencies_modified = []
        
        compatibility_changes = metadata.get("compatibility", {})
        base_version = None
        
        # For differential storage, compute changes from base version
        if not is_first_version:
            pkg = self.find_package(repo_name, package_name)
            if pkg and pkg.get("versions"):
                base_version = pkg["latest_version"]
                base_version_data = self.find_version(repo_name, package_name, base_version)
                
                if base_version_data:
                    # Load the full base version metadata to compute diffs
                    base_metadata_path = os.path.join(base_version_data["path"], base_version_data["metadata_path"])
                    
                    try:
                        with open(base_metadata_path, 'r') as f:
                            base_metadata = json.load(f)
                            
                        # Compute diffs for dependencies
                        dependencies_added, dependencies_removed, dependencies_modified = self.compute_dependency_diff(
                            base_metadata.get("dependencies", []),
                            metadata.get("dependencies", [])
                        )
                        
                        # Compute diffs for Python dependencies
                        python_dependencies_added, python_dependencies_removed, python_dependencies_modified = self.compute_python_dependency_diff(
                            base_metadata.get("python_dependencies", []),
                            metadata.get("python_dependencies", [])
                        )
                        
                        # Compute diffs for compatibility
                        compatibility_changes = self.compute_compatibility_diff(
                            base_metadata.get("compatibility", {}),
                            metadata.get("compatibility", {})
                        )
                        
                    except Exception as e:
                        self.logger.error(f"Error computing diffs: {e}")
                        # Fall back to non-differential storage
                        is_first_version = True
        
        # Add the base version reference
        if base_version:
            version_data["base_version"] = base_version
        
        # Add differential data if not the first version
        if not is_first_version:
            if dependencies_added:
                version_data["dependencies_added"] = dependencies_added
            if dependencies_removed:
                version_data["dependencies_removed"] = dependencies_removed
            if dependencies_modified:
                version_data["dependencies_modified"] = dependencies_modified
                
            if python_dependencies_added:
                version_data["python_dependencies_added"] = python_dependencies_added
            if python_dependencies_removed:
                version_data["python_dependencies_removed"] = python_dependencies_removed
            if python_dependencies_modified:
                version_data["python_dependencies_modified"] = python_dependencies_modified
                
            if compatibility_changes:
                version_data["compatibility_changes"] = compatibility_changes
        else:
            # For first version, store complete dependency information
            version_data["dependencies_added"] = metadata.get("dependencies", [])
            version_data["python_dependencies_added"] = metadata.get("python_dependencies", [])
            version_data["compatibility_changes"] = metadata.get("compatibility", {})
        
        return version_data
    
    def update_repository_timestamp(self, repo_name: str) -> bool:
        """
        Update the last_indexed timestamp for a repository.
        
        Args:
            repo_name: Repository name
            
        Returns:
            bool: True if successful
        """
        repo = self.find_repository(repo_name)
        if repo:
            repo["last_indexed"] = datetime.datetime.now().isoformat()
            self._save_registry()
            return True
        return False
    
    def _validate_package(self, package_dir: Path) -> Tuple[bool, Optional[dict], Optional[dict]]:
        """
        Validate a package against schemas and check for circular dependencies.
        
        Args:
            package_dir: Path to the package directory
            
        Returns:
            Tuple of (is_valid, validation_results, metadata)
        """
        # Validate the package - disallow local dependencies for registry packages
        validator = HatchPackageValidator(allow_local_dependencies=False)
        is_valid, results = validator.validate_package(package_dir)
        
        if not is_valid:
            # Log validation errors
            self._log_validation_errors(results, "Package validation failed")
            return False, results, None
            
        # Load the metadata
        metadata = results['metadata']
        
        # Extract required metadata fields
        package_name = metadata.get("name")
        version = metadata.get("version")
        
        if not package_name or not version:
            self.logger.error(f"Missing required metadata fields (name, version)")
            return False, results, None
            
        # Check for circular dependencies
        if not self._check_circular_dependencies(package_name, version):
            return False, results, None
                
        return True, results, metadata
    
    def _check_circular_dependencies(self, package_name: str, version: str) -> bool:
        """
        Check for circular dependencies in a package.
        
        Args:
            package_name: Name of the package
            version: Version of the package
            
        Returns:
            bool: True if no circular dependencies found
        """
        try:
            # Create a dependency resolver that uses our registry
            resolver = DependencyResolver(registry_path=self.registry_path)
            
            # Check for circular dependencies
            has_circular, cycle = resolver.check_circular_dependencies(
                package_name, 
                version
            )
            
            if has_circular:
                self.logger.error(f"Circular dependency detected: {' -> '.join(cycle)}")
                return False
                
            return True
        except Exception as e:
            self.logger.error(f"Error checking for circular dependencies: {e}")
            return False
    
    def _log_validation_errors(self, results: dict, message: str) -> None:
        """
        Log validation errors in a structured way.
        
        Args:
            results: Validation results dictionary
            message: Header message for the validation errors
        """
        self.logger.error(message)
        for section in ['metadata_schema', 'entry_point', 'dependencies', 'tools']:
            if section in results and not results[section]['valid']:
                for error in results[section]['errors']:
                    self.logger.error(f"  {section.replace('_', ' ').title()} error: {error}")


if __name__ == "__main__":
    # Simple CLI for testing
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <registry_file>")
        sys.exit(1)
        
    registry_path = Path(sys.argv[1])
    updater = RegistryUpdater(registry_path)
    
    # Example: Add a repository
    # updater.add_repository("Hatch-Dev", "https://github.com/user/hatch-dev")
    
    print(f"Registry loaded: {registry_path}")
    print(f"Contains {len(updater.registry_data.get('repositories', []))} repositories")
    print(f"Total packages: {updater.registry_data.get('stats', {}).get('total_packages', 0)}")
    print(f"Total versions: {updater.registry_data.get('stats', {}).get('total_versions', 0)}")