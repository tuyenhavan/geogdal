import os

import geopandas as gpd
from osgeo import gdal
from shapely.geometry import box


def merge_raster(file_list, outpath, xres=10, yres=10, resample="bilinear"):
    """Merge raster files into a single raster file.
    Args:
        file_list (list): List of input raster file paths.
        outpath (str): Output raster file path.
        xres (float, optional): Output raster x resolution. Defaults to 10.
        yres (float, optional): Output raster y resolution. Defaults to 10.
        resample (str, optional): Resampling method. Defaults to "bilinear".
            Options include "nearest", "bilinear", "cubic", etc.
    Returns:
        None
    """

    gdal.SetConfigOption("GDAL_NUM_THREADS", "ALL_CPUS")
    # os.environ['GTIFF_SRS_SOURCE'] = 'EPSG'

    folder = os.path.dirname(outpath)
    vrt = gdal.BuildVRT(os.path.join(folder, "temp.vrt"), file_list)
    if os.path.basename(outpath).endswith(".tif"):
        gdal.Translate(
            outpath,
            vrt,
            format="GTiff",
            creationOptions=["COMPRESS=LZW", "TILED=YES", "BIGTIFF=YES"],
            xRes=xres,
            yRes=yres,
            resampleAlg=resample,
        )
        vrt = None
        if os.path.exists(os.path.join(folder, "temp.vrt")):
            os.remove(os.path.join(folder, "temp.vrt"))
    else:
        print("Output should be a .tif file!")


def generate_grids_from_aoi(gdf, ncols=4, nrows=2, predicate="intersects"):
    """
    Split the extent of a GeoDataFrame into a grid (ncols * nrows parts)
    and add a column to the original GeoDataFrame indicating
    which grid cell (part) each feature belongs to.

    Parameters
    ----------
    gdf : GeoDataFrame
        Input GeoDataFrame with geometries.
    nx : int, default=4
        Number of columns (horizontal divisions).
    ny : int, default=2
        Number of rows (vertical divisions).
    predicate : str, default="intersects"
        Spatial join predicate ("intersects", "within", "contains", etc.)

    Returns
    -------
    gdf_with_zones : GeoDataFrame
        Original GeoDataFrame with a new column 'zones'
        showing which grid cell each feature belongs to.
    """
    if gdf.empty:
        raise ValueError("Input GeoDataFrame is empty.")
    if not isinstance(gdf, gpd.GeoDataFrame):
        raise TypeError("Input must be a GeoDataFrame.")
    if gdf.crs is None:
        raise ValueError("Input GeoDataFrame must have a valid CRS.")

    # 1. Get bounding box of input geometries
    minx, miny, maxx, maxy = gdf.total_bounds

    # 2. Compute grid size
    dx = (maxx - minx) / ncols
    dy = (maxy - miny) / nrows

    # 3. Generate grid polygons
    tiles = []
    names = []
    for i in range(ncols):
        for j in range(nrows):
            x0 = minx + i * dx
            x1 = x0 + dx
            y0 = miny + j * dy
            y1 = y0 + dy
            tiles.append(box(x0, y0, x1, y1))
            names.append(f"zone_{j*ncols + i + 1}")

    tiles_gdf = gpd.GeoDataFrame({"zones": names, "geometry": tiles}, crs=gdf.crs)

    # 4. Spatial join: assign zone name to each feature
    joined = gpd.sjoin(
        gdf, tiles_gdf[["zones", "geometry"]], how="left", predicate=predicate
    )
    # 5. Handle duplicates - keep only the first match for each original polygon
    # Create a dictionary mapping from original indices to zones (first occurrence only)
    index_to_zones = {}
    for idx, row in joined.iterrows():
        if idx not in index_to_zones:  # Keep only first occurrence
            index_to_zones[idx] = row["zones"]

    # 6. Return the original data + new column
    gdf_with_zones = gdf.copy()
    if "zones" in gdf_with_zones.columns:
        new_col_name = "parts"
    else:
        new_col_name = "zones"
    gdf_with_zones[new_col_name] = gdf_with_zones.index.map(index_to_zones)

    return gdf_with_zones
