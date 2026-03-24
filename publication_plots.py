#!/usr/bin/env python3
"""
publication_plots.py - Create publication quality plots for drone mapping.

Features:
- DEM with contours, hillshade, lat/lon coordinates
- RGB orthophoto with white background for nodata
- 3D perspective view
- Vegetation index maps (NDVI, NDRE, GNDVI, NDWI)
- Scale bar and north arrow on all plots
- Configurable elevation offset

Usage:
    python3 publication_plots.py --dem /path/to/dsm.tif --rgb /path/to/ortho.tif --output /path/to/output/
    python3 publication_plots.py --dem dsm.tif --rgb ortho.tif --output plots/ --indices /path/to/indices/
"""

import argparse
import sys
from pathlib import Path
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource, LinearSegmentedColormap
from scipy import ndimage


def get_latlon_bounds(tif_path, height, width):
    """Get lat/lon bounds for a GeoTIFF."""
    with rasterio.open(tif_path) as src:
        bounds = src.bounds
        src_crs = src.crs
        bounds_4326 = transform_bounds(
            src_crs, "EPSG:4326", bounds.left, bounds.bottom, bounds.right, bounds.top
        )
        return bounds_4326[0], bounds_4326[2], bounds_4326[1], bounds_4326[3]


def clean_dem_outliers(dem, nodata):
    """Remove outliers and fill gaps using median filter."""
    if nodata is not None:
        valid_mask = dem != nodata
    else:
        valid_mask = ~np.isnan(dem)

    valid = dem[valid_mask]
    if len(valid) == 0:
        return dem

    mean, std = valid.mean(), valid.std()
    outlier_mask = (np.abs(dem - mean) > 3 * std) & valid_mask
    n_outliers = np.sum(outlier_mask)

    if n_outliers > 0:
        print(f"  Removing {n_outliers:,} outlier pixels")
        dem_clean = dem.copy()
        dem_clean[outlier_mask] = nodata if nodata is not None else np.nan
        dem_filled = ndimage.median_filter(
            np.where(valid_mask, dem, np.nanmedian(dem)), size=5
        )
        dem_clean = np.where(outlier_mask, dem_filled, dem_clean)
        return dem_clean

    return dem


def add_scale_bar(ax, lon_min, lon_max, lat_min, lat_max):
    """Add a scale bar in bottom right corner."""
    meters_per_deg = 111320
    lon_range = lon_max - lon_min
    lat_range = lat_max - lat_min
    width_meters = (
        lon_range * meters_per_deg * np.cos(np.radians((lat_min + lat_max) / 2))
    )

    if width_meters > 1000:
        length_meters = int(round(width_meters / 5 / 100) * 100)
        label = f"{length_meters // 1000} km"
    else:
        length_meters = int(round(width_meters / 5 / 10) * 10)
        label = f"{length_meters} m"

    length_deg = (
        length_meters / meters_per_deg / np.cos(np.radians((lat_min + lat_max) / 2))
    )

    x_start = lon_max - lon_range * 0.25
    y_pos = lat_min + lat_range * 0.08

    bar_height = lat_range * 0.008
    ax.plot(
        [x_start, x_start + length_deg], [y_pos, y_pos], "k-", linewidth=3, zorder=10
    )
    ax.plot(
        [x_start, x_start],
        [y_pos - bar_height, y_pos + bar_height],
        "k-",
        linewidth=2,
        zorder=10,
    )
    ax.plot(
        [x_start + length_deg, x_start + length_deg],
        [y_pos - bar_height, y_pos + bar_height],
        "k-",
        linewidth=2,
        zorder=10,
    )
    ax.text(
        x_start + length_deg / 2,
        y_pos + bar_height * 2.5,
        label,
        ha="center",
        va="bottom",
        fontsize=11,
        fontweight="bold",
        zorder=10,
        bbox=dict(
            boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.9
        ),
    )


def add_north_arrow(ax, lon_min, lon_max, lat_min, lat_max):
    """Add a north arrow."""
    lon_range = lon_max - lon_min
    lat_range = lat_max - lat_min

    x_pos = lon_max - lon_range * 0.06
    y_pos = lat_max - lat_range * 0.15

    ax.annotate(
        "",
        xy=(x_pos, y_pos + lat_range * 0.06),
        xytext=(x_pos, y_pos),
        arrowprops=dict(arrowstyle="->", color="black", lw=2.5),
        zorder=10,
    )
    ax.text(
        x_pos,
        y_pos + lat_range * 0.07,
        "N",
        ha="center",
        va="bottom",
        fontsize=14,
        fontweight="bold",
        zorder=10,
        bbox=dict(
            boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.9
        ),
    )


def create_dem_plot(dem_path, rgb_path, output_dir, elevation_offset=0, title=None):
    """Create DEM with lat/lon, basemap, scale bar, and north arrow."""
    dem_path = Path(dem_path)
    rgb_path = Path(rgb_path)
    output_dir = Path(output_dir)

    print("Creating DEM plot...")

    with rasterio.open(dem_path) as src:
        downsample = 4
        height, width = src.height // downsample, src.width // downsample
        dem = src.read(1, out_shape=(height, width), resampling=Resampling.average)
        nodata = src.nodata
        if nodata is not None:
            dem = np.where(dem == nodata, np.nan, dem)

    lon_min, lon_max, lat_min, lat_max = get_latlon_bounds(rgb_path, height, width)

    dem = clean_dem_outliers(dem, np.nan)

    dem_offset = dem - np.nanmin(dem) + elevation_offset
    dem_clean = np.nan_to_num(dem_offset, nan=np.nanmean(dem_offset))

    elev_min = np.nanmin(dem_offset)
    elev_max = np.nanmax(dem_offset)
    print(f"  Elevation: {elev_min:.2f} to {elev_max:.2f} m")

    fig, ax = plt.subplots(figsize=(14, 12), dpi=150)
    ax.set_facecolor("#e6f2ff")

    ls = LightSource(azdeg=315, altdeg=45)
    dx = (lon_max - lon_min) / width * 111000
    dy = (lat_max - lat_min) / height * 111000
    hillshade = ls.hillshade(dem_clean, vert_exag=1.5, dx=dx, dy=dy)

    turbo_colors = [
        "#30123b",
        "#3d3984",
        "#4d68c4",
        "#5f96d6",
        "#73c2d4",
        "#8ce7b6",
        "#aef887",
        "#d4f545",
        "#f9d62c",
        "#fc9f24",
        "#f7671d",
        "#d93820",
    ]
    turbo = LinearSegmentedColormap.from_list("turbo", turbo_colors)

    dem_plot = ax.imshow(
        dem_clean,
        extent=[lon_min, lon_max, lat_min, lat_max],
        cmap=turbo,
        aspect="equal",
        zorder=1,
    )
    ax.imshow(
        hillshade,
        extent=[lon_min, lon_max, lat_min, lat_max],
        cmap="gray",
        alpha=0.25,
        aspect="equal",
        zorder=2,
    )

    lon = np.linspace(lon_min, lon_max, width)
    lat = np.linspace(lat_max, lat_min, height)
    X, Y = np.meshgrid(lon, lat)

    levels = np.linspace(np.nanmin(dem_clean), np.nanmax(dem_clean), 12)
    contours = ax.contour(
        X,
        Y,
        dem_clean,
        levels=levels,
        colors="black",
        linewidths=0.5,
        alpha=0.6,
        zorder=3,
    )
    ax.clabel(contours, inline=True, fontsize=8, fmt="%.1f")

    cbar = plt.colorbar(dem_plot, ax=ax, shrink=0.6, pad=0.02, aspect=30)
    cbar.set_label("Elevation (m)", fontsize=12)
    cbar.ax.tick_params(labelsize=10)

    add_scale_bar(ax, lon_min, lon_max, lat_min, lat_max)
    add_north_arrow(ax, lon_min, lon_max, lat_min, lat_max)

    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)

    plot_title = title or "Digital Elevation Model"
    ax.set_title(plot_title, fontsize=18, fontweight="bold", pad=15)
    ax.set_xlabel("Longitude (°)", fontsize=12)
    ax.set_ylabel("Latitude (°)", fontsize=12)

    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x:.4f}"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x:.4f}"))

    ax.text(
        0.02,
        0.98,
        f"Elev: {elev_min:.1f} to {elev_max:.1f} m",
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        zorder=10,
        bbox=dict(
            boxstyle="round,pad=0.5", facecolor="white", edgecolor="gray", alpha=0.95
        ),
    )

    plt.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(
        output_dir / "dem_contours.png", dpi=150, bbox_inches="tight", facecolor="white"
    )
    plt.savefig(
        output_dir / "dem_contours.jpg", dpi=150, bbox_inches="tight", facecolor="white"
    )
    plt.close()
    print(f"  Created: dem_contours.png")


def create_rgb_plot(rgb_path, output_dir, title=None):
    """Create RGB orthophoto with white background."""
    rgb_path = Path(rgb_path)
    output_dir = Path(output_dir)

    print("Creating RGB plot...")

    with rasterio.open(rgb_path) as src:
        height, width = src.height // 4, src.width // 4
        n_bands = min(4, src.count)
        rgb = np.zeros((n_bands, height, width), dtype=np.float32)
        for i in range(n_bands):
            rgb[i] = src.read(
                i + 1, out_shape=(height, width), resampling=Resampling.bilinear
            )

    lon_min, lon_max, lat_min, lat_max = get_latlon_bounds(rgb_path, height, width)

    if n_bands >= 4:
        alpha = rgb[3]
        rgb = rgb[:3].transpose(1, 2, 0)
    else:
        rgb = rgb[:3].transpose(1, 2, 0)
        alpha = np.ones((height, width))

    for i in range(3):
        band = rgb[:, :, i]
        valid = band[band > 0]
        if len(valid) > 0:
            p2, p98 = np.percentile(valid, [2, 98])
            rgb[:, :, i] = np.clip((band - p2) / (p98 - p2 + 1e-10) * 255, 0, 255)

    rgb = rgb.astype(np.uint8)

    rgb_white = np.ones((height, width, 3), dtype=np.uint8) * 255
    mask = alpha > 10
    for i in range(3):
        rgb_white[:, :, i] = np.where(mask, rgb[:, :, i], 255)

    fig, ax = plt.subplots(figsize=(14, 12), dpi=150)
    ax.set_facecolor("#e6f2ff")

    ax.imshow(
        rgb_white, extent=[lon_min, lon_max, lat_min, lat_max], aspect="equal", zorder=1
    )

    add_scale_bar(ax, lon_min, lon_max, lat_min, lat_max)
    add_north_arrow(ax, lon_min, lon_max, lat_min, lat_max)

    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)

    plot_title = title or "RGB Orthophoto"
    ax.set_title(plot_title, fontsize=18, fontweight="bold", pad=15)
    ax.set_xlabel("Longitude (°)", fontsize=12)
    ax.set_ylabel("Latitude (°)", fontsize=12)

    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x:.4f}"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x:.4f}"))

    plt.tight_layout()
    plt.savefig(
        output_dir / "rgb_orthophoto.png",
        dpi=150,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.savefig(
        output_dir / "rgb_orthophoto.jpg",
        dpi=150,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close()
    print(f"  Created: rgb_orthophoto.png")


def create_index_plot(
    idx_path, rgb_path, output_dir, idx_name, cmap="RdYlGn", title=None
):
    """Create vegetation index map with proper naming."""
    idx_path = Path(idx_path)
    rgb_path = Path(rgb_path)
    output_dir = Path(output_dir)

    if not idx_path.exists():
        print(f"  Skipping {idx_name}: file not found")
        return

    print(f"Creating {idx_name.upper()} plot...")

    with rasterio.open(idx_path) as src:
        height, width = src.height // 4, src.width // 4
        data = src.read(1, out_shape=(height, width), resampling=Resampling.bilinear)
        nodata = src.nodata
        if nodata is not None:
            data = np.where(data == nodata, np.nan, data)

    lon_min, lon_max, lat_min, lat_max = get_latlon_bounds(rgb_path, height, width)

    valid = data[~np.isnan(data)]
    if len(valid) == 0:
        return

    vmin, vmax = np.percentile(valid, 2), np.percentile(valid, 98)

    titles = {
        "ndvi": "Normalized Difference Vegetation Index (NDVI)\nVegetation Health & Density",
        "ndre": "Normalized Difference Red Edge (NDRE)\nChlorophyll & Nitrogen Content",
        "gndvi": "Green NDVI (GNDVI)\nVegetation Water Content",
        "ndwi": "Normalized Difference Water Index (NDWI)\nWater Stress & Moisture",
    }

    fig, ax = plt.subplots(figsize=(14, 12), dpi=150)
    ax.set_facecolor("#e6f2ff")

    im = ax.imshow(
        data,
        extent=[lon_min, lon_max, lat_min, lat_max],
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        aspect="equal",
        zorder=1,
    )

    cbar = plt.colorbar(im, ax=ax, shrink=0.6, pad=0.02, aspect=30)
    cbar.set_label("Index Value", fontsize=12)
    cbar.ax.tick_params(labelsize=10)

    add_scale_bar(ax, lon_min, lon_max, lat_min, lat_max)
    add_north_arrow(ax, lon_min, lon_max, lat_min, lat_max)

    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)

    plot_title = title or titles.get(idx_name, idx_name.upper())
    ax.set_title(plot_title, fontsize=16, fontweight="bold", pad=15)
    ax.set_xlabel("Longitude (°)", fontsize=12)
    ax.set_ylabel("Latitude (°)", fontsize=12)

    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x:.4f}"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x:.4f}"))

    plt.tight_layout()
    plt.savefig(
        output_dir / f"{idx_name}.png", dpi=150, bbox_inches="tight", facecolor="white"
    )
    plt.savefig(
        output_dir / f"{idx_name}.jpg", dpi=150, bbox_inches="tight", facecolor="white"
    )
    plt.close()
    print(f"  Created: {idx_name}.png")


def create_3d_perspective(
    dem_path, rgb_path, output_dir, elevation_offset=0, title=None
):
    """Create 3D perspective view."""
    dem_path = Path(dem_path)
    rgb_path = Path(rgb_path)
    output_dir = Path(output_dir)

    print("Creating 3D perspective...")

    with rasterio.open(dem_path) as src:
        dem = src.read(
            1,
            out_shape=(src.height // 6, src.width // 6),
            resampling=Resampling.average,
        )
        nodata = src.nodata
        transform = src.transform
        if nodata is not None:
            dem = np.where(dem == nodata, np.nan, dem)

    x = np.arange(dem.shape[1]) * abs(transform[0])
    y = np.arange(dem.shape[0]) * transform[4]
    x = x - x.min()
    y = y - y.min()

    dem = clean_dem_outliers(dem, np.nan)

    with rasterio.open(rgb_path) as src:
        h, w = dem.shape
        n_bands = min(4, src.count)
        rgb = np.zeros((n_bands, h, w), dtype=np.float32)
        for i in range(n_bands):
            rgb[i] = src.read(i + 1, out_shape=(h, w), resampling=Resampling.bilinear)

    if n_bands >= 4:
        alpha = rgb[3]
        rgb = rgb[:3].transpose(1, 2, 0)
    else:
        rgb = rgb[:3].transpose(1, 2, 0)
        alpha = np.ones((h, w))

    for i in range(3):
        band = rgb[:, :, i]
        valid = band[band > 0]
        if len(valid) > 0:
            p2, p98 = np.percentile(valid, [2, 98])
            rgb[:, :, i] = np.clip((band - p2) / (p98 - p2 + 1e-10) * 255, 0, 255)

    rgb = rgb.astype(np.uint8)

    for i in range(3):
        rgb[:, :, i] = np.where(alpha > 10, rgb[:, :, i], 255)

    dem_offset = dem - np.nanmin(dem) + elevation_offset
    dem_clean = np.nan_to_num(dem_offset, nan=np.nanmean(dem_offset))

    from mpl_toolkits.mplot3d import Axes3D

    fig = plt.figure(figsize=(16, 12), dpi=150)
    ax = fig.add_subplot(111, projection="3d")

    X, Y = np.meshgrid(x, y)
    rgb_norm = rgb / 255.0

    ls = LightSource(azdeg=315, altdeg=45)

    ax.plot_surface(
        X,
        Y,
        dem_clean,
        facecolors=rgb_norm,
        shade=True,
        lightsource=ls,
        antialiased=True,
    )

    ax.set_xlabel("Distance East (m)", fontsize=12, labelpad=10)
    ax.set_ylabel("Distance North (m)", fontsize=12, labelpad=10)
    ax.set_zlabel("Elevation (m)", fontsize=12, labelpad=10)

    plot_title = title or "3D Perspective View"
    ax.set_title(plot_title, fontsize=18, fontweight="bold", pad=20)

    ax.view_init(elev=25, azim=45)

    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(
        output_dir / "3d_perspective.png",
        dpi=150,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.savefig(
        output_dir / "3d_perspective.jpg",
        dpi=150,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close()
    print(f"  Created: 3d_perspective.png")


def main():
    parser = argparse.ArgumentParser(
        description="Create publication quality plots from drone data"
    )
    parser.add_argument("--dem", "-d", required=True, help="Path to DEM GeoTIFF (DSM)")
    parser.add_argument(
        "--rgb", "-r", required=True, help="Path to RGB orthophoto GeoTIFF"
    )
    parser.add_argument(
        "--output", "-o", required=True, help="Output directory for plots"
    )
    parser.add_argument(
        "--indices", "-i", help="Directory containing vegetation index GeoTIFFs"
    )
    parser.add_argument(
        "--offset",
        type=float,
        default=0,
        help="Elevation offset in meters (default: 0)",
    )
    parser.add_argument("--title", help="Base title for plots")

    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("CREATING PUBLICATION QUALITY PLOTS")
    print("=" * 60)

    create_dem_plot(
        args.dem, args.rgb, output_dir, elevation_offset=args.offset, title=args.title
    )
    create_rgb_plot(args.rgb, output_dir, title=args.title)
    create_3d_perspective(
        args.dem, args.rgb, output_dir, elevation_offset=args.offset, title=args.title
    )

    if args.indices:
        indices_dir = Path(args.indices)
        index_configs = [
            ("ndvi", "RdYlGn"),
            ("ndre", "YlGn"),
            ("gndvi", "YlGn"),
            ("ndwi", "RdYlBu"),
        ]

        for idx_name, cmap in index_configs:
            idx_path = indices_dir / f"{idx_name}.tif"
            if idx_path.exists():
                create_index_plot(
                    idx_path, args.rgb, output_dir, idx_name, cmap, title=args.title
                )

    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)
    print(f"\nOutput: {output_dir}")
    print("\nFiles created:")
    for f in sorted(output_dir.glob("*.png")):
        print(f"  {f.name} ({f.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
