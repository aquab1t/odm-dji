#!/usr/bin/env python3
"""
mangrove_pipeline.py - Unified processing pipeline for mangrove site.

This pipeline:
1. Uses RGB DEM as authoritative elevation model (no gaps, no spikes)
2. Extracts MS bands from existing aligned orthophoto
3. Calculates all vegetation indices
4. Generates publication quality DEM map
5. Creates 3D visualizations

Usage:
    python3 mangrove_pipeline.py --input /path/to/images --output /path/to/output
"""

import argparse
import sys
import os
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import reproject, Resampling

sys.path.insert(0, str(Path(__file__).parent))

from vegetation_indices import calculate_all_indices, save_index_geotiff


class MangrovePipeline:
    """Unified processing pipeline for mangrove multispectral data."""

    def __init__(self, input_dir: Path, output_dir: Path):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.rgb_ortho = self.output_dir / "rgb_ortho"
        self.ms_bands = self.output_dir / "ms_bands"
        self.bands_aligned_dir = self.output_dir / "bands_aligned"
        self.indices_dir = self.output_dir / "indices"

    def verify_rgb_products(self) -> bool:
        """Verify RGB products exist and are valid."""
        required = [
            self.rgb_ortho / "odm_dem" / "dsm.tif",
            self.rgb_ortho / "odm_dem" / "dtm.tif",
            self.rgb_ortho / "odm_orthophoto" / "odm_orthophoto.tif",
        ]

        for path in required:
            if not path.exists():
                print(f"ERROR: Missing required file: {path}")
                return False

        print("RGB products verified:")
        for path in required:
            with rasterio.open(path) as src:
                print(f"  {path.name}: {src.width}x{src.height}, {src.count} band(s)")

        return True

    def extract_ms_bands(self) -> dict:
        """Extract MS bands from the MS orthophoto."""
        ms_ortho = self.ms_bands / "odm_orthophoto" / "odm_orthophoto.tif"

        if not ms_ortho.exists():
            print(f"ERROR: MS orthophoto not found: {ms_ortho}")
            return None

        self.bands_aligned_dir.mkdir(parents=True, exist_ok=True)

        band_names = ["red", "green", "nir", "rededge"]
        bands = {}

        print(f"\nExtracting MS bands from: {ms_ortho}")

        with rasterio.open(ms_ortho) as src:
            profile = src.profile.copy()
            profile.update(count=1, dtype="uint16")

            for i, name in enumerate(band_names):
                data = src.read(i + 1)
                bands[name] = data

                output_path = self.bands_aligned_dir / f"{name}.tif"
                with rasterio.open(output_path, "w", **profile) as dst:
                    dst.write(data, 1)

                print(
                    f"  Extracted {name}: {data.shape}, range=[{data.min()}, {data.max()}]"
                )

        return bands

    def calculate_indices(self, bands: dict) -> dict:
        """Calculate all vegetation indices."""
        self.indices_dir.mkdir(parents=True, exist_ok=True)

        print("\nCalculating vegetation indices...")

        indices = calculate_all_indices(bands)

        ms_ortho = self.ms_bands / "odm_orthophoto" / "odm_orthophoto.tif"
        with rasterio.open(ms_ortho) as src:
            profile = src.profile.copy()

        profile.update(
            dtype="float32",
            count=1,
            nodata=-9999,
        )

        for name, data in indices.items():
            output_path = self.indices_dir / f"{name}.tif"

            data_out = np.nan_to_num(data, nan=-9999)

            with rasterio.open(output_path, "w", **profile) as dst:
                dst.write(data_out.astype(np.float32), 1)

            valid = data[~np.isnan(data)]
            if len(valid) > 0:
                print(f"  {name}: range=[{valid.min():.4f}, {valid.max():.4f}]")

        return indices

    def generate_dem_publication_map(self) -> Path:
        """Generate publication quality DEM map using RGB DEM."""
        from dem_publication_map_fixed import create_publication_map

        dem_path = self.rgb_ortho / "odm_dem" / "dsm.tif"
        output_path = self.output_dir / "dem_publication_map.png"

        print(f"\nGenerating DEM publication map...")
        print(f"  DEM: {dem_path}")
        print(f"  Output: {output_path}")

        create_publication_map(
            dem_path,
            output_path,
            title="Digital Surface Model - Mangrove Site",
            remove_spikes=False,
        )

        return output_path

    def run(self):
        """Run the complete pipeline."""
        print("=" * 60)
        print("MANGROVE PROCESSING PIPELINE")
        print("=" * 60)

        if not self.verify_rgb_products():
            return False

        bands = self.extract_ms_bands()
        if bands is None:
            return False

        self.calculate_indices(bands)

        self.generate_dem_publication_map()

        print("\n" + "=" * 60)
        print("PIPELINE COMPLETE")
        print("=" * 60)
        print(f"Output directory: {self.output_dir}")

        return True


def main():
    parser = argparse.ArgumentParser(description="Mangrove processing pipeline")
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Input directory with DJI images",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output directory",
    )
    args = parser.parse_args()

    pipeline = MangrovePipeline(args.input, args.output)
    success = pipeline.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
