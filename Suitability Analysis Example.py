import rasterio
import numpy as np
import os
import glob
from scipy.spatial import cKDTree
from rasterio.warp import calculate_default_transform, reproject, Resampling
from moving_window import mean_filter
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

#Setting up data directory.
dir = './data'
raster_files = glob.glob(dir + '/*tif')

#Define some control variables.
row = 11
col = 9

def mean_filter(ma, mask):
    pct_array = np.zeros(ma.shape)
    win_area = float(mask.sum())
    row_dim = mask.shape[0]//2
    col_dim = mask.shape[1]//2
    for row in range(row_dim,ma.shape[0]-row_dim):
        for col in range(col_dim,ma.shape[1]-col_dim):
            win = ma[row-row_dim:row+row_dim+1,col-col_dim:col+col_dim+1]
            pct_array[row,col] = win.sum()
    return pct_array/win_area

#Defining and reprojecting the rasters.
def raster_reproject(raster_file):
    srcRst = raster_file
    
    dstCrs = 'ESRI:102028'
    
    print(dstCrs)
    transform, width, height = calculate_default_transform(
        srcRst.crs, dstCrs, srcRst.width, srcRst.height, *srcRst.bounds)
    kwargs = srcRst.meta.copy()
    kwargs.update({
        'crs':dstCrs,
        'transform': transform,
        'width': width,
        'height': height
    })
    
    destination = np.zeros((1765, 1121), np.uint8)
    
    for i in range(1, srcRst.count + 1):
        reproject(
            source = rasterio.band(srcRst, i),
            destination = destination,
            src_crs = srcRst.crs,
            dst_crs = dstCrs,
            resampling = Resampling.nearest)
        return destination
# Store the reprojected raster into a dictionary to be accessed later by name.
rlist = {}

for r in glob.glob(f"{dir}/*.tif"):
    file=os.path.basename(r)[:-4]
    with rasterio.open(r) as raster_obj:
        if raster_obj.crs!= 'ESRI: 102028':
            reprojeted_ras = raster_reproject(raster_obj)
            rlist[file]=reprojeted_ras
        else:
            data = raster_obj.read(1)
            meta = raster_obj.meta
            rlist[file] = data
#Organizing raster data.
rlist["slope"] = np.where(rlist["slope"] < 0, 0, rlist["slope"])
rlist["ws80m"] = np.where(rlist["ws80m"] < 0, 0, rlist["ws80m"])

#Defining the mask that will be used as the moving window.
mask = np.ones((row, col))

#Suitability Analysis Code

#The site cannot contain urban areas.
urban_sites = mean_filter(rlist["urban_areas"], mask)
urban_sites = np.where(urban_sites == 0 , 1, 0)
                      
#Less than 2% of land can be covered by water bodies.
water_sites = mean_filter(rlist["water_bodies"], mask)
water_sites = np.where(water_sites < 0.02, 1, 0)

#Less than 5% of the site can be within protected areas.
protected_sites = mean_filter(rlist["protected_areas"], mask)
protected_sites = np.where(protected_sites < 0.05, 1, 0)

#An average slope of less than 15 degrees is necessary  for the development plans.
slope_sites = mean_filter(rlist["slope"], mask)
slope_sites = np.where(slope_sites < 15, 1, 0)

# The average wind speed must be greater thatn 8.5m/s.
wind_sites = mean_filter(rlist["ws80m"], mask)
wind_sites = np.where(wind_sites > 8.5, 1, 0)

#Calculating the sites.
site_sum = protected_sites + slope_sites + urban_sites + water_sites + wind_sites

#Reclssify raster and print statement stating number of possible sites.
suit_array = np.where(site_sum == 5, 1, np.nan)
print('suitable sites:' ,np.sum(site_sum == 5))

# Save suitable raster
meta.update({'dtype': 'int16', 'nodata': 0})
with rasterio.open(os.path.join(FILE_DIR, 'suitables_sites.tif'), 'w', **meta) as dest:
            dest.write(suit_arr.astype('int16'), indexes=1)