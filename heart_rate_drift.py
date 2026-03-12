"""
Heart Rate Drift Calculator for Running
Calculates Aerobic Decoupling (aerobic efficiency drift) from a GPX file.
Aerobic Decoupling = (EF_second_half - EF_first_half) / EF_first_half × 100%
Where EF (Efficiency Factor) = Distance / Heart Rate
"""

import gpxpy
import gpxpy.gpx
from datetime import timedelta
from typing import List, Tuple, Optional
import math


class HeartRateDriftCalculator:
    """Calculates heart rate drift from a GPX file."""
    
    def __init__(self, gpx_file_path: str, smooth: bool = True, smoothing_factor: float = 0.3, skip_pauses: bool = True, pause_threshold_seconds: int = 30):
        """
        Initialize with a GPX file path.
        
        Args:
            gpx_file_path: Path to the GPX file
            smooth: Whether to apply exponential moving average smoothing
            smoothing_factor: EMA smoothing factor (0-1, higher = more responsive to new values)
            skip_pauses: Whether to skip paused segments (gaps > pause_threshold_seconds)
            pause_threshold_seconds: Time gap threshold to detect pauses (seconds)
        """
        self.gpx_file_path = gpx_file_path
        self.smooth = smooth
        self.smoothing_factor = smoothing_factor
        self.skip_pauses = skip_pauses
        self.pause_threshold_seconds = pause_threshold_seconds
        self.gpx = self._load_gpx()
        self.track_points = self._extract_track_points()
        self.pause_info = None  # Will store pause detection info for debugging
    
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
        
        if self.skip_pauses:
            points = self._remove_pauses(points)
        
        if self.smooth:
            points = self._apply_smoothing(points)
        
        return points
    
    def _remove_pauses(self, points: List[Tuple]) -> List[Tuple]:
        """
        Remove paused segments (gaps > pause_threshold_seconds) from track points.
        
        Pauses are detected by checking time gaps between consecutive points.
        All points within a pause window are removed.
        
        Args:
            points: List of track points
            
        Returns:
            Track points with paused segments removed
        """
        if not points:
            return points
        
        filtered_points = [points[0]]  # Always keep first point
        pause_count = 0
        pause_duration = timedelta()
        
        for i in range(1, len(points)):
            curr_time = points[i][0]
            prev_time = points[i - 1][0]
            
            if curr_time is None or prev_time is None:
                filtered_points.append(points[i])
                continue
            
            time_gap = curr_time - prev_time
            
            if time_gap.total_seconds() > self.pause_threshold_seconds:
                # Pause detected - skip this point
                pause_count += 1
                pause_duration += time_gap
            else:
                # Active segment - keep this point
                filtered_points.append(points[i])
        
        self.pause_info = {
            'pause_count': pause_count,
            'pause_duration': pause_duration,
            'original_points': len(points),
            'filtered_points': len(filtered_points)
        }
        
        return filtered_points
    
    def _apply_smoothing(self, points: List[Tuple]) -> List[Tuple]:
        """
        Apply exponential moving average (EMA) smoothing to HR data.
        
        Args:
            points: List of track points
            
        Returns:
            Smoothed track points
        """
        smoothed_points = []
        ema_hr = None
        
        for time, hr, lat, lon, elev in points:
            if hr is not None:
                if ema_hr is None:
                    ema_hr = float(hr)
                else:
                    ema_hr = (hr * self.smoothing_factor) + (ema_hr * (1 - self.smoothing_factor))
                smoothed_hr = ema_hr
            else:
                smoothed_hr = None
            
            smoothed_points.append((time, smoothed_hr, lat, lon, elev))
        
        return smoothed_points
    
    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance in kilometers between two GPS points using haversine formula.
        
        Args:
            lat1, lon1: First point latitude/longitude
            lat2, lon2: Second point latitude/longitude
            
        Returns:
            Distance in kilometers
        """
        R = 6371  # Earth radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def _calculate_segment_metrics(self, segment_hrs: List[float], segment_points: List[Tuple]) -> dict:
        """
        Calculate distance and efficiency factor for a segment.
        
        Args:
            segment_hrs: List of HR values for the segment
            segment_points: List of (lat, lon) points for the segment
            
        Returns:
            Dictionary with distance (km) and efficiency factor
        """
        # Calculate total distance
        total_distance = 0.0
        for i in range(1, len(segment_points)):
            lat1, lon1 = segment_points[i - 1]
            lat2, lon2 = segment_points[i]
            total_distance += self._haversine_distance(lat1, lon1, lat2, lon2)
        
        # Calculate average HR
        avg_hr = sum(segment_hrs) / len(segment_hrs) if segment_hrs else 0
        
        # Calculate efficiency factor (distance / avg_hr)
        # EF typically expressed in km/bpm or miles/bpm
        ef = total_distance / avg_hr if avg_hr > 0 else 0
        
        return {
            'distance_km': total_distance,
            'avg_hr': avg_hr,
            'efficiency_factor': ef,
            'sample_count': len(segment_hrs)
        }
    
    def calculate_drift(self, skip_first_mins: int = 15, skip_last_mins: int = 15) -> dict:
        """
        Calculate Aerobic Decoupling (EF drift) for running.
        
        Removes warm-up (first N minutes) and cool-down (last N minutes),
        then splits by time and compares Efficiency Factor (EF) between halves.
        
        EF = Distance / Average Heart Rate
        Aerobic Decoupling = (EF_second - EF_first) / EF_first × 100%
        
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
        
        # Collect HR and GPS data split by time
        first_segment_hrs = []
        first_segment_gps = []
        last_segment_hrs = []
        last_segment_gps = []
        
        for time, hr, lat, lon, elev in self.track_points:
            if hr is not None and lat is not None and lon is not None and after_warmup <= time <= before_cooldown:
                if time <= active_mid_time:
                    first_segment_hrs.append(hr)
                    first_segment_gps.append((lat, lon))
                else:
                    last_segment_hrs.append(hr)
                    last_segment_gps.append((lat, lon))
        
        if not first_segment_hrs or not first_segment_gps:
            raise ValueError(f"No heart rate/GPS data in first half (after {skip_first_mins}min warm-up)")
        if not last_segment_hrs or not last_segment_gps:
            raise ValueError(f"No heart rate/GPS data in second half (before {skip_last_mins}min cool-down)")
        
        # Calculate metrics for each segment
        first_metrics = self._calculate_segment_metrics(first_segment_hrs, first_segment_gps)
        last_metrics = self._calculate_segment_metrics(last_segment_hrs, last_segment_gps)
        
        first_ef = first_metrics['efficiency_factor']
        last_ef = last_metrics['efficiency_factor']
        
        # Calculate aerobic decoupling
        # Positive value = efficiency decreased (HR increased or distance decreased)
        # Negative value = efficiency improved (HR decreased or distance increased)
        decoupling_bpm = first_ef - last_ef
        decoupling_percent = (decoupling_bpm / first_ef) * 100 if first_ef > 0 else 0
        
        return {
            'total_duration': total_duration,
            'skip_first_mins': skip_first_mins,
            'skip_last_mins': skip_last_mins,
            'first_distance_km': round(first_metrics['distance_km'], 2),
            'first_avg_hr': round(first_metrics['avg_hr'], 2),
            'first_ef': round(first_ef, 4),
            'last_distance_km': round(last_metrics['distance_km'], 2),
            'last_avg_hr': round(last_metrics['avg_hr'], 2),
            'last_ef': round(last_ef, 4),
            'decoupling_bpm': round(decoupling_bpm, 4),
            'decoupling_percent': round(decoupling_percent, 2),
            'first_segment_samples': len(first_segment_hrs),
            'last_segment_samples': len(last_segment_hrs),
        }


def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python heart_rate_drift.py <gpx_file_path> [skip_warm_up_mins] [skip_cool_down_mins] [--no-smooth]")
        print("\nExample: python heart_rate_drift.py workout.gpx 15 15")
        print("\nOptions:")
        print("  --no-smooth  : Disable smoothing (default: smoothing enabled)")
        print("\nCalculates Aerobic Decoupling (Aerobic Efficiency drift) for RUNNING:")
        print("  1. Removing the first N minutes (warm-up)")
        print("  2. Removing the last N minutes (cool-down)")
        print("  3. Splitting remaining active time in half (by time, not samples)")
        print("  4. Calculating Efficiency Factor (EF) = Distance / Avg HR for each half")
        print("  5. Computing Aerobic Decoupling = (EF_second - EF_first) / EF_first × 100%")
        sys.exit(1)
    
    gpx_file = sys.argv[1]
    skip_first = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    skip_last = int(sys.argv[3]) if len(sys.argv) > 3 else 15
    smooth = "--no-smooth" not in sys.argv
    
    try:
        calculator = HeartRateDriftCalculator(gpx_file, smooth=smooth)
        results = calculator.calculate_drift(skip_first, skip_last)
        
        print(f"\n{'='*60}")
        print(f"Aerobic Decoupling Analysis (Running)")
        print(f"{'='*60}")
        print(f"Total Workout Duration: {results['total_duration']}")
        print(f"\nConfiguration:")
        print(f"  Skip first {skip_first} mins (warm-up)")
        print(f"  Skip last {skip_last} mins (cool-down)")
        print(f"  Smoothing: {'Enabled' if smooth else 'Disabled'}")
        
        print(f"\n{'First Half (after warm-up):':40}")
        print(f"  Distance: {results['first_distance_km']} km")
        print(f"  Average HR: {results['first_avg_hr']} bpm ({results['first_segment_samples']} samples)")
        print(f"  Efficiency Factor: {results['first_ef']} km/bpm")
        
        print(f"\n{'Second Half (before cool-down):':40}")
        print(f"  Distance: {results['last_distance_km']} km")
        print(f"  Average HR: {results['last_avg_hr']} bpm ({results['last_segment_samples']} samples)")
        print(f"  Efficiency Factor: {results['last_ef']} km/bpm")
        
        print(f"\n{'Aerobic Decoupling:':40}")
        print(f"  EF Change: {results['decoupling_bpm']:.4f} km/bpm")
        print(f"  Percentage: {results['decoupling_percent']}%")
        print(f"{'='*60}\n")
        
    except FileNotFoundError:
        print(f"Error: GPX file not found: {gpx_file}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
