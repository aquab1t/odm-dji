# Contributing

## Adding a New Camera Model

The camera database lives in `odm_dji.py` at the top of the file (`CAMERA_DB`).
To add a new DJI model, append one entry:

```python
"FC####": {
    "name": "DJI Model Name",
    "rolling_shutter": True,
    "readout": <readout_ms>,   # rolling shutter readout time in milliseconds
    "k1": <k1>,               # Brown radial distortion coefficient
    "k2": <k2>,
},
```

### Finding the correct values

**EXIF model string** — use `exiftool -Model <photo.jpg>` on a photo from that drone.
The output must match the dict key exactly (e.g. `"FC3411"`).

**Readout time** — manufacturer spec or measured from calibration targets.
Typical consumer DJI range: 16–33 ms.

**k1 / k2** — Brown radial distortion coefficients.
Sources (in order of preference):
1. Manufacturer published calibration data
2. OpenDroneMap community calibration reports
3. Calibrate from a large, well-distributed photo set using ODM's self-calibration
   and read the optimized values from `opensfm/stats/stats.json` after a run

### Adding a unit test

Add a test in `tests/test_odm_dji.py` inside `TestGetCameraInfo`:

```python
def test_fc####_known_model(self):
    info = get_camera_info("FC####")
    self.assertEqual(info["name"], "DJI Model Name")
    self.assertEqual(info["readout"], <readout_ms>)
    self.assertAlmostEqual(info["k1"], <k1>, places=3)
```

Run tests with:

```bash
python3 -m pytest tests/ -v
```

All 29 existing tests must still pass.

## Reporting Issues

Please include:
- Drone model and EXIF `Model` field (`exiftool -Model photo.jpg`)
- Number of photos and approximate overlap
- ODM reprojection error (from `opensfm/stats/stats.json`)
- What you expected vs. what happened
