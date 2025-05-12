import sys
import argparse
import logging
from pathlib import Path

from .registry_updater import RegistryUpdater

def main():
    """Main entry point for registry CLI."""
    # Create the parser
    parser = argparse.ArgumentParser(description='Hatch Registry Updater')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Add repository command
    add_repo_parser = subparsers.add_parser('add-repository', help='Add a new repository')
    add_repo_parser.add_argument('--name', required=True, help='Repository name')
    add_repo_parser.add_argument('--url', required=True, help='Repository URL')
    
    # Add package command
    add_pkg_parser = subparsers.add_parser('add-package', help='Performs validation and add a new package')
    add_pkg_parser.add_argument('--repository-name', required=True, help='Repository name')
    add_pkg_parser.add_argument('--package-dir', required=True, help='Path to package directory')
    
    # List repositories command
    list_repos_parser = subparsers.add_parser('list-repositories', help='List all repositories')
    
    # List packages command
    list_pkgs_parser = subparsers.add_parser('list-packages', help='List packages in a repository')
    list_pkgs_parser.add_argument('--repository-name', required=True, help='Repository name')
    
    # Show package command
    show_pkg_parser = subparsers.add_parser('show-package', help='Show package details')
    show_pkg_parser.add_argument('--repository-name', required=True, help='Repository name')
    show_pkg_parser.add_argument('--package-name', required=True, help='Package name')
    
    # Validate package command
    validate_pkg_parser = subparsers.add_parser('validate-package', help='Validate whether a package can be added to the registry.')
    validate_pkg_parser.add_argument('--repository-name', required=True, help='Repository name')
    validate_pkg_parser.add_argument('--package-dir', required=True, help='Path to package directory')
    
    # Common args
    parser.add_argument('--registry',
                        default="./data/hatch_packages_registry.json",
                        help='Path to registry file. Default (./data/hatch_packages_registry.json) is relative to "/Hatch-Registry"')
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
            success = updater.core.add_repository(args.name, args.url)
            sys.exit(0 if success else 1)
            
        elif args.command == 'add-package':
            success = updater.validate_and_add_package(args.repository_name, Path(args.package_dir))
            if not success:
                print(f"Failed to add package to repository {args.repository_name}")
                sys.exit(1)
            sys.exit(0)
            
        elif args.command == 'list-repositories':
            repositories = updater.core.registry_data.get("repositories", [])
            print(f"Repositories ({len(repositories)}):")
            for repo in repositories:
                print(f"  - {repo['name']}: {repo['url']}")
                print(f"    Packages: {len(repo.get('packages', []))}")
                print(f"    Last indexed: {repo.get('last_indexed', 'Never')}")
            sys.exit(0)
            
        elif args.command == 'list-packages':
            repo = updater.core.find_repository(args.repository_name)
            if not repo:
                print(f"Repository not found: {args.repository_name}")
                sys.exit(1)
                
            packages = repo.get("packages", [])
            print(f"Packages in {args.repository_name} ({len(packages)}):")
            for pkg in packages:
                print(f"  - {pkg['name']} ({pkg.get('latest_version', 'No version')})")
                print(f"    Description: {pkg.get('description', 'No description')}")
                print(f"    Versions: {len(pkg.get('versions', []))}")
            sys.exit(0)
            
        elif args.command == 'show-package':
            pkg = updater.core.find_package(args.repository_name, args.package_name)
            if not pkg:
                print(f"Package not found: {args.package_name} in repository {args.repository_name}")
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
            sys.exit(0)
            
        elif args.command == 'validate-package':
            is_valid, results = updater.validate_package(args.repository_name, Path(args.package_dir))
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
