
import numpy as np

from pyproj import Proj, transform
import matplotlib

matplotlib.use('Agg')
from mpl_toolkits.basemap import Basemap
import matplotlib.pyplot as plt
#from PIL import Image
import io

import requests
from rasterio.io import MemoryFile


def generate_browser_url(sat, date, lon, lat, no2=False):
    if sat == 'S1':
        instrument = 'Sentinel-1%20GRD%20IW'
        layer = '1_VV_ORTHORECTIFIED'
    elif sat == 'S2':
        instrument = 'Sentinel-2%20L1C'
        layer = '1_TRUE_COLOR'
    elif sat == 'S3':
        instrument = 'Sentinel-3%20OLCI'
        layer = '1_TRUE_COLOR'
    elif sat == 'S5P':
        instrument = 'Sentinel-5P%20NO2' if no2 else 'Sentinel-5P%20CO'
        layer = 'NO2_VISUALIZED' if no2 else 'CO_VISUALIZED'
        date = ''

    url = f'http://apps.sentinel-hub.com/eo-browser/#lat={lat}&'\
          f'lng={lon}&zoom=10&datasource={instrument}&'\
          f'time={date}&preset={layer}'

    return url


def get_current_image(sat, lon, lat):

    sats = {'S1': 'Sentinel1',
            'S2': 'Sentinel2',
            'S3': 'Sentinel3',
            'S5P': 'Sentinel5P'}

    coll = sats.get(sat, 'Sentinel2')

    url = f'https://finder.eocloud.eu/resto/api/collections/{coll}/search.json'

    params = {'dataset': 'ESA-DATASET',
              'maxRecords': 10,
              'lon': f'{lon}',
              'lat': f'{lat}',
              'sortOrder': 'descending',
              'sortParam': 'startDate'}

    timeout = 10
    if sat == 'S1':
        params['processingLevel'] = 'LEVEL1'
        params['productType'] = 'GRD'
    elif sat == 'S2':
        params['cloudCover'] = '[0,10]'
        params['processingLevel'] = 'LEVELL1C'
    elif sat == 'S3':
        params['processingLevel'] = 'LEVEL1'
        params['instrument'] = 'OL'
        params['productType'] = 'EFR'
        timeout=30
    elif sat == 'S5P':
        pass
    else:
        logger.info(f'Unknown satellite {sat}')

    try:
        res = requests.get(url, params, timeout=timeout)
        logger.info(f'Finder responds in {res.elapsed.total_seconds()} sec')
        jres = json.loads(res.content)
    except requests.exceptions.Timeout:
        logger.error(f'Request to Finder timed out.')
        return None
    except Exception as e:
        logger.error(f'Could not obtain result from Finder for {sat}, {lon}/{lat}; exception was {e}')
        return None

    if len(jres['features']) >= 1:
        j = jres['features'][0]
        path = j['properties']['productIdentifier']

        if sat == 'S1':
            preview = j['properties']['thumbnail']
        elif sat == 'S2':
            if j['properties']['thumbnail'] is not None:
                preview = j['properties']['thumbnail']
            else:
                title = j['properties']['title'][:-5]
                suffix = f'{title}/{title}-ql.jpg'
                url = f'https://finder.eocloud.eu/files/{path[8:]}/{suffix}'
                preview = url
                logger.info(f'Thumbnail: {j["properties"]["thumbnail"]}')
        elif sat == 'S3':
            preview = j['properties']['thumbnail']
        else:
            preview = None
        logger.info(f'Request to {res.url} returned the following: {preview}')
        date = j['properties']['startDate'].split('T')[0]
        return (date, preview, generate_browser_url(sat, date, lon, lat))
    else:
        logger.info(f'Request to {res.url} returned the following: {jres}')
        return None


def request_S5Pimage(bot, update, user_data):
    inProj = Proj(init='epsg:4326')
    outProj = Proj(init='epsg:3857')
    if 'location' in user_data:
        lon, lat = user_data['location']
    else:
        logger.info(f'{update.message.from_user.id} has no location')
        update.message.reply_text('Please send me a location first.')
        return
    trace_gas = user_data['trace_gas']
    xC, yC = transform(inProj, outProj, lon, lat)
    reso = 2e3
    k = 1
    width = 980 * k
    height = 540 * k
    xmin = xC - width * reso / 2
    xmax = xC + width * reso / 2
    ymin = yC - height * reso / 2
    ymax = yC + height * reso / 2
    print(user_data)
    ID = tokens['wms_token']['sentinel5p']
    URL = 'http://services.eocloud.sentinel-hub.com/v1/wms/' + ID
    params = {'service': 'WMS',
              'request': 'GetMap',
              'layers': f'S5P_{trace_gas}',
              'styles': '',
              'format': 'image/tiff',
              'version': '1.1.1',
              'showlogo': 'false',
              'height': height,
              'width': width,
              'srs': 'EPSG%3A3857',
              'bbox': str(xmin) + ', ' + str(ymin) + ', ' + str(xmax) + ', ' + str(ymax)}
    try:
        r = requests.get(URL, {**params}, timeout=10)
        with MemoryFile(r.content) as memfile:
            with memfile.open() as dataset:
                imgData = dataset.read(1)
                imgTiff = imgData * 1e4
                logger.info('s5p image opened')
    except requests.exceptions.Timeout:
        logger.info(f'Request to the S5P WMS server timed out.')
        updater.message.reply_text('Unfortunately, there is no answer from the server, the system might be busy.')
        return
    except Exception as e:
        logger.info(f'Could not retrieve or open S5P data, Exception: {e}. {r.url}')
        updater.message.reply_text('There is no image available at the moment, I\'ll see to this being fixed.')
        return

    photo = io.BytesIO()
    photo.name = 'image.png'
    lonmin, latmin = transform(outProj, inProj, xmin, ymin)
    lonmax, latmax = transform(outProj, inProj, xmax, ymax)
    m = Basemap(projection='merc',
                llcrnrlat=latmin,
                urcrnrlat=latmax,
                llcrnrlon=lonmin,
                urcrnrlon=lonmax,
                resolution='i')
    m.drawcoastlines()
    m.drawcountries()
    ny = imgTiff.shape[0];
    nx = imgTiff.shape[1]
    ma1 = np.ma.masked_values(imgTiff, 0, copy=False)
    ma = np.ma.masked_where(ma1 < 0, ma1, copy=False)
    lons, lats = m.makegrid(nx, ny)  # get lat/lons of ny by nx evenly space grid.
    x, y = m(lons, lats)  # compute map proj coordinates.
    cs = m.contourf(x, y, np.flip(ma, 0), cmap=plt.cm.jet)
    cbar = m.colorbar(cs, location='bottom', pad="5%")
    cbar.set_label(params['layers'] + r' in $mol / cm^2$ ' + f'at lon = {"%.1f" % lon}, lat = {"%.1f" % lat}')
    plt.savefig(photo)
    photo.seek(0)
    update.message.reply_photo(photo=photo, reply_markup=entry_markup)
    logger.info(f's5p image sent to {user_data["user_id"]}.')
    plt.clf()
    no2 = True if trace_gas == 'NO2' else False
    eobrowser = generate_browser_url('S5P', None, lon, lat, no2=no2)
    update.message.reply_text(text=f'Browse it here in <a href="{eobrowser}">EO Browser</a>.',
                              parse_mode=tl.ParseMode.HTML,
                              disable_web_page_preview=True)
