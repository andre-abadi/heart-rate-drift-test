# Aerobic Decoupling Calculator

Calculate **aerobic decoupling** (aerobic efficiency drift) from Garmin GPX files for running workouts.

Aerobic decoupling measures how your aerobic efficiency degrades over the course of a run, indicating aerobic fatigue and fitness level. This implementation follows the methodology used by TrainingPeaks, analyzing efficiency changes between the first and second half of your active workout time.

## What is Aerobic Decoupling?

Aerobic decoupling is the change in aerobic efficiency (power/heart rate ratio for running: distance/heart rate ratio) between the first and second halves of a workout.

**Formula:**
- **Efficiency Factor (EF)** = Distance / Average Heart Rate
- **Aerobic Decoupling %** = (EF_first_half - EF_second_half) / EF_first_half × 100

**Interpretation:**
- **Low decoupling (0-3%)**: Below aerobic threshold.
- **Moderate (3-5%)**: At aerobic threshold.
- **High (>5%)**: Above aerobic threshold.

## Algorithm

1. **Load GPX file** and extract GPS points with heart rate data from Garmin extensions
2. **Remove warm-up** (first N minutes, default 15) and **cool-down** (last N minutes, default 15)
3. **Calculate active duration** and find the midpoint by time (not sample count)
4. **Interpolate at midpoint** linearly between the two closest data points when midpoint falls between samples
5. **Split segments** into first half (before midpoint) and second half (after midpoint)
6. **Calculate EF for each half:**
   - Sum total distance using haversine formula (2D latitude/longitude)
   - Average heart rate across all samples
   - EF = total_distance / avg_hr
7. **Compute decoupling percentage** = (EF_first - EF_last) / EF_first × 100

### Technical Details

**Distance Calculation:**
- Uses **haversine formula** on WGS-84 spheroid (Earth radius = 6371 km)
- 2D calculation based on latitude/longitude only (no 3D distance)

**Heart Rate Averaging:**
- Simple arithmetic mean of all HR values in the segment
- All valid HR readings included (no filtering or smoothing)

**Time Interpolation:**
- Linear interpolation when the exact midpoint timestamp falls between data points
- Ensures precise temporal splitting regardless of GPS sample rate

## Files

### `heart_rate_drift.py`
Main calculator implementation. Contains the `HeartRateDriftCalculator` class with all logic for:
- Loading and parsing Garmin GPX files
- Extracting HR data from nested extensions
- Calculating haversine distances
- Performing time-based segment splitting with interpolation
- Computing efficiency factors and decoupling

**Key Methods:**
- `calculate_drift(skip_first_mins, skip_last_mins)` - Main entry point; returns decoupling stats

### `validate_accuracy.py`
Testing harness for accuracy validation. Auto-detects test files by filename pattern and compares calculated results against known truth values.

**Filename pattern:** `test[_skip_first_skip_last_truth_value].gpx`
- Example: `test_15_15_2.16.gpx` = test with 15 min skip each end, expected result 2.16%

**Output:** Comparison table showing file, truth value, calculated value, error %, and pass/fail

## Usage

### CLI

```bash
python heart_rate_drift.py <gpx_file> [skip_warmup_mins] [skip_cooldown_mins]
```

**Example:**
```bash
python heart_rate_drift.py my_run.gpx 15 15
```

**Output:**
```
============================================================
Aerobic Decoupling Analysis (Running)
============================================================
Total Duration: 1:15:30
Skip: 15min warm-up, 15min cool-down

First Half:
  Distance: 6.42 km
  Avg HR: 145 bpm (780 samples)
  EF: 0.0443 km/bpm

Second Half:
  Distance: 6.38 km
  Avg HR: 152 bpm (775 samples)
  EF: 0.0420 km/bpm

Aerobic Decoupling: 5.19%
============================================================
```

## Accuracy

This section is a report of evaluations conducted on two GPX files, which are, for privacy reasons not included with this repository, but served as the sources of truth, having been analysed in TrainingPeaks.

**Current performance against TrainingPeaks:**
- GPX 1 (2.16% expected): 2.11% calculated = **0.05% error**
- GPX 2 (4.96% expected): 4.90% calculated = **0.06% error**

## Debugging: What We Tried (and Why It Didn't Help)

The initial implementation achieved consistent 0.05% error against TrainingPeaks across different test GPX files done by different subjects using different equipment. That is, the number was always 0.05% **less** than the TrainingPeaks number We explored several optimization approaches to close this final gap:

### ❌ 3D Distance with Elevation
**Tried:** Including elevation delta in distance calculation using 3D haversine
- **Result:** Test 1 improved to 0.01% error, but Test 2 worsened to 0.15% error
- **Conclusion:** Elevation data from Garmin is noisy and terrain-specific. 2D haversine performs better on average.

### ❌ Heart Rate Outlier Removal (IQR Method)
**Tried:** Filtered HR values using Interquartile Range (IQR = 1.5 × (Q3 - Q1)) to remove extreme readings
- **Result:** Accuracy became significantly worse
- **Conclusion:** Garmin HR data is clean. No filtering needed. The bias isn't coming from outliers.

### ❌ HR Data Smoothing
**Tried:** Gaussian/moving average smoothing of heart rate values
- **Result:** No meaningful improvement, added complexity
- **Conclusion:** Simple mean is the best approach. Smoothing introduces artificial data.

### ❌ Pause Detection & Time Exclusion
**Tried:** Automatically detect pauses (low GPS speed) and exclude from calculations
- **Result:** Unnecessary complexity for typical continuous runs
- **Conclusion:** Removed. Users can manually specify skip times if needed.

### ✓ Time-Based Splitting with Linear Interpolation
**What worked:** Splitting by timestamp (not sample count) with linear interpolation at midpoint crossing
- This was critical for matching TrainingPeaks more closely
- Ensures precise temporal division regardless of GPS sample rate

### Conclusion: The 0.05% Bias

After exhaustive testing, the remaining 0.05% systematic bias is likely due to TrainingPeaks implementation specifics that we can't replicate exactly


