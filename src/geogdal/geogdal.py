import os

import geopandas as gpd
from osgeo import gdal
from shapely.geometry import box
gdal.UseExceptions()


def _to_gdal_type(dtype):
    """Convert a type name like 'Float32' to a GDAL constant."""
    if isinstance(dtype, int):
        return dtype  # already a GDAL constant (e.g. gdal.GDT_Float32)
    code = gdal.GetDataTypeByName(dtype)
    if code == gdal.GDT_Unknown:
        raise ValueError(f"Unknown dtype: {dtype!r}")
    return code


def merge_raster(file_list, outfile, xres=None, yres=None, resample="bilinear", crs=None, nodata=None, dtype="Float32"):
    """Merge raster files into a single raster file.
    Args:
        file_list (list): List of input raster file paths.
        outfile (str): Output raster file path.
        xres (float, optional): Output raster x resolution. Defaults to None.
        yres (float, optional): Output raster y resolution. Defaults to None.
        resample (str, optional): Resampling method. Defaults to "bilinear".
            Options include "nearest", "bilinear", "cubic", etc.
        crs (str, optional): Target CRS, e.g. "EPSG:32630". Defaults to None.
        nodata (float, optional): Nodata value for source and output. Defaults to None.
        dtype (str, optional): Output data type, e.g. "Float32", "Float64", "Int16", "UInt16", "Byte". Defaults to "Float32".
    Returns:
        None
    """
    if not isinstance(file_list, list):
        raise TypeError("file_list must be a list of raster file paths.")
    if not isinstance(outfile, str):
        raise TypeError(
            "outfile must be a string representing the output file path.")
    if resample == "nearest":
        resample = "near"
    resample_list = [
        "bilinear",
        "near",
        "cubic",
        "cubicspline",
        "average",
        "mode",
        "max",
        "min",
        "med",
        "q1",
        "q3",
        "sum",
    ]
    if resample not in resample_list:
        raise ValueError(f"Please select the follow methods {resample_list}")
    gdal.SetConfigOption("GDAL_NUM_THREADS", "ALL_CPUS")
    os.environ["GTIFF_SRS_SOURCE"] = "EPSG"
    if not outfile.lower().endswith(".tif"):
        outfile += ".tif"
    opts = {
        "format": "GTiff",
        "creationOptions": ["COMPRESS=LZW", "TILED=YES", "BIGTIFF=YES"],
        "resampleAlg": resample,
        "multithread": True,
    }
    if xres is not None:
        opts["xRes"] = xres
    if yres is not None:
        opts["yRes"] = yres
    if crs is not None:
        opts["dstSRS"] = crs
    if nodata is not None:
        opts["dstNodata"] = nodata
    if dtype is not None:
        opts["outputType"] = _to_gdal_type(dtype)
    ds = gdal.Warp(outfile, file_list, **opts)
    if ds is not None:
        ds = None


def merge_raster_without_specific_resolution(file_list, outfile):
    """Merge raster files into a single GeoTIFF.
    All rasters must have the same CRS, resolution, and grid alignment.
    Args:
        file_list (list): List of input raster file paths.
        outfile (str): Output raster file path.
    Returns:
        None
    """
    if not isinstance(file_list, list):
        raise TypeError("file_list must be a list of raster file paths.")
    if not isinstance(outfile, str):
        raise TypeError(
            "outfile must be a string representing the output file path.")
    # check if the file ends with tif
    if not outfile.lower().endswith(".tif"):
        outfile += ".tif"
    gdal.SetConfigOption("GDAL_NUM_THREADS", "ALL_CPUS")

    folder = os.path.dirname(outfile)
    vrt_path = os.path.join(folder, "temp.vrt")

    vrt = gdal.BuildVRT(vrt_path, file_list)

    gdal.Translate(
        outfile,
        vrt,
        format="GTiff",
        creationOptions=[
            "COMPRESS=LZW",
            "TILED=YES",
            "BIGTIFF=YES",
        ],
    )

    vrt = None
    if os.path.exists(vrt_path):
        os.remove(vrt_path)


def generate_grids_from_aoi(gdf, ncols=4, nrows=2, predicate="intersects"):
    """
    Split the extent of a GeoDataFrame into a grid (ncols * nrows parts)
    and add a column to the original GeoDataFrame indicating
    which grid cell (part) each feature belongs to.

    Args:
    gdf : GeoDataFrame
        Input GeoDataFrame with geometries.
    ncols : int, default=4
        Number of columns (horizontal divisions).
    nrows : int, default=2
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

    tiles_gdf = gpd.GeoDataFrame(
        {"zones": names, "geometry": tiles}, crs=gdf.crs)

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


def resample_raster(input_file, out_file, xres=None, yres=None, resample='bilinear',
                    out_crs=None, nodata=None, dtype=None):
    """Resample a raster file to a new resolution and optionally reproject it.
    Args:
        input_file (str): Path to the input raster file.
        out_file (str): Path to the output resampled raster file.
        xres (float, optional): Target resolution in the x direction. Default is None (use original resolution).
        yres (float, optional): Target resolution in the y direction. Default is None (use original resolution).
        resample (str, optional): Resampling method ('nearest', 'bilinear', 'cubic', 'cubicspline', 'lanczos', 'average', 'mode', 'max', 'min', 'med', 'q1', 'q3', etc.). Default is 'bilinear'.
        out_crs (str or CRS, optional): Target coordinate reference system. Default is None (no reprojection).
        nodata (float, optional): Value to use for nodata. Default is None.
        dtype (str, optional): Data type for the output raster. Default is None.

    Returns:
        None
    """
    if resample == 'nearest':
        resample = 'near'
    dtype_map = {
        'uint8': gdal.GDT_Int8,
        'int16': gdal.GDT_Int16,
        'uint16': gdal.GDT_UInt16,
        'int32': gdal.GDT_Int32,
        'uint32': gdal.GDT_UInt32,
        'float32': gdal.GDT_Float32,
        'float64': gdal.GDT_Float64
    }
    if dtype is not None and dtype not in dtype_map:
        raise ValueError(
            f"Unsupported dtype: {dtype}. Supported dtypes are: {list(dtype_map.keys())}")
    resample_list = ['near', 'bilinear', 'cubic', 'cubicspline',
                     'lanczos', 'average', 'mode', 'max', 'min', 'med', 'q1', 'q3']
    if resample not in resample_list:
        raise ValueError(
            f"Unsupported resample method: {resample}. Supported methods are: {resample_list}")
    options = {
        "resampleAlg": resample,
        "multithread": True,
        "format": "GTiff",
        "creationOptions": ["COMPRESS=LZW", "TILED=YES", "BIGTIFF=YES"]
    }

    if xres is not None:
        options["xRes"] = xres
    if yres is not None:
        options["yRes"] = yres
    if out_crs is not None:
        options["dstSRS"] = out_crs if isinstance(
            out_crs, str) else out_crs.to_wkt()
    if nodata is not None:
        options["dstNodata"] = nodata
    if dtype is not None:
        options["outputType"] = dtype_map[dtype]
    ds = gdal.Warp(out_file, input_file, options=gdal.WarpOptions(**options))
    if ds is None:
        raise RuntimeError(
            f"Failed to resample raster: {input_file} to {out_file}")
    ds = None
