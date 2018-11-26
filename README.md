# Telegram Bot in Earth Observation

This bot allows the Telegram user to request an image from either Sentinel-1, Sentinel-2 or Sentinel-3 of his current location or any other location he chooses. Upon receiving the location data, the bot looks for the most recent imagery with the least possible cloud coverage and sends it to the user along with a link to Sinergise's EO Browser (https://apps.sentinel-hub.com/eo-browser/).

First, the user has to send /start to @TerraMaterBot in order to initialize the bot. It creates the user's chat ID along with other default settings. To receive an image, the user has to either send a command in the form of /s1, /s2, /s3, or /s5p or tap on the button on the custom keyboard. For further instructions, /help may be used.

![](https://github.com/fvivian/TerraMaterBot/blob/master/TerraMaterV4_img.PNG)

## Functionality

Each of the commands above makes the bot call a function on the backend. Each of the /Sx commands involves a GetFeature request to Sinergise’s web feature service (WFS) in order to find the latest acquisition date for a chosen location. For a WFS GetFeature request one needs several parameters, depending on the data’s source satellite. An exemplary url request might look something like this:
```
params = {'service': 'WFS',
          'request': 'GetFeature',
          'outputformat': 'application/json',
          'srs': 'EPSG%3A3857',
          'maxfeatures': '100',
          'typenames': 'S2.TILE',
          'maxcc': 5,
          'bbox': f'{xmin}, {ymin}, {xmax}, {ymax}'}
url_wfs = f'https://services.sentinel-hub.com/ogc/wfs/{ID}'
res_wfs = requests.get(url_wfs, {**params})
```
The response  (res_wfs) of this simple HTTP get request will be a json with information about the location (bbox) and layer (typenames) containing information such as time, date, geometry, or product name.
The date will then be used for a GetMap WMS request with the following exemplary parameters:
```
params = {'service': 'WMS',
          'request': 'GetMap',
          'layers': 'S2-TRUE-COLOR',
          'srs': 'EPSG%3A3857',
          'format': 'image/jpeg',
          'version': '1.1.1',
          'showlogo': 'false',
          'height': 720,
          'width': 1280,
          'time': f'{date}/{date}',
          'maxcc': 5,
          'bbox': f'{xmin}, {ymin}, {xmax}, {ymax}'}
          
url_base = f'https://services.sentinel-hub.com/ogc/wms/{ID}'
url_wms = f'{url_base}?{urllib.parse.urlencode(params)}'
```
For performance reasons the url is not used for a get request since the the image would then be downloaded twice, once by the server running the backend and once by Telegram’s API. Fortunately, the Telegram Bot API offers a function to send an image to the user via url, i.e. the image is only downloaded once, by Telegram’s API.
The layers being used are predefined and for Sentinel-1 it is the VV-orthorectified, for Sentinel-2 and Sentinel-3 the True Color (bands 4, 3 and 2 for S2 and bands 8, 6 and 4 for S3, respectively) and for Sentinel-5P either NO2 or CO layer.

### Time lapse videos with Sentinel data
The scripts create_video.py and utils_vid.py are currently not in use. It would include using the openCV library to create a time lapse video of a chosen location/satellite. Unfortunately, openCV is i) in conflict with the mpl_toolkit Basemap and ii) not compatible with  Telegram's requirements of H.264 and MPEG-4 to be used as the codec and container. The codes are included in this repository for completeness reasons.

In order to run the script:
```
rm in/*
rm out/*
export PROJ_LIB=/home/eouser/anaconda3/envs/env_name/share/proj/

nohup /home/eouser/anaconda3/envs/env_name/bin/python3.6 TerraMaterBot.py &
nohup /home/eouser/anaconda3/envs/env_name/bin/python3.6 create_video.py &
```
When in use, the /timelapse button in Telegram creates a pickle dump file with user_data (i.e. lon/lat, satellite) in the in/ directory. The create_video.py (which is running constantly) checks every 5 seconds for a new dump file in in/. When there is a new task, it extracts the information from the dump file, requests information from the WFS (similar to above), uses the dates to download the 10 latest images from a WMS (similar to the above, but in a loop), creates the time lapse file with the openCV library and stores it in the out/ directory. Once the file has been sent back to the user, files in the in/ and out/ directories are removed.
