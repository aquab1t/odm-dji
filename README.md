# odm-dji

Python 3 scripts for processing DJI drone imagery with
[OpenDroneMap](https://opendronemap.org/), including multispectral processing
and vegetation index calculation.

## Features

- **Lens calibration injection** - Auto-detects DJI camera model from EXIF and injects correct distortion coefficients
- **Rolling shutter correction** - Applies model-specific readout times
- **Multispectral processing** - Process DJI Mavic 3M and other multispectral drones
- **Vegetation indices** - Calculate NDVI, NDRE, GNDVI, SAVI, EVI, and more
- **3D visualization** - Generate interactive 3D HTML maps and animations
- **Publication plots** - Create print-ready maps with scale bars and north arrows

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

### Python Dependencies

```bash
pip install numpy rasterio matplotlib scipy plotly
```

### Build the Docker image

The `:fixed` tag patches a `gdal_array` incompatibility in ODM v3.5.6 that
prevents PDF report generation:

```bash
docker build -t opendronemap/odm:fixed \
  -f docker/Dockerfile.fix \
  docker/
```

---

## Usage

### Publication Plots

Generate publication-quality maps from ODM outputs:

```bash
python3 publication_plots.py \
  --dem /path/to/dsm.tif \
  --rgb /path/to/ortho.tif \
  --output /path/to/plots/ \
  --indices /path/to/indices/ \
  --offset 0 \
  --title "Your Site Name"
```

Options:
- `--dem` - Path to DEM/DSM GeoTIFF
- `--rgb` - Path to RGB orthophoto GeoTIFF
- `--output` - Output directory for plots
- `--indices` - Directory containing vegetation index GeoTIFFs (optional)
- `--offset` - Elevation offset in meters (default: 0)
- `--title` - Title for plots (optional)

Outputs: `dem_contours.png`, `rgb_orthophoto.png`, `3d_perspective.png`, `ndvi.png`, `ndre.png`, `gndvi.png`, `ndwi.png`

### 3D Interactive Visualization

Create an interactive 3D HTML map with RGB texture:

```bash
python3 dem_3d_rgb_mesh.py \
  --dem /path/to/dsm.tif \
  --rgb /path/to/ortho.tif \
  --output /path/to/3d_map.html \
  --downsample 4 \
  --exaggeration 1.0
```

Options:
- `--dem` - Path to DEM/DSM GeoTIFF
- `--rgb` - Path to RGB orthophoto GeoTIFF
- `--output` - Output HTML file path
- `--downsample` - Downsample factor (default: 4, lower = higher quality)
- `--exaggeration` - Vertical exaggeration (default: 1.0 = no exaggeration)

### Vegetation Indices

Calculate vegetation indices from multispectral bands:

```python
from vegetation_indices import calculate_all_indices, save_index_geotiff

bands = {
    'red': red_array,
    'green': green_array,
    'nir': nir_array,
    'rededge': rededge_array
}

indices = calculate_all_indices(bands)
# Returns: ndvi, ndre, gndvi, savi, ndwi, evi, evi2, mcari, ndvire, ccci
```

---

## Supported Cameras

Camera model is auto-detected from EXIF. Known models receive pre-loaded lens
calibration (Brown radial distortion k1/k2) and the correct rolling shutter
readout time.

| EXIF Model | Drone | k1 | k2 | Readout |
|------------|-------|----|----|---------|
| FC330 | DJI Phantom 3 | -0.270 | 0.090 | 16 ms |
| FC6310 | DJI Phantom 4 Pro | -0.098 | 0.010 | 29 ms |
| FC220 | DJI Mavic Pro | -0.154 | 0.025 | 32 ms |
| FC7203 | DJI Mini 2 | -0.143 | 0.028 | 33 ms |
| FC3582 | DJI Mini 3 Pro | -0.120 | 0.021 | 30 ms |
| FC3411 | DJI Mini 4 Pro | -0.110 | 0.018 | 28 ms |
| FC3170 | DJI Air 2S | -0.095 | 0.015 | 25 ms |
| FC2103 | DJI Mavic Air 2 | -0.131 | 0.022 | 30 ms |
| FC8282 | DJI Neo | -0.158 | 0.030 | 30 ms |
| FC2105 | DJI Mavic 3 Multispectral | -0.105 | 0.020 | 28 ms |

Unknown cameras fall back to rolling shutter only (k1=k2=0, readout=30 ms),
which is always safer than ODM's default of no rolling shutter correction at all.

See [CONTRIBUTING.md](CONTRIBUTING.md) to add a new model.

---

## Vegetation Indices

The following indices are calculated from multispectral bands:

| Index | Name | Bands Used |
|-------|------|------------|
| NDVI | Normalized Difference Vegetation Index | NIR, Red |
| NDRE | Normalized Difference Red Edge | NIR, RedEdge |
| GNDVI | Green NDVI | NIR, Green |
| SAVI | Soil Adjusted Vegetation Index | NIR, Red |
| NDWI | Normalized Difference Water Index | Green, NIR |
| EVI | Enhanced Vegetation Index | NIR, Red |
| EVI2 | Two-band EVI | NIR, Red |
| MCARI | Modified Chlorophyll Absorption Index | RedEdge, Red, Green |
| NDVIre | Red Edge NDVI | NIR, RedEdge |
| CCCI | Canopy Chlorophyll Content Index | NDRE, NDVI |

---

## Outputs

After processing, typical output structure:

```
<project_name>/
├── odm_orthophoto/
│   └── odm_orthophoto.tif    # Georeferenced orthophoto
├── odm_dem/
│   ├── dsm.tif               # Digital Surface Model
│   └── dtm.tif               # Digital Terrain Model
├── indices/                   # Vegetation indices (if processed)
│   ├── ndvi.tif
│   ├── ndre.tif
│   └── ...
└── plots/                     # Publication plots (if generated)
    ├── dem_contours.png
    ├── rgb_orthophoto.png
    └── ...
```

---

## How It Works

**1. Lens calibration injection**

ODM accepts an initial `cameras.json` via `--cameras`. The scripts write the
known Brown distortion coefficients (k1, k2) for each DJI model and let ODM
self-calibrate from that starting point rather than from zero.

**2. Rolling shutter correction**

All consumer DJI cameras use CMOS sensors that expose line-by-line rather than
all at once. At flight speed this creates a "jello" distortion. The scripts
pass `--rolling-shutter --rolling-shutter-readout <N>` with the correct
readout time for each model.

**3. Multispectral processing**

For multispectral drones like the DJI Mavic 3M, the pipeline extracts individual
bands (Red, Green, NIR, RedEdge) from the multispectral orthophoto and calculates
vegetation indices for analysis.

---

## License

MIT - see [LICENSE](LICENSE).
