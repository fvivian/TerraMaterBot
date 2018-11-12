

import numpy as np
from pyproj import Proj, transform
import io
import json
import requests
from urllib.parse import urlencode
import logging

logger = logging.getLogger(__name__)

# import all the necessary tokens/IDs:
with open('configFips.cfg') as f:
    tokens = json.loads(f.read())


def get_bounding_box(lon, lat, reso):
    inProj = Proj(init='epsg:4326')
    outProj = Proj(init='epsg:3857')

    xC, yC = transform(inProj, outProj, lon, lat)
    width = 980
    height = 540
    xmin = xC - width * reso / 2
    xmax = xC + width * reso / 2
    ymin = yC - height * reso / 2
    ymax = yC + height * reso / 2

    return(xmin, ymin, xmax, ymax)

def create_wms_image_url(sat, lon, lat, gas=None):
    xmin, ymin, xmax, ymax = get_bounding_box(lon, lat, reso=60)

    params = {'service': 'WMS',
              'request': 'GetMap',
              'layers': '',
              'styles': '',
              'format': 'image/jpeg',
              'version': '1.1.1',
              'showlogo': 'false',
              'height': 720,
              'width': 1280,
              'srs': 'EPSG%3A3857',
              'bbox': f'{xmin}, {ymin}, {xmax}, {ymax}'}
    if sat == 'S1':
        ID = tokens['wms_token']['sentinel1']
        URL = 'http://services.sentinel-hub.com/ogc/wms/' + ID
        params['layers'] = 'S1-VV-ORTHORECTIFIED'
    if sat == 'S2':
        ID = tokens['wms_token']['sentinel2']
        URL = 'http://services.sentinel-hub.com/ogc/wms/' + ID
        params['layers'] = 'S2-TRUE-COLOR'
        params['maxcc'] = 0
    if sat == 'S3':
        ID = tokens['wms_token']['sentinel3']
        URL = 'http://services.eocloud.sentinel-hub.com/v1/wms/' + ID
        params['layers'] = 'S3_TRUE_COLOR'
        xmin, ymin, xmax, ymax = get_bounding_box(lon, lat, reso=2e3)
        params['bbox'] = f'{xmin}, {ymin}, {xmax}, {ymax}'
    if sat == 'S5P':
        ID = tokens['wms_token']['sentinel5p']
        URL = 'http://services.eocloud.sentinel-hub.com/v1/wms/'+ ID
        params['layers'] = f'S5P_{gas}'
        params['format'] = 'image/tiff'
        xmin, ymin, xmax, ymax = get_bounding_box(lon, lat, reso=2e3)
        params['bbox'] = f'{xmin}, {ymin}, {xmax}, {ymax}'
        
    url = f'{URL}?{urlencode(params)}'
    
    return(url)

def create_parameters_wfs(sat, lon, lat, gas=None):
    xmin, ymin, xmax, ymax = get_bounding_box(lon, lat, reso=60)

    params = {'service': 'WFS',
              'request': 'GetFeature',
              'outputformat': 'application/json',
              'srs': 'EPSG%3A3857',
              'maxfeatures': '100',
              'bbox': f'{xmin}, {ymin}, {xmax}, {ymax}'}
    if sat == 'S1':
        ID = tokens['wms_token']['sentinel1']
        URL = 'http://services.sentinel-hub.com/ogc/wfs/' + ID
        params['typenames'] = 'S1.TILE'
    if sat == 'S2':
        ID = tokens['wms_token']['sentinel2']
        URL = 'http://services.sentinel-hub.com/ogc/wfs/' + ID
        params['typenames'] = 'S2.TILE'
        params['maxcc'] = 0
    if sat == 'S3':
        ID = tokens['wms_token']['sentinel3']
        URL = 'http://services.eocloud.sentinel-hub.com/v1/wfs/' + ID
        params['typenames'] = 'S3.TILE'
        xmin, ymin, xmax, ymax = get_bounding_box(lon, lat, reso=2e3)
        params['bbox'] = f'{xmin}, {ymin}, {xmax}, {ymax}'
    if sat == 'S5P':
        ID = tokens['wms_token']['sentinel5p']
        URL = 'http://services.eocloud.sentinel-hub.com/v1/wfs/' + ID
        params['typenames'] = f'S5P_{gas}'
        xmin, ymin, xmax, ymax = get_bounding_box(lon, lat, reso=2e3)
        params['bbox'] = f'{xmin}, {ymin}, {xmax}, {ymax}'
    return(URL, params)

def get_image_dates(sat, lon, lat, gas=None):
    URL, params = create_parameters_wfs(sat, lon, lat)

    try:
        r = requests.get(URL, {**params}, timeout=10)
        js = json.loads(r.content)
        dates = []
        date_old = None
        for j in js['features']:
            if date_old != j['properties']['date']:
                dates.append(j['properties']['date'])
            date_old = j['properties']['date']
        return(dates)
    except requests.exceptions.RequestException as e:
        logger.exception(f'WMS server did not respond to GetFeatureInfo request in time.')
        raise requests.exceptions.RequestsException('WMS server timed out')
    except Exception as e:
        logger.exception(f'Exception in get_latest_image_date')
        logger.info(f'URL that caused exception: {r.url}')
        raise

