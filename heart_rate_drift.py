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


def _format_timedelta(td: timedelta) -> str:
    """Format a timedelta as H:MM:SS."""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours}:{minutes:02d}:{seconds:02d}"


def _get_drift_interpretation(decoupling_percent: float) -> dict:
    """
    Classify aerobic decoupling into an AeT band with label and visual marker position.

    Thresholds (Uphill Athlete method):
      <= 3.5%  → Below AeT
      3.5–5%   → Within AeT
      >= 5%    → Above AeT

    Marker percent maps the result onto a three-zone bar:
      Below zone  = first 12.5% of bar width  (0–3.5%)
      Within zone = middle 75% of bar width   (3.5–5.0%)
      Above zone  = last 12.5% of bar width   (5.0%+, clamped at 8%)
    """
    p = decoupling_percent

    if p <= 3.5:
        band = 'below'
        label = 'Below AeT - Recommend increasing Z2 Max by 5bpm'
        marker_percent = (p / 3.5) * 12.5
    elif p < 5.0:
        band = 'within'
        label = 'Within AeT - No Change Recommended'
        marker_percent = 12.5 + ((p - 3.5) / 1.5) * 75.0
    else:
        band = 'above'
        label = 'Above AeT - Recommend reducing Z2 Max by 5bpm'
        marker_percent = 87.5 + ((min(p, 8.0) - 5.0) / 3.0) * 12.5

    return {
        'band': band,
        'label': label,
        'marker_percent': round(min(100.0, max(0.0, marker_percent)), 1),
    }


class HeartRateDriftCalculator:
    """Calculates heart rate drift from a GPX file."""
    
    def __init__(self, gpx_file_path: Optional[str] = None, gpx_file_obj = None):
        """
        Initialize with a GPX file path or file object.
        
        Args:
            gpx_file_path: Path to the GPX file (for CLI usage)
            gpx_file_obj: File object or path-like (for web uploads, in-memory)
        """
        self.gpx_file_path = gpx_file_path
        self.gpx_file_obj = gpx_file_obj
        self.gpx = self._load_gpx()
        self.track_points = self._extract_track_points()
    
    def _load_gpx(self) -> gpxpy.gpx.GPX:
        """Load and parse the GPX file."""
        if self.gpx_file_obj is not None:
            # Load from file object (web upload)
            if hasattr(self.gpx_file_obj, 'read'):
                # File object (BytesIO or similar)
                content = self.gpx_file_obj.read()
                if isinstance(content, bytes):
                    content = content.decode('utf-8')
                return gpxpy.parse(content)
            else:
                # Path-like object
                with open(self.gpx_file_obj, 'r') as gpx_file:
                    return gpxpy.parse(gpx_file)
        else:
            # Load from file path (CLI)
            if self.gpx_file_path is None:
                raise ValueError("Either gpx_file_path or gpx_file_obj must be provided")
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
        
        # Collect HR and GPS data split by time with interpolation at midpoint
        first_segment_hrs = []
        first_segment_gps = []
        last_segment_hrs = []
        last_segment_gps = []
        
        prev_point = None  # Store previous point for interpolation
        
        for time, hr, lat, lon, elev in self.track_points:
            if hr is not None and lat is not None and lon is not None and after_warmup <= time <= before_cooldown:
                # Check if midpoint falls between previous and current point
                if prev_point is not None and prev_point[0] < active_mid_time < time:
                    # Interpolate at the midpoint
                    prev_time, prev_hr, prev_lat, prev_lon = prev_point
                    
                    # Calculate interpolation factor (0 to 1)
                    time_span = (time - prev_time).total_seconds()
                    time_to_mid = (active_mid_time - prev_time).total_seconds()
                    t = time_to_mid / time_span  # Ranges from 0 to 1
                    
                    # Linear interpolate HR
                    interpolated_hr = prev_hr + (hr - prev_hr) * t
                    
                    # Linear interpolate lat/lon
                    interpolated_lat = prev_lat + (lat - prev_lat) * t
                    interpolated_lon = prev_lon + (lon - prev_lon) * t
                    
                    # Add interpolated point to first segment
                    first_segment_hrs.append(interpolated_hr)
                    first_segment_gps.append((interpolated_lat, interpolated_lon))
                    
                    # Add current point to second segment (not interpolated, as it's past midpoint)
                    last_segment_hrs.append(hr)
                    last_segment_gps.append((lat, lon))
                elif time <= active_mid_time:
                    # Before midpoint - add to first segment
                    first_segment_hrs.append(hr)
                    first_segment_gps.append((lat, lon))
                else:
                    # After midpoint - add to second segment
                    last_segment_hrs.append(hr)
                    last_segment_gps.append((lat, lon))
                
                # Store current point for next iteration
                prev_point = (time, hr, lat, lon)
        
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
            'first_ef': first_ef,
            'last_distance_km': round(last_metrics['distance_km'], 2),
            'last_avg_hr': round(last_metrics['avg_hr'], 2),
            'last_ef': last_ef,
            'decoupling_bpm': first_ef - last_ef,
            'decoupling_percent': ((first_ef - last_ef) / first_ef) * 100 if first_ef > 0 else 0,
            'first_segment_samples': len(first_segment_hrs),
            'last_segment_samples': len(last_segment_hrs),
        }


def format_results_for_web(gpx_file: Optional[str] = None, gpx_file_obj = None, skip_first: int = 15, skip_last: int = 15, verbose: bool = False) -> dict:
    """
    Calculate drift and return results in web-friendly format.
    
    Args:
        gpx_file: Path to the GPX file (for CLI usage)
        gpx_file_obj: File object (for web uploads, in-memory)
        skip_first: Minutes to skip at start (warm-up)
        skip_last: Minutes to skip at end (cool-down)
        verbose: Include detailed segment information
    
    Returns:
        Dictionary with results (JSON-serializable)
    """
    try:
        calculator = HeartRateDriftCalculator(gpx_file_path=gpx_file, gpx_file_obj=gpx_file_obj)
        results = calculator.calculate_drift(skip_first, skip_last)
        
        tp_equivalent = results['decoupling_percent'] + 0.05
        decoupling_percent = round(results['decoupling_percent'], 2)

        total_td = results['total_duration']
        analyzed_td = total_td - timedelta(minutes=skip_first + skip_last)

        output = {
            'status': 'success',
            'data': {
                'total_duration': _format_timedelta(total_td),
                'analyzed_duration': _format_timedelta(analyzed_td),
                'skip_first_mins': skip_first,
                'skip_last_mins': skip_last,
                'decoupling_percent': decoupling_percent,
                'tp_equivalent': round(tp_equivalent, 2),
                'interpretation': _get_drift_interpretation(decoupling_percent),
            }
        }

        if verbose:
            hr_change = results['last_avg_hr'] - results['first_avg_hr']
            output['data'].update({
                'first_distance_km': results['first_distance_km'],
                'first_avg_hr': results['first_avg_hr'],
                'first_ef': round(results['first_ef'], 4),
                'first_ef_m_per_bpm': round(results['first_ef'] * 1000, 2),
                'first_segment_samples': results['first_segment_samples'],
                'last_distance_km': results['last_distance_km'],
                'last_avg_hr': results['last_avg_hr'],
                'last_ef': round(results['last_ef'], 4),
                'last_ef_m_per_bpm': round(results['last_ef'] * 1000, 2),
                'last_segment_samples': results['last_segment_samples'],
                'hr_change': round(hr_change, 2),
                'ef_change': round(results['decoupling_bpm'], 6),
                'ef_change_m_per_bpm': round(results['decoupling_bpm'] * 1000, 2),
            })
        
        return output
        
    except FileNotFoundError:
        file_ref = gpx_file if gpx_file else 'uploaded GPX file'
        return {'status': 'error', 'message': f'GPX file not found: {file_ref}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python heart_rate_drift.py <gpx_file_path> [skip_warm_up_mins] [skip_cool_down_mins] [--verbose]")
        sys.exit(1)
    
    gpx_file = sys.argv[1]
    skip_first = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    skip_last = int(sys.argv[3]) if len(sys.argv) > 3 else 15
    verbose = "--verbose" in sys.argv
    
    try:
        calculator = HeartRateDriftCalculator(gpx_file)
        results = calculator.calculate_drift(skip_first, skip_last)

        decoupling_percent = round(results['decoupling_percent'], 2)
        tp_equivalent = round(decoupling_percent + 0.05, 2)
        interpretation = _get_drift_interpretation(decoupling_percent)

        total_td = results['total_duration']
        analyzed_td = total_td - timedelta(minutes=skip_first + skip_last)

        print(f"\n{'='*60}")
        print(f"Aerobic Decoupling Analysis (Running)")
        print(f"{'='*60}")
        print(f"Total Workout Duration : {_format_timedelta(total_td)}")
        print(f"Analysed Duration      : {_format_timedelta(analyzed_td)}")
        print(f"\nConfiguration:")
        print(f"  Skip first {skip_first} mins (warm-up)")
        print(f"  Skip last {skip_last} mins (cool-down)")

        if verbose:
            hr_change = results['last_avg_hr'] - results['first_avg_hr']
            hr_sign = '+' if hr_change >= 0 else ''

            print(f"\nFirst Half (after warm-up):")
            print(f"  Distance        : {results['first_distance_km']} km")
            print(f"  Average HR      : {results['first_avg_hr']} bpm  ({results['first_segment_samples']} samples)")
            print(f"  Efficiency (EF) : {results['first_ef'] * 1000:.2f} m/bpm")

            print(f"\nSecond Half (before cool-down):")
            print(f"  Distance        : {results['last_distance_km']} km")
            print(f"  Average HR      : {results['last_avg_hr']} bpm  ({results['last_segment_samples']} samples)")
            print(f"  Efficiency (EF) : {results['last_ef'] * 1000:.2f} m/bpm")

            print(f"\nDelta (2nd half vs 1st half):")
            print(f"  HR Change       : {hr_sign}{hr_change:.2f} bpm")
            print(f"  EF Change       : {results['decoupling_bpm'] * 1000:.2f} m/bpm")

        print(f"\nResults:")
        print(f"  Pa:HR: {decoupling_percent:.2f}% [TP: {tp_equivalent:.2f}%]")
        print(f"  {interpretation['label']}")
        print(f"{'='*60}\n")
        
    except FileNotFoundError:
        print(f"Error: GPX file not found: {gpx_file}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
