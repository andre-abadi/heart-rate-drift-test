# Heart Rate Drift Analyser

<img src="templates/logo.png" alt="Heart Rate Drift Analyser logo" width="180">

Calculate heart rate drift from GPX files for running workouts.

This project uses an efficiency-factor approach rather than a heart-rate-only shortcut:

- Efficiency Factor (EF) = distance / average heart rate
- Heart Rate Drift % = (EF_first_half - EF_second_half) / EF_first_half x 100

That makes it useful for aerobic-threshold tests where you hold heart rate steady and let pace vary. A heart-rate-only comparison can miss drift in that scenario; EF-based drift captures the loss of output at the same cardiac cost.

## Features

- CLI analysis for a single GPX file
- Flask web UI for uploading and analysing GPX files
- Time-based midpoint split with linear interpolation at the half-way timestamp
- Detailed first-half / second-half / delta metrics
- TrainingPeaks-style Pa:HR output with a small displayed TP equivalent offset
- In-memory upload processing only; no file persistence required
- Stateless Docker packaging using an LSIO base image and s6-overlay

## How It Works

1. Load a GPX file and extract GPS points plus heart rate values from Garmin extensions.
2. Skip the configured warm-up and cool-down durations.
3. Split the remaining analysed duration in half by timestamp, not by sample count.
4. Interpolate a midpoint sample if the half-way time falls between two data points.
5. Compute segment metrics for each half:
   - distance
   - average heart rate
   - efficiency factor
6. Calculate drift percentage from the change in efficiency factor.

## Interpretation

The current backend interpretation bands are:

- `0.0%` to `3.5%`: Below AeT
- `>3.5%` to `<5.0%`: Within AeT
- `>=5.0%`: Above AeT

The web UI renders this on a visual scale and the backend returns the interpretation label and marker position in the API response.

## Project Files

- [heart_rate_drift.py](heart_rate_drift.py): Core parser, calculations, CLI entry point, and web response formatting
- [webapp.py](webapp.py): Flask app with `/`, `/analyze`, and `/health`
- [templates/index.html](templates/index.html): Single-page UI
- [validate_accuracy.py](validate_accuracy.py): Validation harness against GPX files in `test/`
- [docker/Dockerfile](docker/Dockerfile): Stateless LSIO-based container image

## Requirements

- Python 3.10+
- `flask`
- `gpxpy`
- `gunicorn` for the container image

## Local CLI Usage

Basic usage:

```bash
python heart_rate_drift.py <gpx_file_path> [skip_warm_up_mins] [skip_cool_down_mins] [--verbose]
```

Example:

```bash
python heart_rate_drift.py test/test_15_15_2.16.gpx 15 15 --verbose
```

Example output:

```text
============================================================
Heart Rate Drift Analyser
============================================================
Total Workout Duration : 1:40:18
Analysed Duration      : 1:10:18

Configuration:
  Skip first 15 mins (warm-up)
  Skip last 15 mins (cool-down)

First Half (after warm-up):
  Distance        : 5.41 km
  Average HR      : 154.22 bpm  (2078 samples)
  Efficiency (EF) : 35.08 m/bpm

Second Half (before cool-down):
  Distance        : 5.29 km
  Average HR      : 154.07 bpm  (2078 samples)
  Efficiency (EF) : 34.34 m/bpm

Delta (2nd half vs 1st half):
  HR Change       : -0.15 bpm
  EF Change       : -0.74 m/bpm

Results:
  Pa:HR: 2.11% [TP: 2.16%]
  Below AeT - Recommend increasing Z2 Max by 5bpm
============================================================
```

## Local Web Usage

Run the Flask app:

```bash
python webapp.py
```

Then open:

```text
http://127.0.0.1:5000
```

API endpoints:

- `GET /` - web UI
- `POST /analyze` - analyse an uploaded GPX file
- `GET /health` - health check

The web app processes uploads entirely in memory and does not save GPX files to disk.

## Validation

Run the validation harness:

```bash
python validate_accuracy.py
```

It discovers GPX files in `test/` using the naming convention:

```text
test[_skip_first_skip_last_truth_value].gpx
```

Examples:

- `test_15_15_2.16.gpx`
- `test2_15_5_4.96.gpx`

Current verified accuracy is approximately `0.05%` absolute error versus the stored truth values in the sample test files.

## Docker

The container image is:

- based on `lscr.io/linuxserver/baseimage-alpine:3.21`
- stateless
- running under s6-overlay
- configured to run the app as the LSIO `abc` user
- publishable to GitHub Container Registry via [docker-publish.yml](.github/workflows/docker-publish.yml)

Build from the repository root:

```bash
docker build -f docker/Dockerfile -t heart-rate-drift .
```

Run:

```bash
docker run -e PUID=1000 -e PGID=1000 -p 5000:5000 heart-rate-drift
```

Notes:

- No volume mappings are required.
- `PUID` and `PGID` are optional for this stateless app but still allow the container to avoid running as root.
- The Docker packaging files live under `docker/` and are copied into the image from there.

### GitHub Container Registry

The repository includes a GitHub Actions workflow at [docker-publish.yml](.github/workflows/docker-publish.yml) that builds from [docker/Dockerfile](docker/Dockerfile) and publishes the image to GitHub Container Registry (`ghcr.io`).

The workflow:

- builds on pull requests to validate the Dockerfile
- publishes on pushes to `main`
- publishes on pushes to `master`
- publishes version tags such as `v1.0.0`
- can also be run manually with `workflow_dispatch`

Published image names follow this pattern:

```text
ghcr.io/<owner>/<repo>
```

Typical tags include:

- branch tags such as `main`
- version tags such as `v1.0.0`
- `latest` on the default branch

After the workflow has published an image, you can pull and run it with:

```bash
docker pull ghcr.io/<owner>/<repo>:latest
docker run -e PUID=1000 -e PGID=1000 -p 5000:5000 ghcr.io/<owner>/<repo>:latest
```

## Accuracy Notes

The implementation is designed to match TrainingPeaks-style behaviour closely, using:

- time-based splitting instead of sample-count splitting
- midpoint interpolation
- 2D haversine distance
- no pause detection
- no HR smoothing

Those choices were kept because they produced the most consistent results across the included validation files.

Across the validation GPX files we tested, the calculated result was consistently `0.05%` lower than the corresponding TrainingPeaks result, regardless of the file itself. Because that difference remained constant rather than varying unpredictably by workout, we believe that our implementation is mathematically sound and that the remaining gap is due to a small TrainingPeaks-specific reporting or implementation offset rather than a flaw in the underlying calculation.

For that reason, the app reports both:

- the raw calculated `Pa:HR` result from this implementation
- a `TP equivalent` value with the `+0.05%` offset applied as an alternative comparison value


