#!/usr/bin/env python3
from typing import Dict, Any, List, Tuple, Optional
import logging

# Import Hatch modules
from hatch_validator import DependencyResolver

class RegistryDiffError(Exception):
    """Exception for differential storage operations."""
    pass

class RegistryDiff:
    """Handles differential storage calculations for registry versions."""
    
    def __init__(self, registry_data: dict = None):
        """
        Initialize the registry diff calculator.
        
        Args:
            registry_data: Optional registry data for dependency resolution
        """
        self.logger = logging.getLogger("hatch.registry.diff")
        self.registry_data = registry_data
    
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
            
            # Check if any of the diff fields changed
            for field in diff_fields:
                if old_item.get(field) != new_item.get(field):
                    modified.append(new_item)
                    break
                
        return added, removed, modified
    
    def compute_dependency_diff(self, old_deps: List[Dict[str, str]], 
                              new_deps: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], List[str], List[Dict[str, str]]]:
        """
        Compute the difference between two sets of dependencies
        
        Args:
            old_deps: List of old dependencies [{"name": "pkg", "version_constraint": ">=1.0"}, ...]
            new_deps: List of new dependencies
            
        Returns:
            Tuple of (added_deps, removed_deps, modified_deps)
        """
        
        # Use generic diff computation
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
        
        # Use generic diff computation with proper fields for Python dependencies
        return self._compute_generic_diff(old_deps, new_deps, key_field="name", 
                                        diff_fields=["version_constraint", "package_manager"])
    
    def compute_compatibility_diff(self, old_compat: Dict[str, str], 
                                 new_compat: Dict[str, str]) -> Dict[str, str]:
        """
        Compute the difference between compatibility information.
        
        Args:
            old_compat: Old compatibility data containing hatchling and python version constraints
            new_compat: New compatibility data containing hatchling and python version constraints
            
        Returns:
            Dict[str, str]: Dictionary of changed compatibility constraints
        """
        changes = {}
        
        for key in ["hatchling", "python"]:
            old_val = old_compat.get(key, "")
            new_val = new_compat.get(key, "")
            
            if old_val != new_val:
                changes[key] = new_val
                
        return changes

    def reconstruct_package_version(self, package: Dict[str, Any], version_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Reconstruct complete package metadata for a specific version by walking the diff tree.
        If version is not specified, uses the latest version.
        
        Args:
            package: Package object from the registry
            version_info: Specific version information from which to start reconstruction

        Returns:
            Dict[str, Any]: Reconstructed package metadata including dependencies and compatibility
            
        Raises:
            RegistryDiffError: If version not found or reconstruction fails
        """

        if not package:
            msg = "No package data provided"
            self.logger.error(msg)
            raise RegistryDiffError(msg)
        
        # If version not specified, use latest
        if version_info is None:
            version_info = package["versions"][-1]

        package_versions = package["versions"]

        version_chain = []
        while version_info.get("base_version"):
            version_chain += [version_info]
            base_version = version_info.get("base_version")
            # If no base version, we are at the root of the chain
            # and can stop
            if not base_version:
                break

            # Find the next version in the chain
            for ver in package_versions:
                if ver.get("version") == base_version:
                    version_info = ver
                    break
        
        # Now reconstruct the package metadata
        reconstructed = {
            "name": package["name"],
            "version": version_info["version"],
            "hatch_dependencies": [],
            "python_dependencies": [],
            "compatibility": {}
        }

        # Apply changes from each version in the chain
        for ver in reversed(version_chain): # version chain was built from latest to oldest
            # Process hatch dependencies
            # Apply diffs for Hatch dependencies
            # Add new dependencies
            for dep in ver.get("hatch_dependencies_added", []):
                reconstructed["hatch_dependencies"].append(dep)

            # Remove dependencies
            for dep_name in ver.get("hatch_dependencies_removed", []):
                reconstructed["hatch_dependencies"] = [
                    d for d in reconstructed["hatch_dependencies"] 
                    if d.get("name") != dep_name
                ]
                
            # Modify dependencies
            for mod_dep in ver.get("hatch_dependencies_modified", []):
                for i, dep in enumerate(reconstructed["hatch_dependencies"]):
                    if dep.get("name") == mod_dep.get("name"):
                        reconstructed["hatch_dependencies"][i] = mod_dep
                        break
            
            # Process Python dependencies
            # Apply diffs for Python dependencies
            # Add new dependencies
            for dep in ver.get("python_dependencies_added", []):
                reconstructed["python_dependencies"].append(dep)
                
            # Remove dependencies
            for dep_name in ver.get("python_dependencies_removed", []):
                reconstructed["python_dependencies"] = [
                    d for d in reconstructed["python_dependencies"] 
                    if d.get("name") != dep_name
                ]
                
            # Modify dependencies
            for mod_dep in ver.get("python_dependencies_modified", []):
                for i, dep in enumerate(reconstructed["python_dependencies"]):
                    if dep.get("name") == mod_dep.get("name"):
                        reconstructed["python_dependencies"][i] = mod_dep
                        break
            
            # Process compatibility info
            # Update compatibility with changes
            for key, value in ver.get("compatibility_changes", {}).items():
                reconstructed["compatibility"][key] = value

        self.logger.debug(f"Successfully reconstructed metadata for {package['name']} v{version_info['version']}")
        return reconstructed


