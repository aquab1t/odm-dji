#!/usr/bin/env python3
"""
vegetation_indices.py - Calculate vegetation indices from multispectral bands.

Bands: Red, Green, NIR, RedEdge
Indices: NDVI, NDRE, GNDVI, SAVI, NDWI, EVI, MCARI, CCCI, NDVIre, EVI2
"""

import numpy as np
import rasterio
from pathlib import Path
from typing import Dict


def safe_divide(
    numerator: np.ndarray, denominator: np.ndarray, default: float = np.nan
) -> np.ndarray:
    """Safe division handling zero and NaN values."""
    result = np.full_like(numerator, default, dtype=np.float32)
    valid = (denominator != 0) & ~np.isnan(numerator) & ~np.isnan(denominator)
    result[valid] = numerator[valid] / denominator[valid]
    return result


def calculate_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Normalized Difference Vegetation Index."""
    return safe_divide(nir - red, nir + red)


def calculate_ndre(nir: np.ndarray, rededge: np.ndarray) -> np.ndarray:
    """Normalized Difference Red Edge Index."""
    return safe_divide(nir - rededge, nir + rededge)


def calculate_gndvi(nir: np.ndarray, green: np.ndarray) -> np.ndarray:
    """Green Normalized Difference Vegetation Index."""
    return safe_divide(nir - green, nir + green)


def calculate_savi(nir: np.ndarray, red: np.ndarray, L: float = 0.5) -> np.ndarray:
    """Soil Adjusted Vegetation Index."""
    return (1 + L) * safe_divide(nir - red, nir + red + L)


def calculate_ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """Normalized Difference Water Index."""
    return safe_divide(green - nir, green + nir)


def calculate_evi(
    nir: np.ndarray,
    red: np.ndarray,
    blue: np.ndarray = None,
    G: float = 2.5,
    C1: float = 6.0,
    C2: float = 7.5,
    L: float = 1.0,
) -> np.ndarray:
    """Enhanced Vegetation Index. Uses EVI2 if blue not available."""
    if blue is None:
        return calculate_evi2(nir, red)
    return G * safe_divide(nir - red, nir + C1 * red - C2 * blue + L)


def calculate_evi2(
    nir: np.ndarray, red: np.ndarray, G: float = 2.5, C: float = 2.4, L: float = 1.0
) -> np.ndarray:
    """Two-band Enhanced Vegetation Index (no blue required)."""
    return G * safe_divide(nir - red, nir + C * red + L)


def calculate_mcari(
    rededge: np.ndarray, red: np.ndarray, green: np.ndarray
) -> np.ndarray:
    """Modified Chlorophyll Absorption in Reflectance Index."""
    term1 = rededge - red - 0.2 * (rededge - green)
    term2 = np.abs(rededge - red)
    term3 = np.where(green != 0, green / red, 0)
    return term1 * safe_divide(term2, term3)


def calculate_ccci(ndre: np.ndarray, ndvi: np.ndarray) -> np.ndarray:
    """Canopy Chlorophyll Content Index."""
    return safe_divide(ndre, ndvi)


def calculate_ndvire(nir: np.ndarray, rededge: np.ndarray) -> np.ndarray:
    """Red Edge NDVI (alias for NDRE)."""
    return calculate_ndre(nir, rededge)


def calculate_all_indices(bands: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    """Calculate all vegetation indices from band dictionary.

    Args:
        bands: Dict with keys 'red', 'green', 'nir', 'rededge'

    Returns:
        Dict with all calculated indices
    """
    red = bands["red"].astype(np.float32)
    green = bands["green"].astype(np.float32)
    nir = bands["nir"].astype(np.float32)
    rededge = bands["rededge"].astype(np.float32)

    indices = {
        "ndvi": calculate_ndvi(nir, red),
        "ndre": calculate_ndre(nir, rededge),
        "gndvi": calculate_gndvi(nir, green),
        "savi": calculate_savi(nir, red),
        "ndwi": calculate_ndwi(green, nir),
        "evi": calculate_evi2(nir, red),
        "evi2": calculate_evi2(nir, red),
        "mcari": calculate_mcari(rededge, red, green),
        "ndvire": calculate_ndvire(nir, rededge),
    }

    indices["ccci"] = calculate_ccci(indices["ndre"], indices["ndvi"])

    return indices


def save_index_geotiff(
    index: np.ndarray, output_path: Path, profile: dict, nodata: float = np.nan
) -> None:
    """Save index as GeoTIFF with proper metadata."""
    profile = profile.copy()
    profile.update(
        dtype="float32",
        count=1,
        nodata=-9999 if np.isnan(nodata) else nodata,
        compress="DEFLATE",
        tiled=True,
        blockxsize=512,
        blockysize=512,
    )

    if np.isnan(nodata):
        index = np.nan_to_num(index, nan=-9999)

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(index.astype(np.float32), 1)
