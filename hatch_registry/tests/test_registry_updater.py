#!/usr/bin/env python3
import os
import sys
import json
import logging
import tempfile
import unittest
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple

# Add parent directory to path if needed for direct testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from hatch_registry.registry_updater import RegistryUpdater

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("hatch.registry_tests")


class RegistryUpdaterTests(unittest.TestCase):
    """Tests for the registry updater functionality."""

    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary directory for test registry
        self.temp_dir = tempfile.mkdtemp()
        self.registry_path = Path(self.temp_dir) / "test_registry.json"
        
        # Create a test registry file
        test_registry = {
            "registry_schema_version": "1.0.0",
            "last_updated": datetime.now().isoformat(),
            "repositories": [],
            "stats": {
                "total_packages": 0,
                "total_versions": 0,
                "total_artifacts": 0
            }
        }
        
        with open(self.registry_path, 'w') as f:
            json.dump(test_registry, f, indent=2)
            
        # Path to Hatching-Dev packages
        self.hatch_dev_path = Path(__file__).parent.parent.parent.parent / "Hatching-Dev"
        self.assertTrue(self.hatch_dev_path.exists(), 
                       f"Hatching-Dev directory not found at {self.hatch_dev_path}")
        
        # Initialize registry updater
        self.registry_updater = RegistryUpdater(self.registry_path)
        
        # Add a test repository
        self.repo_name = "test-repo"
        self.registry_updater.core.add_repository(self.repo_name, "file:///test-repo")
        
    def tearDown(self):
        """Clean up test environment after each test."""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)
    
    def test_add_valid_package(self):
        """Test adding a valid package to the registry."""
        # Test with arithmetic_pkg which should have no dependency issues
        package_path = self.hatch_dev_path / "arithmetic_pkg"
        self.assertTrue(package_path.exists(), f"Test package not found: {package_path}")
        
        # Add the package using the new public API
        result, _ = self.registry_updater.validate_and_add_package(self.repo_name, package_path)
        
        # Check that the package was added successfully
        self.assertTrue(result, "Failed to add valid package")
        
        # Verify the package is in the registry
        pkg = self.registry_updater.core.find_package(self.repo_name, "arithmetic_pkg")
        self.assertIsNotNone(pkg, "Package not found in registry")
        self.assertEqual(pkg["name"], "arithmetic_pkg")
        
        # Verify stats were updated
        stats = self.registry_updater.core.registry_data["stats"]
        self.assertEqual(stats["total_packages"], 1)
        self.assertEqual(stats["total_versions"], 1)

        # Finally, test for the integrity of the registry
        is_valid, validation_results = self.registry_updater.validator.validate_registry()
        self.assertTrue(is_valid, "Registry validation failed after adding a valid package")
    
    def test_add_simple_dependency_package(self):
        """Test adding a package with simple dependencies."""        # First add the base package that will be a dependency
        base_pkg_path = self.hatch_dev_path / "base_pkg_1"
        result, _ = self.registry_updater.validate_and_add_package(self.repo_name, base_pkg_path)
        self.assertTrue(result, "Failed to add base package")
        
        # Then add a package that depends on it
        dependent_pkg_path = self.hatch_dev_path / "simple_dep_pkg"
        result, _ = self.registry_updater.validate_and_add_package(self.repo_name, dependent_pkg_path)
        
        # Check that the dependent package was added successfully
        self.assertTrue(result, "Failed to add package with simple dependency")
        
        # Verify both packages are in the registry
        base_pkg = self.registry_updater.core.find_package(self.repo_name, "base_pkg_1")
        dep_pkg = self.registry_updater.core.find_package(self.repo_name, "simple_dep_pkg")

        self.assertIsNotNone(base_pkg, "Base package not found in registry")
        self.assertIsNotNone(dep_pkg, "Dependent package not found in registry")

        # Finally, test for the integrity of the registry
        is_valid, validation_results = self.registry_updater.validator.validate_registry()
        self.assertTrue(is_valid, "Registry validation failed after adding a chain of simple dependencies")
    
    def test_add_circular_dependency_package(self):
        """Test adding packages with circular dependencies."""        # First add circular_dep_pkg_2 which don't have any hatch_dependency from the start
        # This will be the base for which the next version (circular_dep_pkg_2_next_v)
        # will have a circular dependency on circular_dep_pkg_1
        pkg2_path = self.hatch_dev_path / "circular_dep_pkg_2"
        result, _ = self.registry_updater.validate_and_add_package(self.repo_name, pkg2_path)
        self.assertTrue(result, "Failed to add second circular dependency package")

        # Then, add circular_dep_pkg_1 which has a circular dependency on pkg2
        # This should work because circular_dep_pkg_2 has not yet a dependency on pkg1
        pkg1_path = self.hatch_dev_path / "circular_dep_pkg_1"
        result, _ = self.registry_updater.validate_and_add_package(self.repo_name, pkg1_path)
        self.assertTrue(result, "Failed to add first circular dependency package")

        # Finally, we are using the other package "circular_dep_pkg_2_next_v" which 
        # is the next version of circular_dep_pkg_2 and has an actual dependency on pkg1
        # as part of the version update.
        result, _ = self.registry_updater.validate_and_add_package(
            self.repo_name,
            self.hatch_dev_path/"circular_dep_pkg_2_next_v"
        )

        # This should fail due to circular dependency
        self.assertFalse(result, "Should have failed to add new version of circular_dep_pkg_2 with circular dependency to cirular_dep_pkg_1")

        # Finally, test for the integrity of the registry
        is_valid, validation_results = self.registry_updater.validator.validate_registry()
        self.assertTrue(is_valid, "Registry validation failed refusing circular dependency")

    def test_add_missing_dependency_package(self):
        """Test adding a package with a missing dependency."""
        # Try to add missing_dep_pkg which has a dependency that doesn't exist
        pkg_path = self.hatch_dev_path / "missing_dep_pkg"
        
        result, _ = self.registry_updater.validate_and_add_package(self.repo_name, pkg_path)
        
        # This should fail because of missing dependency
        self.assertFalse(result, "Should have failed to add package with missing dependency")
        
        # Verify the package is not in the registry
        pkg = self.registry_updater.core.find_package(self.repo_name, "missing_dep_pkg")
        self.assertIsNone(pkg, "Package with missing dependency should not be in registry")
        
        # Finally, test for the integrity of the registry
        is_valid, validation_results = self.registry_updater.validator.validate_registry()
        self.assertTrue(is_valid, "Registry validation failed after adding packages")
    
    def test_add_complex_dependencies(self):
        """Test adding a package with complex dependencies."""        # First add all the base packages
        for base_pkg in ["base_pkg_1", "base_pkg_2", "python_dep_pkg"]:
            pkg_path = self.hatch_dev_path / base_pkg
            if not pkg_path.exists():
                logger.warning(f"Base package not found: {pkg_path}")
                continue
                
            result, _ = self.registry_updater.validate_and_add_package(self.repo_name, pkg_path)
            self.assertTrue(result, f"Failed to add base package: {base_pkg}")
        
        # Now add the complex dependency package
        complex_pkg_path = self.hatch_dev_path / "complex_dep_pkg"
        
        result, _ = self.registry_updater.validate_and_add_package(self.repo_name, complex_pkg_path)
        
        # This should succeed because all dependencies are satisfied
        self.assertTrue(result, "Failed to add package with complex dependencies")
        
        # Verify the package is in the registry
        pkg = self.registry_updater.core.find_package(self.repo_name, "complex_dep_pkg")
        self.assertIsNotNone(pkg, "Complex dependency package not found in registry")

        # Finally, test for the integrity of the registry
        is_valid, validation_results = self.registry_updater.validator.validate_registry()
        self.assertTrue(is_valid, "Registry validation failed after adding complex dependencies")
    
    def test_add_version_dependency(self):
        """Test adding a package with version-specific dependencies."""        # First add the base package
        base_pkg_path = self.hatch_dev_path / "base_pkg_1"
        if not base_pkg_path.exists():
            logger.warning(f"Base package not found: {base_pkg_path}")
            return
            
        result, _ = self.registry_updater.validate_and_add_package(self.repo_name, base_pkg_path)
        self.assertTrue(result, "Failed to add base package")
        
        # Then add a package with version-specific dependency
        version_dep_pkg_path = self.hatch_dev_path / "version_dep_pkg"
        
        result, _ = self.registry_updater.validate_and_add_package(self.repo_name, version_dep_pkg_path)
        
        # Check if the addition was successful
        self.assertTrue(result, "Failed to add package with version-specific dependency")

        # Finally, test for the integrity of the registry
        is_valid, validation_results = self.registry_updater.validator.validate_registry()
        self.assertTrue(is_valid, "Registry validation failed adding version-specific dependencies")
    
    def test_add_duplicate_package_version(self):
        """Test adding the same package version twice."""        # Add a package
        pkg_path = self.hatch_dev_path / "arithmetic_pkg"
        if not pkg_path.exists():
            logger.warning(f"Arithmetic package not found: {pkg_path}")
            return
            
        result, _ = self.registry_updater.validate_and_add_package(self.repo_name, pkg_path)
        self.assertTrue(result, "Failed to add package")
        
        # Try to add the same package version again
        result, _ = self.registry_updater.validate_and_add_package(self.repo_name, pkg_path)
        
        # This should return False but not raise an exception
        self.assertFalse(result, "Should have failed to add duplicate package version")
        
        # Check stats to ensure no duplication
        stats = self.registry_updater.core.registry_data["stats"]
        self.assertEqual(stats["total_packages"], 1)
        self.assertEqual(stats["total_versions"], 1)

        # Finally, test for the integrity of the registry
        is_valid, validation_results = self.registry_updater.validator.validate_registry()
        self.assertTrue(is_valid, "Registry after refusing duplicate package.")


class RegistryIntegrationTests(unittest.TestCase):
    """Integration tests for the registry functionality with real packages."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Use a temporary registry file for testing
        self.temp_dir = tempfile.mkdtemp()
        self.registry_path = Path(self.temp_dir) / "integration_registry.json"
                
        # Path to Hatching-Dev packages
        self.hatch_dev_path = Path(__file__).parent.parent.parent.parent / "Hatching-Dev"
        self.assertTrue(self.hatch_dev_path.exists(), 
                        f"Hatching-Dev directory not found at {self.hatch_dev_path}")
        
        # Initialize registry updater
        self.registry_updater = RegistryUpdater(self.registry_path)
        
        # Add a test repository
        self.repo_name = "hatching-dev"
        self.registry_updater.core.add_repository(self.repo_name, "file:///hatching-dev")
    
    def tearDown(self):
        """Clean up test environment after each test."""
        shutil.rmtree(self.temp_dir)
    
    def test_bulk_add_packages(self):
        """Test adding multiple packages to the registry."""
        # List of packages that should add successfully
        successful_packages = [
            "arithmetic_pkg",
            "base_pkg_1",
            "base_pkg_2",
            "python_dep_pkg",
            "simple_dep_pkg",
            "complex_dep_pkg"
        ]
        
        # Add each package
        for pkg_name in successful_packages:
            pkg_path = self.hatch_dev_path / pkg_name
            if not pkg_path.exists():
                logger.warning(f"Package not found: {pkg_path}")
                continue

            is_valid, validation_results = self.registry_updater.validate_and_add_package(self.repo_name, pkg_path)
            self.assertTrue(is_valid, f"Failed to add package: {pkg_name}.")
            
            # Verify package was added
            pkg = self.registry_updater.core.find_package(self.repo_name, pkg_name)
            self.assertIsNotNone(pkg, f"Package {pkg_name} should have been added to registry")

        # Finally, test for the integrity of the registry
        is_valid, validation_results = self.registry_updater.validator.validate_registry()
        self.assertTrue(is_valid, "Registry validation failed after adding packages")
    
    def test_failing_packages(self):
        """Test packages that should fail to add."""
        # First add some base packages for dependency resolution
        base_packages = [
            "simple_dep_pkg",
            "complex_dep_pkg"
        ]
        
        for pkg_name in base_packages:
            pkg_path = self.hatch_dev_path / pkg_name
            if not pkg_path.exists():
                logger.warning(f"Base package not found: {pkg_path}")
                continue
            
            logger.info(f"Adding base package: {pkg_name}")
            result, _ = self.registry_updater.validate_and_add_package(self.repo_name, pkg_path)
            
            # this should fail because all packages have something missing
            self.assertFalse(result, f"Package {pkg_name} should not have been added to registry")

        self.assertEqual(len(self.registry_updater.core.registry_data["repositories"][0]["packages"]), 0, "No packages should have been added to the registry")

        # Finally, test for the integrity of the registry
        is_valid, validation_results = self.registry_updater.validator.validate_registry()
        self.assertTrue(is_valid, "Registry validation failed after adding packages")   

if __name__ == '__main__':
    unittest.main()