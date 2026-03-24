#!/usr/bin/env python3
"""
dem_3d_rgb_mesh.py - Create 3D visualization with RGB texture using Mesh3d.

This properly overlays RGB orthophoto on DEM using Plotly's Mesh3d with vertex colors.
No vertical exaggeration by default.

Usage:
    python3 dem_3d_rgb_mesh.py --dem /path/to/dem.tif --rgb /path/to/ortho.tif --output /path/to/output.html
"""

import argparse
import sys
from pathlib import Path
import numpy as np
import rasterio
from rasterio.enums import Resampling
import plotly.graph_objects as go


def load_dem(dem_path: Path, downsample: int = 1) -> tuple:
    """Load DEM from GeoTIFF."""
    with rasterio.open(dem_path) as src:
        if downsample > 1:
            out_shape = (src.height // downsample, src.width // downsample)
            dem = src.read(1, out_shape=out_shape, resampling=Resampling.average)
            transform = src.transform * src.transform.scale(downsample, downsample)
        else:
            dem = src.read(1)
            transform = src.transform

        nodata = src.nodata
        if nodata is not None:
            dem = np.where(dem == nodata, np.nan, dem)

        x = np.arange(dem.shape[1]) * abs(transform[0]) + transform[2]
        y = np.arange(dem.shape[0]) * transform[4] + transform[5]

    return dem, x, y


def load_rgb(rgb_path: Path, target_shape: tuple) -> np.ndarray:
    """Load and resample RGB orthophoto to match DEM dimensions."""
    target_h, target_w = target_shape

    with rasterio.open(rgb_path) as src:
        n_bands = min(3, src.count)
        rgb = src.read(
            indexes=list(range(1, n_bands + 1)),
            out_shape=(n_bands, target_h, target_w),
            resampling=Resampling.bilinear,
        )
        rgb = rgb.transpose(1, 2, 0)

        if rgb.shape[2] == 1:
            rgb = np.repeat(rgb, 3, axis=2)

        for i in range(min(3, rgb.shape[2])):
            band = rgb[:, :, i]
            valid = band[band > 0]
            if len(valid) > 0:
                p2, p98 = np.percentile(valid, [2, 98])
                band_min, band_max = max(0, p2), min(65535, p98)
                rgb[:, :, i] = np.clip(
                    (band - band_min) / (band_max - band_min + 1e-10) * 255, 0, 255
                )

        rgb = rgb[:, :, :3].astype(np.uint8)

    return rgb


def create_mesh3d_rgb(
    dem: np.ndarray,
    rgb: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    title: str = "3D RGB Map",
    vertical_exaggeration: float = 1.0,
) -> go.Figure:
    """Create 3D mesh with RGB vertex colors."""

    dem_mean = np.nanmean(dem)
    dem = np.nan_to_num(dem, nan=dem_mean)
    Z = dem * vertical_exaggeration

    X, Y = np.meshgrid(x, y)

    h, w = dem.shape

    print(f"  Building mesh: {h}x{w} = {h * w:,} vertices")
    print(f"  Creating triangles...")

    i_indices = []
    j_indices = []
    k_indices = []

    for row in range(h - 1):
        for col in range(w - 1):
            idx = row * w + col
            i_indices.extend([idx, idx + 1, idx + w, idx + 1])
            j_indices.extend([idx + w, idx + w + 1, idx + w + 1, idx])
            k_indices.extend([idx + 1, idx + w + 1, idx, idx + w])

    print(f"  Total triangles: {len(i_indices):,}")

    vertices_x = X.flatten()
    vertices_y = Y.flatten()
    vertices_z = Z.flatten()

    print(f"  Assigning vertex colors...")

    colors = np.zeros((h * w, 3), dtype=np.uint8)
    colors[:, 0] = rgb[:, :, 0].flatten()
    colors[:, 1] = rgb[:, :, 1].flatten()
    colors[:, 2] = rgb[:, :, 2].flatten()

    vertexcolor = [f"rgb({r},{g},{b})" for r, g, b in colors]

    print(f"  Creating Plotly figure...")

    fig = go.Figure()

    mesh = go.Mesh3d(
        x=vertices_x,
        y=vertices_y,
        z=vertices_z,
        i=i_indices,
        j=j_indices,
        k=k_indices,
        vertexcolor=vertexcolor,
        lighting=dict(
            ambient=0.7,
            diffuse=0.8,
            fresnel=0.0,
            specular=0.1,
            roughness=0.8,
        ),
        lightposition=dict(x=10000, y=10000, z=1000),
        hovertemplate="<b>Elevation: %{z:.2f} m</b><br>"
        + "Easting: %{x:.1f} m<br>"
        + "Northing: %{y:.1f} m<extra></extra>",
    )

    fig.add_trace(mesh)

    aspect_ratio = w / h
    z_range = Z.max() - Z.min()
    xy_range = max(x.max() - x.min(), y.max() - y.min())
    z_aspect = (z_range / xy_range) * 2 if xy_range > 0 else 0.2

    fig.update_layout(
        title=dict(
            text=title, x=0.5, xanchor="center", font=dict(size=20, color="black")
        ),
        scene=dict(
            xaxis=dict(
                title="Easting (m)",
                tickfont=dict(size=10),
                backgroundcolor="white",
                gridcolor="lightgray",
            ),
            yaxis=dict(
                title="Northing (m)",
                tickfont=dict(size=10),
                backgroundcolor="white",
                gridcolor="lightgray",
            ),
            zaxis=dict(
                title="Elevation (m)",
                tickfont=dict(size=10),
                backgroundcolor="white",
                gridcolor="lightgray",
            ),
            camera=dict(
                eye=dict(x=-1.5, y=-1.5, z=0.8),
                up=dict(x=0, y=0, z=1),
                center=dict(x=0, y=0, z=0),
            ),
            aspectmode="manual",
            aspectratio=dict(x=aspect_ratio, y=1, z=z_aspect),
        ),
        width=1400,
        height=1000,
        paper_bgcolor="white",
        margin=dict(l=0, r=0, t=50, b=0),
    )

    return fig


def export_to_html(fig: go.Figure, output_path: Path):
    """Export figure to standalone HTML file."""
    fig.write_html(
        str(output_path),
        include_plotlyjs="cdn",
        full_html=True,
        config={
            "displayModeBar": True,
            "scrollZoom": True,
            "displaylogo": False,
            "toImageButtonOptions": {
                "format": "png",
                "filename": "dem_3d_rgb",
                "height": 1200,
                "width": 1600,
                "scale": 2,
            },
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        },
    )


def main():
    parser = argparse.ArgumentParser(description="Create 3D RGB mesh visualization")
    parser.add_argument("--dem", "-d", required=True, help="Path to DEM GeoTIFF")
    parser.add_argument(
        "--rgb", "-r", required=True, help="Path to RGB orthophoto GeoTIFF"
    )
    parser.add_argument(
        "--output", "-o", required=True, help="Output path for HTML file"
    )
    parser.add_argument(
        "--title", "-t", default="3D RGB Map - Mangrove Site", help="Map title"
    )
    parser.add_argument(
        "--downsample", "-s", type=int, default=4, help="Downsample factor"
    )
    parser.add_argument(
        "--exaggeration", "-e", type=float, default=1.0, help="Vertical exaggeration"
    )
    args = parser.parse_args()

    dem_path = Path(args.dem).resolve()
    rgb_path = Path(args.rgb).resolve()
    output_path = Path(args.output).resolve()

    if not dem_path.exists():
        sys.exit(f"DEM not found: {dem_path}")
    if not rgb_path.exists():
        sys.exit(f"RGB orthophoto not found: {rgb_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading DEM: {dem_path}")
    dem, x, y = load_dem(dem_path, downsample=args.downsample)
    print(f"DEM size: {dem.shape[1]} x {dem.shape[0]} pixels")
    print(f"Elevation range: {np.nanmin(dem):.2f} - {np.nanmax(dem):.2f} m")

    print(f"\nLoading RGB orthophoto: {rgb_path}")
    rgb = load_rgb(rgb_path, target_shape=dem.shape)
    print(f"RGB size: {rgb.shape[1]} x {rgb.shape[0]} pixels")

    print("\nCreating 3D mesh with RGB texture...")
    fig = create_mesh3d_rgb(
        dem, rgb, x, y, title=args.title, vertical_exaggeration=args.exaggeration
    )

    print(f"\nExporting to HTML: {output_path}")
    export_to_html(fig, output_path)

    print(f"\n=== Interactive 3D RGB Mesh Created ===")
    print(f"Open in browser: file://{output_path}")


if __name__ == "__main__":
    main()
