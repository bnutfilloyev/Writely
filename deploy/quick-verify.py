#!/usr/bin/env python3
"""
Quick deployment verification script for IELTS Telegram Bot.
This script performs basic checks to ensure the deployment is working.
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import requests
except ImportError:
    print("❌ requests module not found. Please install: pip install requests")
    sys.exit(1)


class DeploymentVerifier:
    """Quick deployment verification for IELTS Telegram Bot."""
    
    def __init__(self):
        self.app_name = "ielts-telegram-bot"
        self.health_url = "http://localhost:8000/health"
        self.api_url = "http://localhost:8000"
        self.app_dir = Path("/opt") / self.app_name if Path("/opt").exists() else Path.cwd()
        
        self.tests_passed = 0
        self.tests_failed = 0
        self.failed_tests = []
    
    def log(self, message: str, level: str = "INFO"):
        """Log a message with timestamp and level."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        colors = {
            "INFO": "\033[0;34m",    # Blue
            "SUCCESS": "\033[0;32m", # Green
            "WARNING": "\033[1;33m", # Yellow
            "ERROR": "\033[0;31m",   # Red
            "RESET": "\033[0m"       # Reset
        }
        
        color = colors.get(level, colors["INFO"])
        reset = colors["RESET"]
        
        print(f"{color}[{timestamp}] {level}: {message}{reset}")
    
    def run_test(self, test_name: str, test_func) -> bool:
        """Run a test and track results."""
        self.log(f"Running test: {test_name}")
        
        try:
            result = test_func()
            if result:
                self.log(f"✓ PASS: {test_name}", "SUCCESS")
                self.tests_passed += 1
                return True
            else:
                self.log(f"✗ FAIL: {test_name}", "ERROR")
                self.failed_tests.append(test_name)
                self.tests_failed += 1
                return False
        except Exception as e:
            self.log(f"✗ FAIL: {test_name} - {str(e)}", "ERROR")
            self.failed_tests.append(f"{test_name} ({str(e)})")
            self.tests_failed += 1
            return False
    
    def test_docker_available(self) -> bool:
        """Test if Docker is available and running."""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def test_app_directory(self) -> bool:
        """Test if application directory and files exist."""
        required_files = [
            "docker-compose.yml",
            "Dockerfile",
            ".env"
        ]
        
        if not self.app_dir.exists():
            return False
        
        for file_name in required_files:
            if not (self.app_dir / file_name).exists():
                return False
        
        return True
    
    def test_containers_running(self) -> bool:
        """Test if Docker containers are running."""
        try:
            os.chdir(self.app_dir)
            result = subprocess.run(
                ["docker-compose", "ps", "--services", "--filter", "status=running"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                running_services = result.stdout.strip().split('\n')
                return len([s for s in running_services if s.strip()]) > 0
            
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False
    
    def test_health_endpoint(self) -> bool:
        """Test if health endpoint is responding."""
        try:
            response = requests.get(self.health_url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                return "status" in data
            
            return False
        except (requests.RequestException, json.JSONDecodeError):
            return False
    
    def test_api_root(self) -> bool:
        """Test if API root endpoint is responding."""
        try:
            response = requests.get(self.api_url, timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def test_environment_variables(self) -> bool:
        """Test if required environment variables are set."""
        env_file = self.app_dir / ".env"
        
        if not env_file.exists():
            return False
        
        required_vars = [
            "TELEGRAM_BOT_TOKEN",
            "OPENAI_API_KEY",
            "DATABASE_URL"
        ]
        
        try:
            content = env_file.read_text()
            
            for var in required_vars:
                # Check if variable exists and is not empty
                if f"{var}=" not in content:
                    return False
                
                # Extract value and check it's not empty
                for line in content.split('\n'):
                    if line.startswith(f"{var}="):
                        value = line.split('=', 1)[1].strip()
                        if not value or value.startswith('your_') or value == 'placeholder':
                            return False
                        break
            
            return True
        except Exception:
            return False
    
    def test_database_file(self) -> bool:
        """Test if database file exists."""
        possible_paths = [
            self.app_dir / "data" / "ielts_bot.db",
            Path("/app/data/ielts_bot.db"),
            Path("./data/ielts_bot.db")
        ]
        
        return any(path.exists() for path in possible_paths)
    
    def test_log_directory(self) -> bool:
        """Test if log directory exists."""
        possible_paths = [
            self.app_dir / "logs",
            Path("/app/logs"),
            Path("./logs")
        ]
        
        return any(path.exists() and path.is_dir() for path in possible_paths)
    
    def get_health_info(self) -> Dict:
        """Get detailed health information."""
        try:
            response = requests.get(self.health_url, timeout=5)
            if response.status_code == 200:
                return response.json()
        except requests.RequestException:
            pass
        
        return {"status": "unknown", "error": "Health endpoint not accessible"}
    
    def get_container_status(self) -> List[str]:
        """Get container status information."""
        try:
            os.chdir(self.app_dir)
            result = subprocess.run(
                ["docker-compose", "ps"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return result.stdout.strip().split('\n')
            
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        
        return ["Container status unavailable"]
    
    def run_all_tests(self) -> bool:
        """Run all verification tests."""
        self.log("Starting IELTS Telegram Bot deployment verification", "INFO")
        
        # Core infrastructure tests
        self.run_test("Docker Available", self.test_docker_available)
        self.run_test("Application Directory", self.test_app_directory)
        self.run_test("Environment Variables", self.test_environment_variables)
        
        # Application tests
        self.run_test("Containers Running", self.test_containers_running)
        self.run_test("Health Endpoint", self.test_health_endpoint)
        self.run_test("API Root Endpoint", self.test_api_root)
        
        # Data persistence tests
        self.run_test("Database File", self.test_database_file)
        self.run_test("Log Directory", self.test_log_directory)
        
        return self.tests_failed == 0
    
    def print_summary(self):
        """Print verification summary."""
        total_tests = self.tests_passed + self.tests_failed
        
        self.log("Verification Summary", "INFO")
        self.log(f"Tests passed: {self.tests_passed}/{total_tests}", "INFO")
        
        if self.tests_failed == 0:
            self.log("🎉 All tests passed! Deployment is successful.", "SUCCESS")
            
            # Show additional info
            self.log("Application Information:", "INFO")
            self.log(f"- Health Check: {self.health_url}", "INFO")
            self.log(f"- API Endpoint: {self.api_url}", "INFO")
            self.log(f"- Application Directory: {self.app_dir}", "INFO")
            
            # Show health status
            health_info = self.get_health_info()
            self.log(f"- Health Status: {health_info.get('status', 'unknown')}", "INFO")
            
            # Show container status
            self.log("Container Status:", "INFO")
            for line in self.get_container_status()[:5]:  # Show first 5 lines
                if line.strip():
                    self.log(f"  {line}", "INFO")
            
            return True
        else:
            self.log(f"❌ {self.tests_failed} tests failed!", "ERROR")
            self.log("Failed tests:", "ERROR")
            for test in self.failed_tests:
                self.log(f"  - {test}", "ERROR")
            
            self.log("Please check the logs and fix the issues before proceeding.", "WARNING")
            return False


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Quick deployment verification for IELTS Telegram Bot"
    )
    parser.add_argument(
        "--app-dir",
        type=str,
        help="Application directory path (default: auto-detect)"
    )
    parser.add_argument(
        "--health-url",
        type=str,
        default="http://localhost:8000/health",
        help="Health check URL (default: http://localhost:8000/health)"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run only essential tests"
    )
    
    args = parser.parse_args()
    
    verifier = DeploymentVerifier()
    
    if args.app_dir:
        verifier.app_dir = Path(args.app_dir)
    
    if args.health_url:
        verifier.health_url = args.health_url
        verifier.api_url = args.health_url.replace("/health", "")
    
    if args.quick:
        # Run only essential tests
        verifier.log("Running quick verification (essential tests only)", "INFO")
        
        success = True
        success &= verifier.run_test("Containers Running", verifier.test_containers_running)
        success &= verifier.run_test("Health Endpoint", verifier.test_health_endpoint)
        success &= verifier.run_test("Environment Variables", verifier.test_environment_variables)
        
        if success:
            verifier.log("✓ Quick verification passed!", "SUCCESS")
        else:
            verifier.log("✗ Quick verification failed!", "ERROR")
            sys.exit(1)
    else:
        # Run all tests
        success = verifier.run_all_tests()
        verifier.print_summary()
        
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()