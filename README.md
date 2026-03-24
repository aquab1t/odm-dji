# odm-dji

Interactive Python 3 script that processes DJI drone photos through
[OpenDroneMap](https://opendronemap.org/), automatically injecting the correct
lens calibration and rolling shutter correction for each camera model.

Without correction, ODM initializes all DJI cameras with zero distortion
coefficients and no rolling shutter compensation — causing visible geometric
distortion in orthophotos and DSMs. This tool fixes that.

**Measured improvement on DJI Phantom 3 (FC330), ultra quality:**

| Setup | Reprojection error |
|-------|-------------------|
| No correction (ODM default) | 1.321 px |
| Rolling shutter + lens calibration | **0.731 px** |

---

## Requirements

| Tool | Install |
|------|---------|
| Python 3.8+ | Pre-installed on Ubuntu |
| `exiftool` | `sudo apt install libimage-exiftool-perl` |
| Docker | [docs.docker.com/engine/install](https://docs.docker.com/engine/install/) |
| `opendronemap/odm:fixed` | See [Build the Docker image](#build-the-docker-image) |

### Build the Docker image

The `:fixed` tag patches a `gdal_array` incompatibility in ODM v3.5.6 that
prevents PDF report generation:

```bash
docker build -t opendronemap/odm:fixed \
  -f docker/Dockerfile.fix \
  docker/
```

This only needs to be done once. The build takes a few minutes.

---

## Usage

### Batch Runner (non‑interactive)

```bash
python3 run_batch_odm.py \
    --photos-dir /media/jose/Fury/example2/ \
    --output-dir /media/jose/Fury/output2/ \
    --quality low \
    --no-chm
```

Runs the same processing pipeline as `odm_dji.py` but without any prompts. Use `--quality` to choose `low|medium|high|ultra`. Add `--no-chm` to skip canopy‑height‑model generation.

### PALMAS Batch Runner

```bash
python3 run_palmas_batch_odm.py \
    --input-dir /media/jose/Fury/palmas/ \
    --output-dir /media/jose/Fury/output_palmas/ \
    --quality low \
    --skip-ndvi \
    [--force]  # optional: overwrite existing output folders
```

Runs ODM on each PALMAS granule, aligns multispectral bands and (optionally) creates an NDVI orthophoto. Use `--skip-ndvi` to bypass NDVI generation.




```bash
python3 odm_dji.py
```

The script prompts you step by step:

```
=== ODM DJI Drone Processor ===

Photos folder: /path/to/your/photos
  → Scanning EXIF...
  → Detected: DJI Mini 4 Pro (FC3411) — 120 photos  [known]
  → Camera:   rolling_shutter=True, k1=-0.110, k2=0.018
  → Is this correct? [Y/n]:

Project name [MyFlight_20240101]:
Output folder [/path/to/MyFlight_20240101]:

Quality:
  1) low      — 10 cm/px,  ~5 min
  2) medium   — 5 cm/px,   ~15 min
  3) high     — 3 cm/px,   ~30 min
  4) ultra    — 2 cm/px,   ~60 min
Choose [1-4]:

Generate CHM (DSM − DTM)? [y/N]:

=== Summary ===
  Photos:           120 × FC3411
  Output:           /path/to/MyFlight_20240101
  Quality:          ultra (2 cm/px,  ~60 min)
  Rolling shutter:  yes (readout: 28 ms)
  Lens calibration: pre-loaded (k1=-0.110, k2=0.018)

Run ODM? [Y/n]:
```

---

## Supported Cameras

Camera model is auto-detected from EXIF. Known models receive pre-loaded lens
calibration (Brown radial distortion k1/k2) and the correct rolling shutter
readout time, used as an initial estimate that ODM then refines.

| EXIF Model | Drone | k1 | k2 | Readout |
|------------|-------|----|----|---------|
| FC330 | DJI Phantom 3 | −0.270 | 0.090 | 16 ms |
| FC6310 | DJI Phantom 4 Pro | −0.098 | 0.010 | 29 ms |
| FC220 | DJI Mavic Pro | −0.154 | 0.025 | 32 ms |
| FC7203 | DJI Mini 2 | −0.143 | 0.028 | 33 ms |
| FC3582 | DJI Mini 3 Pro | −0.120 | 0.021 | 30 ms |
| FC3411 | DJI Mini 4 Pro | −0.110 | 0.018 | 28 ms |
| FC3170 | DJI Air 2S | −0.095 | 0.015 | 25 ms |
| FC2103 | DJI Mavic Air 2 | −0.131 | 0.022 | 30 ms |
| FC8282 | DJI Neo | −0.158 | 0.030 | 30 ms |
| FC2105 | DJI Mavic 3 Multispectral | −0.105 | 0.020 | 28 ms |

Unknown cameras fall back to rolling shutter only (k1=k2=0, readout=30 ms),
which is always safer than ODM's default of no rolling shutter correction at all.

See [CONTRIBUTING.md](CONTRIBUTING.md) to add a new model.

---

## Outputs

After a successful run, the output folder contains:

```
<project_name>/
├── images/                       # Relative symlinks to source photos
├── cameras.json                  # Lens calibration passed to ODM
├── odm_orthophoto/
│   └── odm_orthophoto.tif        # Georeferenced orthophoto (GeoTIFF)
├── odm_dem/
│   ├── dsm.tif                   # Digital Surface Model
│   ├── dtm.tif                   # Digital Terrain Model
│   └── chm.tif                   # Canopy Height Model (if requested)
└── odm_report/
    └── report.pdf                # Processing report with quality metrics
```

---

## How It Works

**1. Lens calibration injection**

ODM accepts an initial `cameras.json` via `--cameras`. The script writes the
known Brown distortion coefficients (k1, k2) for each DJI model and lets ODM
self-calibrate from that starting point rather than from zero. The cameras.json
key uses ODM's internal floor-truncation format for the focal length
(e.g. `"v2 dji fc330 4000 3000 brown 0.5555"`), which is critical — a key
mismatch silently falls back to ODM's default uncalibrated state.

**2. Rolling shutter correction**

All consumer DJI cameras use CMOS sensors that expose line-by-line rather than
all at once. At flight speed this creates a "jello" distortion. The script
passes `--rolling-shutter --rolling-shutter-readout <N>` with the correct
readout time for each model.

**3. Relative symlinks**

ODM requires images to be inside the project folder, but copying 36+ raw photos
wastes space. The script creates relative symlinks from `<project>/images/` to
the source folder, which resolve correctly inside the Docker container.

---

## Running Tests

```bash
python3 -m pytest tests/ -v
```

29 unit tests cover all pure functions: camera lookup, focal computation,
cameras.json key generation, ODM command building, and quality presets.

---

## License

MIT — see [LICENSE](LICENSE).
