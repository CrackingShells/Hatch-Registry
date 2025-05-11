#!/usr/bin/env python3
import sys
import os
import argparse
import logging
from pathlib import Path

from .registry_updater import RegistryUpdater, RegistryUpdateError

def main():
    """Main entry point for registry CLI."""
    # Create the parser
    parser = argparse.ArgumentParser(description='Hatch Registry Updater')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Add repository command
    add_repo_parser = subparsers.add_parser('add-repository', help='Add a new repository')
    add_repo_parser.add_argument('--name', required=True, help='Repository name')
    add_repo_parser.add_argument('--url', required=True, help='Repository URL')
    add_repo_parser.add_argument('--registry', required=True, help='Path to registry file')
    
    # Add package command
    add_pkg_parser = subparsers.add_parser('add-package', help='Add a new package')
    add_pkg_parser.add_argument('--repository', required=True, help='Repository name')
    add_pkg_parser.add_argument('--package-dir', required=True, help='Path to package directory')
    add_pkg_parser.add_argument('--metadata-path', default='hatch_metadata.json', help='Relative path to metadata file')
    add_pkg_parser.add_argument('--registry', required=True, help='Path to registry file')
    
    # Update package command
    update_pkg_parser = subparsers.add_parser('update-package', help='Update an existing package')
    update_pkg_parser.add_argument('--repository', required=True, help='Repository name')
    update_pkg_parser.add_argument('--package-name', required=True, help='Package name')
    update_pkg_parser.add_argument('--package-dir', required=True, help='Path to package directory')
    update_pkg_parser.add_argument('--metadata-path', default='hatch_metadata.json', help='Relative path to metadata file')
    update_pkg_parser.add_argument('--registry', required=True, help='Path to registry file')
    
    # List repositories command
    list_repos_parser = subparsers.add_parser('list-repositories', help='List all repositories')
    list_repos_parser.add_argument('--registry', required=True, help='Path to registry file')
    
    # List packages command
    list_pkgs_parser = subparsers.add_parser('list-packages', help='List packages in a repository')
    list_pkgs_parser.add_argument('--repository', required=True, help='Repository name')
    list_pkgs_parser.add_argument('--registry', required=True, help='Path to registry file')
    
    # Show package command
    show_pkg_parser = subparsers.add_parser('show-package', help='Show package details')
    show_pkg_parser.add_argument('--repository', required=True, help='Repository name')
    show_pkg_parser.add_argument('--package-name', required=True, help='Package name')
    show_pkg_parser.add_argument('--registry', required=True, help='Path to registry file')
    
    # Validate package command
    validate_pkg_parser = subparsers.add_parser('validate-package', help='Validate a package')
    validate_pkg_parser.add_argument('--package-dir', required=True, help='Path to package directory')
    validate_pkg_parser.add_argument('--registry', required=True, help='Path to registry file')
    
    # Common args
    parser.add_argument('--log-level', 
                      choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                      default='INFO', 
                      help='Set the logging level')
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Process commands
    try:
        registry_path = Path(args.registry)
        updater = RegistryUpdater(registry_path)
        
        if args.command == 'add-repository':
            success = updater.add_repository(args.name, args.url)
            sys.exit(0 if success else 1)
            
        elif args.command == 'add-package':
            success = updater.add_package(args.repository, Path(args.package_dir), args.metadata_path)
            sys.exit(0 if success else 1)
            
        elif args.command == 'update-package':
            success = updater.update_package_registry(
                args.repository,
                args.package_name,
                Path(args.package_dir),
                Path(args.metadata_path)
            )
            sys.exit(0 if success else 1)
            
        elif args.command == 'list-repositories':
            repositories = updater.registry_data.get("repositories", [])
            print(f"Repositories ({len(repositories)}):")
            for repo in repositories:
                print(f"  - {repo['name']}: {repo['url']}")
                print(f"    Packages: {len(repo.get('packages', []))}")
                print(f"    Last indexed: {repo.get('last_indexed', 'Never')}")
            sys.exit(0)
            
        elif args.command == 'list-packages':
            repo = updater.find_repository(args.repository)
            if not repo:
                print(f"Repository not found: {args.repository}")
                sys.exit(1)
                
            packages = repo.get("packages", [])
            print(f"Packages in {args.repository} ({len(packages)}):")
            for pkg in packages:
                print(f"  - {pkg['name']} ({pkg.get('latest_version', 'No version')})")
                print(f"    Description: {pkg.get('description', 'No description')}")
                print(f"    Versions: {len(pkg.get('versions', []))}")
            sys.exit(0)
            
        elif args.command == 'show-package':
            pkg = updater.find_package(args.repository, args.package_name)
            if not pkg:
                print(f"Package not found: {args.package_name} in repository {args.repository}")
                sys.exit(1)
                
            print(f"Package: {pkg['name']}")
            print(f"Description: {pkg.get('description', 'No description')}")
            print(f"Category: {pkg.get('category', 'Uncategorized')}")
            print(f"Tags: {', '.join(pkg.get('tags', []))}")
            print(f"Latest version: {pkg.get('latest_version', 'No version')}")
            print(f"Versions ({len(pkg.get('versions', []))}):")
            for version in pkg.get('versions', []):
                print(f"  - {version.get('version', 'Unknown')}")
                print(f"    Added: {version.get('added_date', 'Unknown')}")
                print(f"    Path: {version.get('path', 'Unknown')}")
                print(f"    Artifacts: {len(version.get('artifacts', []))}")
            sys.exit(0)
            
        elif args.command == 'validate-package':
            is_valid, results = updater.validator.validate_package(Path(args.package_dir))
            if is_valid:
                print(f"Package validation successful: {args.package_dir}")
                sys.exit(0)
            else:
                print(f"Package validation failed: {args.package_dir}")
                if "errors" in results:
                    print("Errors:")
                    for error in results["errors"]:
                        print(f"  - {error}")
                if "dependency_errors" in results:
                    print("Dependency Errors:")
                    for error in results["dependency_errors"]:
                        print(f"  - {error}")
                sys.exit(1)
    
    except Exception as e:
        logging.error(f"Command failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
