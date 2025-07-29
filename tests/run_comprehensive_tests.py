#!/usr/bin/env python3
"""
Comprehensive test runner for IELTS bot quality assurance.
Runs all comprehensive tests including end-to-end, performance, and load tests.
"""

import subprocess
import sys
import time
from typing import List, Dict, Any


class TestRunner:
    """Comprehensive test runner with reporting."""
    
    def __init__(self):
        self.test_suites = {
            'end_to_end': {
                'name': 'End-to-End User Journeys',
                'file': 'tests/test_end_to_end_user_journeys.py',
                'description': 'Complete user journey simulations'
            },
            'performance': {
                'name': 'Performance & Concurrent Users',
                'file': 'tests/test_performance_concurrent_users.py',
                'description': 'Concurrent user handling and performance'
            },
            'openai_integration': {
                'name': 'OpenRouter API Integration',
                'file': 'tests/test_openai_integration_rate_limiting.py',
                'description': 'OpenRouter API integration with rate limiting'
            },
            'database_load': {
                'name': 'Database Load Testing',
                'file': 'tests/test_database_load_concurrent_access.py',
                'description': 'Database operations under concurrent load'
            },
            'existing_integration': {
                'name': 'Existing Integration Tests',
                'file': 'tests/test_evaluation_workflow_integration.py',
                'description': 'Existing evaluation workflow integration'
            }
        }
        
        self.results = {}
    
    def run_test_suite(self, suite_key: str, verbose: bool = True) -> Dict[str, Any]:
        """Run a specific test suite."""
        suite = self.test_suites[suite_key]
        
        print(f"\n{'='*60}")
        print(f"Running: {suite['name']}")
        print(f"Description: {suite['description']}")
        print(f"File: {suite['file']}")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        # Build pytest command
        cmd = ['python', '-m', 'pytest', suite['file']]
        if verbose:
            cmd.append('-v')
        cmd.extend(['--tb=short', '--no-header'])
        
        try:
            # Run the test
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Parse results
            output_lines = result.stdout.split('\n')
            summary_line = next((line for line in output_lines if 'passed' in line or 'failed' in line), '')
            
            test_result = {
                'suite': suite['name'],
                'file': suite['file'],
                'duration': duration,
                'return_code': result.returncode,
                'passed': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'summary': summary_line.strip()
            }
            
            # Print immediate results
            if test_result['passed']:
                print(f"✅ PASSED: {suite['name']} ({duration:.2f}s)")
                if summary_line:
                    print(f"   {summary_line}")
            else:
                print(f"❌ FAILED: {suite['name']} ({duration:.2f}s)")
                print(f"   Return code: {result.returncode}")
                if result.stderr:
                    print(f"   Error: {result.stderr[:200]}...")
            
            return test_result
            
        except subprocess.TimeoutExpired:
            print(f"⏰ TIMEOUT: {suite['name']} (exceeded 5 minutes)")
            return {
                'suite': suite['name'],
                'file': suite['file'],
                'duration': 300,
                'return_code': -1,
                'passed': False,
                'stdout': '',
                'stderr': 'Test timed out after 5 minutes',
                'summary': 'TIMEOUT'
            }
        
        except Exception as e:
            print(f"💥 ERROR: {suite['name']} - {str(e)}")
            return {
                'suite': suite['name'],
                'file': suite['file'],
                'duration': 0,
                'return_code': -1,
                'passed': False,
                'stdout': '',
                'stderr': str(e),
                'summary': 'ERROR'
            }
    
    def run_all_tests(self, verbose: bool = True) -> Dict[str, Any]:
        """Run all test suites."""
        print("🚀 Starting Comprehensive IELTS Bot Testing")
        print(f"Running {len(self.test_suites)} test suites...")
        
        overall_start = time.time()
        
        for suite_key in self.test_suites.keys():
            self.results[suite_key] = self.run_test_suite(suite_key, verbose)
        
        overall_end = time.time()
        overall_duration = overall_end - overall_start
        
        # Generate summary report
        self.print_summary_report(overall_duration)
        
        return self.results
    
    def run_specific_tests(self, suite_keys: List[str], verbose: bool = True) -> Dict[str, Any]:
        """Run specific test suites."""
        print(f"🎯 Running {len(suite_keys)} specific test suites...")
        
        overall_start = time.time()
        
        for suite_key in suite_keys:
            if suite_key in self.test_suites:
                self.results[suite_key] = self.run_test_suite(suite_key, verbose)
            else:
                print(f"⚠️  Unknown test suite: {suite_key}")
        
        overall_end = time.time()
        overall_duration = overall_end - overall_start
        
        self.print_summary_report(overall_duration)
        
        return self.results
    
    def print_summary_report(self, total_duration: float):
        """Print comprehensive summary report."""
        print(f"\n{'='*80}")
        print("📊 COMPREHENSIVE TEST SUMMARY REPORT")
        print(f"{'='*80}")
        
        passed_count = sum(1 for r in self.results.values() if r['passed'])
        failed_count = len(self.results) - passed_count
        
        print(f"Total Test Suites: {len(self.results)}")
        print(f"✅ Passed: {passed_count}")
        print(f"❌ Failed: {failed_count}")
        print(f"⏱️  Total Duration: {total_duration:.2f} seconds")
        print()
        
        # Detailed results
        for suite_key, result in self.results.items():
            status = "✅ PASS" if result['passed'] else "❌ FAIL"
            print(f"{status} | {result['suite']:<35} | {result['duration']:>6.2f}s | {result['summary']}")
        
        print(f"\n{'='*80}")
        
        # Performance insights
        if self.results:
            fastest = min(self.results.values(), key=lambda x: x['duration'])
            slowest = max(self.results.values(), key=lambda x: x['duration'])
            
            print("🏃 Performance Insights:")
            print(f"   Fastest: {fastest['suite']} ({fastest['duration']:.2f}s)")
            print(f"   Slowest: {slowest['suite']} ({slowest['duration']:.2f}s)")
        
        # Failure details
        failed_suites = [r for r in self.results.values() if not r['passed']]
        if failed_suites:
            print(f"\n💥 Failed Test Details:")
            for result in failed_suites:
                print(f"   {result['suite']}:")
                print(f"     Return Code: {result['return_code']}")
                if result['stderr']:
                    print(f"     Error: {result['stderr'][:100]}...")
        
        print(f"\n{'='*80}")
        
        # Overall status
        if failed_count == 0:
            print("🎉 ALL TESTS PASSED! The IELTS bot is ready for production.")
        else:
            print(f"⚠️  {failed_count} test suite(s) failed. Please review and fix issues.")
        
        print(f"{'='*80}\n")
    
    def print_available_suites(self):
        """Print available test suites."""
        print("📋 Available Test Suites:")
        print("-" * 50)
        for key, suite in self.test_suites.items():
            print(f"  {key:<20} | {suite['name']}")
            print(f"  {' '*20} | {suite['description']}")
            print()


def main():
    """Main entry point for test runner."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Comprehensive IELTS Bot Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tests/run_comprehensive_tests.py                    # Run all tests
  python tests/run_comprehensive_tests.py --list             # List available test suites
  python tests/run_comprehensive_tests.py --suites end_to_end performance  # Run specific suites
  python tests/run_comprehensive_tests.py --quiet            # Run with minimal output
        """
    )
    
    parser.add_argument(
        '--suites',
        nargs='+',
        help='Specific test suites to run (space-separated)'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List available test suites and exit'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Run tests with minimal output'
    )
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    if args.list:
        runner.print_available_suites()
        return
    
    verbose = not args.quiet
    
    try:
        if args.suites:
            results = runner.run_specific_tests(args.suites, verbose)
        else:
            results = runner.run_all_tests(verbose)
        
        # Exit with appropriate code
        failed_count = sum(1 for r in results.values() if not r['passed'])
        sys.exit(0 if failed_count == 0 else 1)
        
    except KeyboardInterrupt:
        print("\n⚠️  Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()