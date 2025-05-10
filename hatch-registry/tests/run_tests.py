#!/usr/bin/env python3
import sys
import unittest
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("test_results.log")
    ]
)
logger = logging.getLogger("hatch.test_runner")

if __name__ == "__main__":
    # Discover and run all tests
    test_loader = unittest.TestLoader()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--unit-only":
        # Run only unit tests
        logger.info("Running unit tests only...")
        test_suite = test_loader.loadTestsFromName("test_registry_updater.RegistryUpdaterTests")
    elif len(sys.argv) > 1 and sys.argv[1] == "--integration-only":
        # Run only integration tests
        logger.info("Running integration tests only...")
        test_suite = test_loader.loadTestsFromName("test_registry_updater.RegistryTests")
    else:
        # Run all tests
        logger.info("Running all tests...")
        test_suite = test_loader.discover('.', pattern='test_*.py')
    
    # Run the tests
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    # Log test results summary
    logger.info(f"Tests run: {result.testsRun}")
    logger.info(f"Errors: {len(result.errors)}")
    logger.info(f"Failures: {len(result.failures)}")
    
    # Exit with appropriate status code
    sys.exit(not result.wasSuccessful())