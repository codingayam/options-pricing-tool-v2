#!/usr/bin/env python3
"""
Startup script for Options Pricing Comparison Tool
"""
import sys
import os
import subprocess
import argparse
import logging
from datetime import datetime

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = [
        'fastapi', 'uvicorn', 'yfinance', 'numpy', 'scipy', 
        'pandas', 'pydantic', 'jinja2'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("Missing required packages:")
        for package in missing_packages:
            print(f"  - {package}")
        print(f"\nInstall with: pip install {' '.join(missing_packages)}")
        return False
    
    return True

def setup_logging():
    """Set up logging to both file and console"""
    # Create timestamped log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"options_analysis_{timestamp}.log"
    
    # Configure logging to both file and console
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s:%(name)s:%(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"=== OPTIONS PRICING TOOL STARTED ===")
    logger.info(f"Log file: {log_filename}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 50)
    
    return log_filename

def start_web_server(port=8000, host="localhost"):
    """Start the web server"""
    # Set up logging first
    log_filename = setup_logging()
    
    print(f"Starting Options Pricing Tool web server...")
    print(f"URL: http://{host}:{port}")
    print(f"Logs will be saved to: {log_filename}")
    print("Press Ctrl+C to stop")
    
    try:
        import uvicorn
        from options_pricing_tool.main import app
        
        uvicorn.run(app, host=host, port=port, log_level="info")
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Error starting server: {e}")
        return False
    
    return True

def run_cli_example():
    """Run CLI example"""
    print("Running CLI example with AAPL call options...")
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "options_pricing_tool.cli",
            "AAPL", "call", "--validate-only"
        ], capture_output=True, text=True, cwd=os.path.dirname(__file__))
        
        if result.returncode == 0:
            print("✓ CLI validation successful")
            print(result.stdout)
        else:
            print("✗ CLI validation failed")
            print(result.stderr)
    
    except Exception as e:
        print(f"Error running CLI: {e}")

def run_tests():
    """Run the test suite"""
    print("Running test suite...")
    
    try:
        result = subprocess.run([
            sys.executable, "test_options_tool.py"
        ], cwd=os.path.dirname(__file__))
        
        return result.returncode == 0
    
    except Exception as e:
        print(f"Error running tests: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Options Pricing Comparison Tool")
    parser.add_argument(
        "command",
        choices=["web", "test", "cli-example", "check"],
        help="Command to run"
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port for web server (default: 8000)"
    )
    parser.add_argument(
        "--host", default="localhost",
        help="Host for web server (default: localhost)"
    )
    
    args = parser.parse_args()
    
    print("Options Pricing Comparison Tool")
    print("=" * 50)
    
    # Always check dependencies first
    if not check_dependencies():
        sys.exit(1)
    
    if args.command == "check":
        print("✓ All dependencies are installed")
        print("\nAvailable commands:")
        print("  web         - Start web server")
        print("  test        - Run test suite") 
        print("  cli-example - Run CLI example")
    
    elif args.command == "web":
        start_web_server(args.port, args.host)
    
    elif args.command == "test":
        success = run_tests()
        sys.exit(0 if success else 1)
    
    elif args.command == "cli-example":
        run_cli_example()

if __name__ == "__main__":
    main()