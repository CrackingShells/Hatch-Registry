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
