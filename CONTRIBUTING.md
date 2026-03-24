# Contributing

## Adding a New Camera Model

To add a new DJI model, submit a pull request with:

1. Updated camera table in README.md
2. Calibration data source (manufacturer spec, community report, or self-calibration)

### Finding the correct values

**EXIF model string** - use `exiftool -Model <photo.jpg>` on a photo from that drone.
The output must match exactly (e.g. `"FC3411"`).

**Readout time** - manufacturer spec or measured from calibration targets.
Typical consumer DJI range: 16-33 ms.

**k1 / k2** - Brown radial distortion coefficients.
Sources (in order of preference):
1. Manufacturer published calibration data
2. OpenDroneMap community calibration reports
3. Calibrate from a large, well-distributed photo set using ODM's self-calibration
   and read the optimized values from `opensfm/stats/stats.json` after a run

### Example camera entry

```
| FC#### | DJI Model Name | k1_value | k2_value | readout_ms |
```

## Reporting Issues

Please include:
- Drone model and EXIF `Model` field (`exiftool -Model photo.jpg`)
- Number of photos and approximate overlap
- ODM reprojection error (from `opensfm/stats/stats.json`)
- What you expected vs. what happened

## Pull Requests

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Ensure scripts run without errors
5. Submit a pull request with a clear description

## Code Style

- Use clear variable names
- Add docstrings to functions
- Keep functions focused and modular
- Avoid hard-coded paths - use command-line arguments
