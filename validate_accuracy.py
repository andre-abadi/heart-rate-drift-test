#!/usr/bin/env python3
"""
Validation script for heart rate drift calculator.
Runs against test files and compares against truth values in filenames.

Filename format: test[_skip_first_skip_last_truth_value].gpx
Examples:
  - test_15_15_2.16.gpx → skip_first=15, skip_last=15, truth=2.16%
  - test2_15_5_4.96.gpx → skip_first=15, skip_last=5, truth=4.96%
"""

import subprocess
import re
from pathlib import Path
from typing import List, Tuple, Optional
import sys


def get_python_executable() -> str:
    """Get the Python executable to use (from venv if available)."""
    venv_path = Path('.venv/Scripts/python.exe')
    if venv_path.exists():
        return str(venv_path)
    return sys.executable


def parse_filename(filename: str) -> Optional[Tuple[int, int, float]]:
    """
    Parse skip_first, skip_last, and truth_value from filename.
    
    Args:
        filename: GPX filename (e.g., test_15_15_2.16.gpx)
    
    Returns:
        Tuple of (skip_first, skip_last, truth_value) or None if format not recognized
    """
    # Match pattern: test[_digits_digits_decimal].gpx
    match = re.search(r'test\d*_(\d+)_(\d+)_([\d.]+)\.gpx', filename)
    if match:
        skip_first = int(match.group(1))
        skip_last = int(match.group(2))
        truth_value = float(match.group(3))
        return skip_first, skip_last, truth_value
    return None


def run_calculator(gpx_file: Path, skip_first: int, skip_last: int) -> Optional[float]:
    """
    Run the heart_rate_drift calculator and extract the percentage.
    
    Args:
        gpx_file: Path to GPX file
        skip_first: Warm-up duration in minutes
        skip_last: Cool-down duration in minutes
    
    Returns:
        Calculated decoupling percentage or None if error
    """
    try:
        python_exe = get_python_executable()
        result = subprocess.run(
            [
                python_exe,
                'heart_rate_drift.py',
                str(gpx_file),
                str(skip_first),
                str(skip_last)
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"  ❌ Error running calculator: {result.stderr}")
            return None
        
        # Extract percentage from output
        # Look for "Pa:HR: X.XX%" format
        match = re.search(r'Pa:HR:\s*([-\d.]+)%', result.stdout)
        if match:
            return float(match.group(1))
        else:
            print(f"  ❌ Could not parse percentage from output")
            return None
            
    except subprocess.TimeoutExpired:
        print(f"  ❌ Timeout")
        return None
    except Exception as e:
        print(f"  ❌ Exception: {e}")
        return None


def main():
    """Find and validate all test GPX files."""
    gpx_dir = Path('./test')
    test_files = sorted(gpx_dir.glob('test*.gpx'))
    
    if not test_files:
        print("No test GPX files found")
        return
    
    print(f"{'='*70}")
    print(f"Heart Rate Drift Accuracy Validation")
    print(f"{'='*70}\n")
    print(f"Python executable: {get_python_executable()}\n")
    
    results = []
    
    for gpx_file in test_files:
        parsed = parse_filename(gpx_file.name)
        
        if not parsed:
            print(f"⚠️  {gpx_file.name}: Filename format not recognized")
            continue
        
        skip_first, skip_last, truth_value = parsed
        
        print(f"{gpx_file.name}")
        print(f"  Parameters: skip_first={skip_first}, skip_last={skip_last}")
        print(f"  Truth value: {truth_value}%")
        
        # Run calculator
        calculated = run_calculator(gpx_file, skip_first, skip_last)
        
        if calculated is None:
            print(f"  ❌ Failed to calculate")
            continue
        
        # Calculate error
        error = abs(calculated - truth_value)
        error_pct = (error / truth_value) * 100
        
        # Determine pass/fail
        if error < 0.1:
            status = "✓ PASS"
        elif error < 0.2:
            status = "⚠ MARGINAL"
        else:
            status = "❌ FAIL"
        
        print(f"  Calculated: {calculated}%")
        print(f"  Error: {error:.4f}% ({error_pct:.2f}% relative)")
        print(f"  {status}\n")
        
        results.append({
            'file': gpx_file.name,
            'truth': truth_value,
            'calculated': calculated,
            'error': error,
            'error_pct': error_pct,
            'pass': status.startswith('✓')
        })
    
    # Summary
    if results:
        print(f"{'='*70}")
        print(f"Summary")
        print(f"{'='*70}")
        print(f"{'File':<30} {'Truth':<10} {'Calc':<10} {'Error':<10} {'Status':<10}")
        print(f"{'-'*70}")
        
        for r in results:
            status_sym = "✓" if r['pass'] else "❌"
            print(f"{r['file']:<30} {r['truth']:<10.2f} {r['calculated']:<10.2f} {r['error']:<10.4f} {status_sym}")
        
        passed = sum(1 for r in results if r['pass'])
        total = len(results)
        avg_error = sum(r['error'] for r in results) / len(results)
        
        print(f"{'-'*70}")
        print(f"Passed: {passed}/{total}")
        print(f"Average Error: {avg_error:.4f}%")
        print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
