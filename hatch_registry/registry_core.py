#!/usr/bin/env python3
import os
import json
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from .registry_diff import RegistryDiff

class RegistryCoreError(Exception):
    """Base exception for registry core operations."""
    pass

class RegistryCore:
    """Core registry operations and data management."""
    
    def __init__(self, registry_path: Path):
        """
        Initialize the registry core.
        
        Args:
            registry_path: Path to the registry JSON file
        """
        self.logger = logging.getLogger("hatch.registry.core")
        self.registry_path = registry_path
        self.registry_data = self._load_registry()
    
    def _load_registry(self) -> dict:
        """
        Load the registry data from file.
        
        Returns:
            dict: Registry data
        """
        if not self.registry_path.exists():
            self.logger.info(f"Registry file not found, creating new: {self.registry_path}")
            # Create a new empty registry
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
            
            # Save the new registry file
            try:
                os.makedirs(self.registry_path.parent, exist_ok=True)
                with open(self.registry_path, 'w') as f:
                    json.dump(registry_data, f, indent=2)
                return registry_data
            except Exception as e:
                msg = f"Failed to create registry file: {e}"
                self.logger.error(msg)
                raise RegistryCoreError(msg) from e
                
        try:
            with open(self.registry_path, 'r') as f:
                registry_data = json.load(f)
                
            # Ensure stats field exists
            if "stats" not in registry_data:
                registry_data["stats"] = {
                    "total_packages": 0,
                    "total_versions": 0,
                    "total_artifacts": 0
                }
            
            return registry_data
                
        except Exception as e:
            msg = f"Failed to load registry file: {e}"
            self.logger.error(msg)
            raise RegistryCoreError(msg) from e
    
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
            with open(self.registry_path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
                
        except Exception as e:
            self.logger.error(f"Failed to save registry file: {e}")
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
            if repo.get("name") == name:
                self.logger.warning(f"Repository {name} already exists")
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
        self.logger.debug(f"Searching for repository {repo_name}")
        for repo in self.registry_data.get("repositories", []):
            if repo.get("name") == repo_name:
                return repo
        self.logger.debug(f"Repository {repo_name} not found")
        return None
    
    def update_repository_timestamp(self, repo_name: str) -> bool:
        """
        Update the last_indexed timestamp of a repository.
        
        Args:
            repo_name: Repository name
            
        Returns:
            bool: True if successful, False if repository not found
        """
        repo = self.find_repository(repo_name)
        if repo:
            repo["last_indexed"] = datetime.datetime.now().isoformat()
            self._save_registry()
            return True
        return False
    
    def remove_repository(self, repo_name: str) -> bool:
        """
        Remove a repository from the registry.
        
        Args:
            repo_name: Repository name
            
        Returns:
            bool: True if successful, False if repository not found
        """
        initial_count = len(self.registry_data.get("repositories", []))
        self.registry_data["repositories"] = [
            repo for repo in self.registry_data.get("repositories", [])
            if repo.get("name") != repo_name
        ]
        
        if len(self.registry_data.get("repositories", [])) < initial_count:
            self._save_registry()
            self.logger.info(f"Removed repository {repo_name} from registry")
            return True
            
        self.logger.warning(f"Repository {repo_name} not found, nothing removed")
        return False
    
    def find_package(self, repo_name: str, package_name: str) -> Optional[dict]:
        """
        Find a package in a repository.
        
        Args:
            repo_name: Repository name
            package_name: Package name
            
        Returns:
            dict: Package data or None if not found
        """
        self.logger.debug(f"Searching for package {package_name} in repository {repo_name}")
        repo = self.find_repository(repo_name)
        if repo:
            for pkg in repo.get("packages", []):
                if pkg.get("name") == package_name:
                    return pkg
        self.logger.debug(f"Package {package_name} not found in repository {repo_name}")
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
        self.logger.debug(f"Searching for version {version} for package {package_name} in repository {repo_name}")
        pkg = self.find_package(repo_name, package_name)
        if pkg:
            for ver in pkg.get("versions", []):
                if ver.get("version") == version:
                    return ver
        self.logger.debug(f"Version {version} not found for package {package_name} in repository {repo_name}")
        return None
    
    def remove_package(self, repo_name: str, package_name: str) -> bool:
        """
        Remove a package from a repository.
        
        Args:
            repo_name: Repository name
            package_name: Package name
            
        Returns:
            bool: True if successful, False if package or repository not found
        """
        repo = self.find_repository(repo_name)
        if not repo:
            self.logger.warning(f"Repository {repo_name} not found, cannot remove package")
            return False
            
        initial_count = len(repo.get("packages", []))
        repo["packages"] = [
            pkg for pkg in repo.get("packages", []) 
            if pkg.get("name") != package_name
        ]
        
        if len(repo.get("packages", [])) < initial_count:
            self._save_registry()
            self.logger.info(f"Removed package {package_name} from repository {repo_name}")
            return True
            
        self.logger.warning(f"Package {package_name} not found in repository {repo_name}")
        return False
    
    def remove_version(self, repo_name: str, package_name: str, version: str) -> bool:
        """
        Remove a specific version of a package.
        
        Args:
            repo_name: Repository name
            package_name: Package name
            version: Version string
            
        Returns:
            bool: True if successful, False if not found
        """
        pkg = self.find_package(repo_name, package_name)
        if not pkg:
            self.logger.warning(f"Package {package_name} not found in repository {repo_name}")
            return False
            
        initial_count = len(pkg.get("versions", []))
        pkg["versions"] = [
            ver for ver in pkg.get("versions", [])
            if ver.get("version") != version
        ]
        
        if len(pkg.get("versions", [])) < initial_count:
            # Update latest version if needed
            if pkg.get("latest_version") == version:
                # Find new latest version based on date added
                if pkg.get("versions"):
                    latest = max(pkg.get("versions", []), 
                               key=lambda v: v.get("added_date", ""))
                    pkg["latest_version"] = latest.get("version")
                else:
                    pkg["latest_version"] = ""
                    
            # Update stats
            self.registry_data["stats"]["total_versions"] -= 1
                
            self._save_registry()
            self.logger.info(f"Removed version {version} from package {package_name}")
            return True
            
        self.logger.warning(f"Version {version} not found in package {package_name}")
        return False
    
    def add_package(self, repo_name: str, package_metadata: Dict[str, Any],
                    author: Optional[Dict[str, str]] = None,
                    ) -> bool:
        """
        Add a new package to the repository.
        
        Args:
            repo_name: Repository name
            package_metadata: Package metadata dictionary containing at least 'name' and description fields
            author: Optional dictionary containing author information with GitHub username and email. If not
                provided, tries to load from package metadata, although it might just be 'name' and 'email'.

        Returns:
            bool: True if the package was added successfully
        """
        # Check if repository exists
        repo = self.find_repository(repo_name)
        if not repo:
            self.logger.error(f"Repository {repo_name} not found")
            return False
            
        # Check if package already exists
        package_name = package_metadata.get("name")
        if not package_name:
            self.logger.error("Package metadata missing 'name' field")
            return False
            
        if self.find_package(repo_name, package_name):
            self.logger.warning(f"Package {package_name} already exists in repository {repo_name}")
            return False
        
        # Ensure author is provided
        if not author:
            author = {
                "GitHubID": package_metadata.get("author").get("name"),
                "email": package_metadata.get("author").get("email"),
            }

        # Create package entry
        package = {
            "name": package_name,
            "description": package_metadata.get("description", ""),
            "tags": package_metadata.get("tags", []),
            "versions": [
                {
                    "author": author,
                    "release_uri": f"https://github.com/CrackingShells/{repo_name}/releases/download/{package_name}-v{package_metadata['version']}/{package_name}-v{package_metadata['version']}.zip",
                    "version": package_metadata["version"],
                    "added_date": datetime.datetime.now().isoformat(),
                    "hatch_dependencies_added": package_metadata.get("hatch_dependencies", []),
                    "python_dependencies_added": package_metadata.get("python_dependencies", []),
                    "compatibility_changes": package_metadata.get("compatibility", {}),
                }
            ],
            "latest_version": package_metadata["version"],
        }
        
        # Add package to repository
        repo["packages"].append(package)
        
        # Update stats
        self.registry_data["stats"]["total_packages"] += 1
        self.registry_data["stats"]["total_versions"] += 1
        
        # Save registry
        self._save_registry()
        self.logger.info(f"Added package {package_name} to repository {repo_name}")
        return True
    
    def update_package_metadata(self, repo_name: str, package_name: str, metadata_updates: Dict[str, Any]) -> bool:
        """
        Update metadata for an existing package.
        
        Args:
            repo_name: Repository name
            package_name: Package name
            metadata_updates: Dictionary containing metadata fields to update
            
        Returns:
            bool: True if the package was updated successfully
        """
        # Find the package
        pkg = self.find_package(repo_name, package_name)
        if not pkg:
            self.logger.error(f"Package {package_name} not found in repository {repo_name}")
            return False
            
        # Update allowed fields
        allowed_fields = ["description", "tags"]
        updated = False
        
        for field in allowed_fields:
            if field in metadata_updates:
                pkg[field] = metadata_updates[field]
                updated = True
                
        if updated:
            self._save_registry()
            self.logger.info(f"Updated metadata for package {package_name} in repository {repo_name}")
            
        return updated
    
    def update_version(self, repo_name: str, package_name: str, version: str, updates: Dict[str, Any]) -> bool:
        """
        Update data for an existing version of a package.
        
        Args:
            repo_name: Repository name
            package_name: Package name
            version: Version string
            updates: Dictionary containing fields to update
            
        Returns:
            bool: True if the version was updated successfully
        """
        # Find the version
        ver_data = self.find_version(repo_name, package_name, version)
        if not ver_data:
            self.logger.error(f"Version {version} not found for package {package_name} in repository {repo_name}")
            return False
            
        # Update allowed fields - note: don't allow changing the version string itself
        restricted_fields = ["version"]
        updated = False
        
        for field, value in updates.items():
            if field not in restricted_fields:
                ver_data[field] = value
                updated = True
                
        if updated:
            self._save_registry()
            self.logger.info(f"Updated data for version {version} of package {package_name}")
            
        return updated
    
    def load_metadata(self, package_path: Path, metadata_path: str = "hatch_metadata.json") -> Dict[str, Any]:
        """
        Load metadata from a package directory.
        
        Args:
            package_path: Path to package directory
            metadata_path: Relative path to metadata file
            
        Returns:
            dict: Metadata or empty dict if not found
        """
        try:
            metadata_file_path = package_path / metadata_path
            if not metadata_file_path.exists():
                self.logger.error(f"Metadata file not found: {metadata_file_path}")
                return {}
                
            with open(metadata_file_path, 'r') as f:
                metadata = json.load(f)
                return metadata
                
        except Exception as e:
            self.logger.error(f"Failed to load metadata: {e}")
            return {}
    

    def _prepare_registry_version_diff_data(self, repo_name: str, package_metadata: dict) -> Dict[str, Any]:
        """
        Prepare version data for storage in the registry.
        
        Args:
            repo_name: Repository name
            package_metadata: Package metadata
            
        Returns:
            Dictionary containing version data
        """

        # Get dependencies from the package metadata
        hatch_dependencies = package_metadata.get("hatch_dependencies", [])
        python_dependencies = package_metadata.get("python_dependencies", [])
        compatibility = package_metadata.get("compatibility", {})

        # Initialize dependency and compatibility changes
        hatch_dependencies_added, hatch_dependencies_removed, hatch_dependencies_modified = [], [], []
        python_dependencies_added, python_dependencies_removed, python_dependencies_modified = [], [], []
        compatibility_changes = {}
            
        # Get the latest version info
        pkg = self.find_package(repo_name, package_metadata['name'])
        
        # Add the base version reference
        diff_data = {
            "base_version": pkg["latest_version"]
        }

        # Get the diff info from the latest package version
        latest_pkg_diff_info = pkg["versions"][-1]

        # Work on the diff data
        reg_diff = RegistryDiff(self.registry_data)

        # Reconstruct the dependencies and compatibility from the latest version
        latest_pkg_all_info = reg_diff.reconstruct_package_version(pkg, latest_pkg_diff_info)
                
        # Compute diffs for dependencies
        hatch_dependencies_added, hatch_dependencies_removed, hatch_dependencies_modified = reg_diff.compute_dependency_diff(
            latest_pkg_all_info["hatch_dependencies"],
            hatch_dependencies
        )
        
        # Compute diffs for Python dependencies
        python_dependencies_added, python_dependencies_removed, python_dependencies_modified = reg_diff.compute_python_dependency_diff(
            latest_pkg_all_info["python_dependencies"],
            python_dependencies
        )

        # Compute diffs for compatibility
        compatibility_changes = reg_diff.compute_compatibility_diff(
            latest_pkg_all_info["compatibility"],
            compatibility
        )
        
        # Add differential data - using "hatch_dependencies" key to match package_validator.py
        if hatch_dependencies_added:
            diff_data["hatch_dependencies_added"] = hatch_dependencies_added
        if hatch_dependencies_removed:
            diff_data["hatch_dependencies_removed"] = hatch_dependencies_removed
        if hatch_dependencies_modified:
            diff_data["hatch_dependencies_modified"] = hatch_dependencies_modified

        if python_dependencies_added:
            diff_data["python_dependencies_added"] = python_dependencies_added
        if python_dependencies_removed:
            diff_data["python_dependencies_removed"] = python_dependencies_removed
        if python_dependencies_modified:
            diff_data["python_dependencies_modified"] = python_dependencies_modified
            
        if compatibility_changes:
            diff_data["compatibility_changes"] = compatibility_changes
        
        return diff_data

    def add_new_package_version(self, repo_name: str, package_metadata: Dict[str, Any],
                                author: Optional[Dict[str, str]] = None
                                ) -> bool:
        """
        Update or add a version of a package.
        
        Args:
            repo_name: Repository name
            package_metadata: Package metadata dictionary
            author: Optional dictionary containing author information
                with GitHub username and email. If not provided, tries to load from package metadata.
        Returns:
            bool: True if successful
        """
        # Check if repository exists
        repo = self.find_repository(repo_name)
        if not repo:
            self.logger.error(f"Repository {repo_name} not found")
            return False

        # Check if the version already exists (basic validation)
        if self.find_version(repo_name, package_metadata['name'], package_metadata['version']):
            self.logger.error(f"Version {package_metadata['version']} of package {package_metadata['name']} already exists")
            return False
        
        # Ensure author is provided
        if not author:
            author = {
                "GitHubID": package_metadata.get("author").get("name"),
                "email": package_metadata.get("author").get("email"),
            }
        
        version_data = {
            "author": author,
            "release_uri": f"https://github.com/CrackingShells/{repo_name}/releases/download/{package_metadata['name']}-v{package_metadata['version']}/{package_metadata['name']}-v{package_metadata['version']}.zip",
            "version": package_metadata['version'],
            "added_date": datetime.datetime.now().isoformat()
        }

        # Compute dependency diffs
        registry_version_diff_data = self._prepare_registry_version_diff_data(repo_name, package_metadata)

        self.logger.debug(f"Version data prepared for {package_metadata['name']}: {registry_version_diff_data}")

        version_data.update(registry_version_diff_data)
        
        # Add new version to package
        pkg = self.find_package(repo_name, package_metadata['name'])
        pkg["versions"].append(version_data) # this will propagate back to self.registry_data by reference
        pkg["latest_version"] = package_metadata['version']
            
        # Update stats
        self.registry_data["stats"]["total_versions"] += 1
        
        self.logger.debug(f"Current registry is: {json.dumps(self.registry_data, indent=2)}")

        # Save registry
        self._save_registry()

        return True
