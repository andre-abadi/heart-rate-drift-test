"""
Heart Rate Drift Calculator
Calculates heart rate drift by comparing average HR from first 15 mins vs last 15 mins of a workout.
"""

import gpxpy
import gpxpy.gpx
from datetime import timedelta
from typing import List, Tuple, Optional


class HeartRateDriftCalculator:
    """Calculates heart rate drift from a GPX file."""
    
    def __init__(self, gpx_file_path: str):
        """
        Initialize with a GPX file path.
        
        Args:
            gpx_file_path: Path to the GPX file
        """
        self.gpx_file_path = gpx_file_path
        self.gpx = self._load_gpx()
        self.track_points = self._extract_track_points()
    
    def _load_gpx(self) -> gpxpy.gpx.GPX:
        """Load and parse the GPX file."""
        with open(self.gpx_file_path, 'r') as gpx_file:
            return gpxpy.parse(gpx_file)
    
    def _extract_track_points(self) -> List[Tuple]:
        """
        Extract track points with timestamps and heart rate data.
        
        Returns:
            List of tuples: (datetime, heart_rate, latitude, longitude, elevation)
        """
        points = []
        for track in self.gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    # Heart rate is typically in extensions
                    hr = None
                    if point.extensions:
                        # Garmin GPX files store HR in ns3:TrackPointExtension/ns3:hr
                        for ext in point.extensions:
                            # Check if this is TrackPointExtension
                            if 'TrackPointExtension' in ext.tag:
                                # Look through children for hr element
                                for child in ext:
                                    if 'hr' in child.tag.lower():
                                        try:
                                            hr = int(child.text)
                                        except (ValueError, TypeError):
                                            pass
                                        break
                                break
                    
                    points.append((point.time, hr, point.latitude, point.longitude, point.elevation))
        
        return points
    
    def calculate_drift(self, skip_first_mins: int = 15, skip_last_mins: int = 15) -> dict:
        """
        Calculate heart rate drift (PA:HR style).
        
        Removes warm-up (first N minutes) and cool-down (last N minutes),
        then splits the remaining active period in half and compares drift.
        
        Args:
            skip_first_mins: Duration to skip at start as warm-up (minutes)
            skip_last_mins: Duration to skip at end as cool-down (minutes)
        
        Returns:
            Dictionary with drift statistics
        """
        if not self.track_points:
            raise ValueError("No track points found in GPX file")
        
        if len(self.track_points) < 2:
            raise ValueError("Not enough track points to calculate drift")
        
        # Get time range
        start_time = self.track_points[0][0]
        end_time = self.track_points[-1][0]
        
        if start_time is None or end_time is None:
            raise ValueError("Track points must have timestamp data")
        
        total_duration = end_time - start_time
        
        # Skip warm-up and cool-down
        after_warmup = start_time + timedelta(minutes=skip_first_mins)
        before_cooldown = end_time - timedelta(minutes=skip_last_mins)
        
        # Calculate active period duration
        active_duration = before_cooldown - after_warmup
        active_mid_time = after_warmup + (active_duration / 2)
        
        # Collect HR data split by time (not sample count)
        first_segment_hrs = []
        last_segment_hrs = []
        
        for time, hr, lat, lon, elev in self.track_points:
            if hr is not None and after_warmup <= time <= before_cooldown:
                if time <= active_mid_time:
                    first_segment_hrs.append(hr)
                else:
                    last_segment_hrs.append(hr)
        
        if not first_segment_hrs:
            raise ValueError(f"No heart rate data in first half (after {skip_first_mins}min warm-up)")
        if not last_segment_hrs:
            raise ValueError(f"No heart rate data in second half (before {skip_last_mins}min cool-down)")
        
        # Calculate averages
        first_avg_hr = sum(first_segment_hrs) / len(first_segment_hrs)
        last_avg_hr = sum(last_segment_hrs) / len(last_segment_hrs)
        
        # Calculate drift
        drift_bpm = last_avg_hr - first_avg_hr
        drift_percent = (drift_bpm / first_avg_hr) * 100 if first_avg_hr > 0 else 0
        
        return {
            'total_duration': total_duration,
            'skip_first_mins': skip_first_mins,
            'skip_last_mins': skip_last_mins,
            'first_avg_hr': round(first_avg_hr, 2),
            'last_avg_hr': round(last_avg_hr, 2),
            'drift_bpm': round(drift_bpm, 2),
            'drift_percent': round(drift_percent, 2),
            'first_segment_samples': len(first_segment_hrs),
            'last_segment_samples': len(last_segment_hrs),
        }


def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python heart_rate_drift.py <gpx_file_path> [skip_warm_up_mins] [skip_cool_down_mins]")
        print("\nExample: python heart_rate_drift.py workout.gpx 15 15")
        print("\nCalculates PA:HR drift by:")
        print("  1. Removing the first N minutes (warm-up)")
        print("  2. Removing the last N minutes (cool-down)")
        print("  3. Splitting remaining active time in half")
        print("  4. Comparing early half HR vs late half HR")
        sys.exit(1)
    
    gpx_file = sys.argv[1]
    skip_first = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    skip_last = int(sys.argv[3]) if len(sys.argv) > 3 else 15
    
    try:
        calculator = HeartRateDriftCalculator(gpx_file)
        results = calculator.calculate_drift(skip_first, skip_last)
        
        print(f"\n{'='*50}")
        print(f"Heart Rate Drift Analysis (PA:HR)")
        print(f"{'='*50}")
        print(f"Total Workout Duration: {results['total_duration']}")
        print(f"\nConfiguration:")
        print(f"  Skip first {skip_first} mins (warm-up)")
        print(f"  Skip last {skip_last} mins (cool-down)")
        print(f"\nEarly half (after warm-up):")
        print(f"  Average HR: {results['first_avg_hr']} bpm ({results['first_segment_samples']} samples)")
        print(f"\nLate half (before cool-down):")
        print(f"  Average HR: {results['last_avg_hr']} bpm ({results['last_segment_samples']} samples)")
        print(f"\nPA:HR Drift:")
        print(f"  Absolute: {results['drift_bpm']} bpm")
        print(f"  Percentage: {results['drift_percent']}%")
        print(f"{'='*50}\n")
        
    except FileNotFoundError:
        print(f"Error: GPX file not found: {gpx_file}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
