# -*- coding: utf-8 -*-
"""
Created on Fri Apr 27 10:25:23 2018

@author: Administrator
"""

#import matplotlib as mlp
#mlp.use('Agg')
import requests
import numpy as np
from pyproj import Proj, transform
from PIL import Image
import io
import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap, cm
from time import time
startTot = time()

inProj = Proj(init='epsg:4326')
outProj = Proj(init='epsg:3857')
lon = 9.22
lat = 45.62
xC,yC = transform(inProj,outProj, lon, lat)
reso = 2e3
k = 1
width = 980*k
height= 540*k
xmin = xC - width*reso/2
xmax = xC + width*reso/2
ymin = yC - height*reso/2
ymax = yC + height*reso/2

ID = '2db0b567-5510-40c4-b060-dc8b0717251d'
URL = 'http://services.eocloud.sentinel-hub.com/v1/wms/'+ID
params = {'service': 'WMS',
              'request': 'GetMap',
              'layers': 'S5P_NO2',
              'styles': '',
              #'transparent': 'True',
              'format': 'image/tiff',
              'version': '1.1.1',
              'showlogo': 'false',
              'time': '2018-04-18',
              'height': height,
              'width': width,
              'srs': 'EPSG%3A3857'}
params['bbox'] = str(xmin)+', '+str(ymin)+', '+str(xmax)+', '+str(ymax)
print('ruequest sent, waiting for response')
r = requests.get(URL, {**params})
print(f'download time: {r.elapsed.total_seconds()}', r.url)
try:
    imgTiff =  np.array(Image.open(io.BytesIO(r.content)))
except Exception as e:
    print(e)
    import sys
    sys.exit()
    
print(imgTiff)

startPlot = time()

lonmin,latmin = transform(outProj,inProj, xmin, ymin)
lonmax,latmax = transform(outProj,inProj, xmax, ymax)
m = Basemap(projection='merc',
            llcrnrlat = latmin,
            urcrnrlat = latmax,
            llcrnrlon = lonmin,
            urcrnrlon = lonmax,
            resolution = 'i')
m.drawcoastlines()
m.drawcountries()
ny = imgTiff.shape[0]; nx = imgTiff.shape[1]
ma = np.ma.masked_values(imgTiff, 254, copy=False)
lons, lats = m.makegrid(nx, ny) # get lat/lons of ny by nx evenly space grid.
x, y = m(lons, lats) # compute map proj coordinates.
clevs = np.arange(ma.min(), ma.max(), 1)
print(clevs)
cs = m.contourf(x,y,np.flip(ma,0), cmap=cm.GMT_red2green)
cbar = m.colorbar(cs,location='bottom',pad="5%")
cbar = cbar.set_label(params['layers']+r' in $mol / m^2$')
#plt.savefig(f'{params["layers"]}.png')
endPlot = time()
endTot = time()
print(f'time used to generate the plot: {endPlot - startPlot}')
print(f'total time: {endTot - startTot}')