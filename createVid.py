#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Fabio Vivian (fabio.vivian@esa.int), based on the work of Antonio Cuomo
# Simple Bot to reply to Telegram location sharing with related Earth Observation images
# This program is made available  under the CC BY 2.0 license.
"""

First, a few handler functions are defined. Then, those functions are passed to
the Dispatcher and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.

"""

import requests
import cv2
import pickle
import logging
import numpy as np
import time
import json
from pyproj import Proj, transform
import io
from PIL import Image
import os

userOld = None
timeOld = None

# load tokens/IDs:
with open('configFips.cfg') as f:
    tokens = json.loads(f.read())

logformat = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(format=logformat,
                    filename=f'vidScript.log',
                    level=logging.INFO)

logger = logging.getLogger(__name__)
logger.info(f'Starting the bot ...')

def sendVid(fileID, dictIn):
    
    sat  = dictIn['sat']
    lon, lat = dictIn['location']

    try:
        vidDataRaw = getVidData(sat, lon, lat, fileID)
    except Exception as e:
        logger.info(f'Could not get Video Data getVidData(sat, lon, lat, fileID). Exception: {e}.')
        return

    # invert data to BGR for openCV
    vidDataList = []
    for i in range(len(vidDataRaw)):
        vidDataList.append(vidDataRaw[i][1][:,:,::-1])
    vidData = np.array(vidDataList)

    fourcc = cv2.VideoWriter_fourcc(*'H264')
    #fourcc = cv2.VideoWriter_fourcc(*'DIVX')
    video = None
    fps = 25
    filename = f'out/{fileID}.mp4' # XVID / avi works on phone

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontSize = 0.3
    color = (255,255,255)
    thickness = 1
    linetype = 0
    
    i=0
    starting = True
    prev_frame = np.uint8([250])
    
    video = cv2.VideoWriter(filename, fourcc, fps, (480,320))
    if not video:
        import sys
        sys.exit(1)
    logger.info('entering video creation loop')
    while(True):

        frame = vidData[i]
        
        #cv2.rectangle(vidData[i],(10,20),(150,40),(255,255,255),60)
        cv2.rectangle(vidData[i], (0,0),(80,50),(1,1,1),
                      thickness=-1, lineType=8, shift=0)
        # putText(image as array, text as string, position in the image, ..., ..., color as bgr?, ., .)
        cv2.putText(frame, vidDataRaw[i][0]      ,(10,15), font, fontSize, color, thickness, linetype)
        cv2.putText(frame, f'lon: {"%.2f" % lon}',(10,30), font, fontSize, color, thickness, linetype)
        cv2.putText(frame, f'lat: {"%.2f" % lat}',(10,45), font, fontSize, color, thickness, linetype)
          
        if starting==True:
            prev_frame = frame
            starting = False
            for m in range(int(round(fps/2.))):
                video.write(frame)
        else:
            for l in range(1,20):
                weight = (20-l)/20
                #get the blended frames in between
                mid_frame = cv2.addWeighted(prev_frame,weight,frame,1-weight,0)
                video.write(mid_frame)

            for m in range(int(round(fps/2.))):
                # add half a second, filled with unprocessed scenes between the blended frames
                video.write(frame)
            prev_frame = frame
        i += 1
        if i == len(vidData):
            break


    video.release()
    try:
        os.rename(filename, f'out/{fileID}DONE.mp4')
        logger.info(f'timelapse video saved as out/{fileID}DONE.mp4')
    except Exception as e:
        logger.info(f'could not save file {fileID} because of the error: {e}')
    
    return
    
def getVidInfo(sat, lon, lat, fileID, page=1):
        
        
    params_eocurl = {'dataset': 'ESA-DATASET',
                     'lat': f'{lat}',
                     'lon': f'{lon}',
                     'maxRecords': 100,
                     'sortOrder': 'descending',
                     'sortParam': 'startDate'}
    if sat == 'S1':
        satellite = 'Sentinel1'
        params_eocurl['productType'] = 'GRD'
        params_eocurl['processingLevel'] = 'LEVEL1'
        satTimeout = 10
    if sat == 'S2':
        satellite = 'Sentinel2'
        params_eocurl['cloudCover'] = '[0,10]'
        satTimeout = 10
    elif sat == 'S3':
        satellite = 'Sentinel3'
        params_eocurl['processingLevel'] = 'LEVEL1'
        params_eocurl['maxRecords'] = 20
        params_eocurl['page'] = page
        satTimeout = 40
    
    EOCURL = f'https://finder.eocloud.eu/resto/api/collections/{satellite}/search.json?'
    
    try:
        r1 = requests.get(EOCURL, params_eocurl, timeout=satTimeout)
        logger.info(f'Finder responds in {r1.elapsed.total_seconds()} seconds to {r1.url}.')
    except requests.exceptions.RequestException as e:
        logger.info(f'Finder did not respond in time {satTimeout}, {e}')
        os.rename(f'in/{fileID}', f'in/{fileID}TIMEDOUT')
        raise requests.exceptions.RequestException('Finder timeout for getVidInfo')
    except Exception as e:
        logger.info(f'Exception in getVidInfo({sat}, {lon}, {lat}, {fileID}): {e}')
        raise

    js = json.loads(r1.content)
    products = []
    day_old = None
    
    try:
        for j in js['features']:
            day = j['properties']['startDate'].split('T')[0]
            if day_old != day:
                products.append((day, j))
            day_old = day
        return(list(reversed(products)))
    except Exception as e:
        logger.info(f'Could not get the dates from the EO Cloud. {e}')
        raise


def getVidData(sat, lon, lat, fileID):
    
    vidDates = getVidInfo(sat, lon, lat, fileID)
    if vidDates is None:
        raise TypeError('getVidInfo returned None')
    
    params = {'service': 'WMS',
              'request': 'GetMap',
              'styles': '',
              'format': 'image/png',
              'version': '1.1.1',
              'showlogo': 'false',
              'height': 320,
              'width': 480,
              'srs': 'EPSG%3A3857'}
    
    if sat == 'S1':
        ID = tokens['wms_token']['sentinel1']
        URL= 'https://services.sentinel-hub.com/ogs/wms'+ID
        params['layers'] = 'S1-VV-ORTHORECTIFIED'
        reso = 60
        threshold = 5 # in percent, 100% means every image will be used.
    if sat == 'S2':
        ID = tokens['wms_token']['sentinel2']
        URL = 'https://services.sentinel-hub.com/ogc/wms/'+ID
        params['layers'] = 'S2-TRUE-COLOR'
        reso = 60
        threshold = 5 # in percent, 100% means every image will be used.
    elif sat == 'S3':
        ID = tokens['wms_token']['sentinel3']
        URL = 'http://services.eocloud.sentinel-hub.com/v1/wms/'+ID
        params['layers'] = 'S3_TRUE_COLOR'
        threshold = 75 # in percent, 100% means every image will be used.
        reso = 1000
        
    inProj = Proj(init='epsg:4326')
    outProj = Proj(init='epsg:3857')
    xC,yC = transform(inProj,outProj, lon, lat)
    xmin = xC - 480*reso/2
    xmax = xC + 480*reso/2
    ymin = yC - 320*reso/2
    ymax = yC + 320*reso/2

    params['bbox'] = str(xmin)+', '+str(ymin)+', '+str(xmax)+', '+str(ymax)
    
    res = []
    maxWhitePix = 480 * 320 * threshold/100
    l=2
    while l<12:
        for i, (day, j) in enumerate(vidDates):
            try:
                r = requests.get(URL, {**params, **{'time': f'{day}/{day}'}}, timeout=10)
                imgTiff =  np.array(Image.open(io.BytesIO(r.content)))
                if imgTiff[(imgTiff >= 240).all(axis=2)].shape[0] <= maxWhitePix:
                    res.append((day, imgTiff))
            except Exception as e:
                logger.info(f'Exception in download loop (requests to sentinel-hub), Exception: {e}')
            if len(res) >= 10:
                logger.info(f'Download loop, all data downloaded.')
                return(res)
        if len(res) < 10:
            logger.info(f'not enough usable data on page {l-1}')
            vidDates = getVidInfo(sat, lon , lat, fileID, page=l)
            l += 1
        else:
            logger.info(f'not enough usable data on first 10 pages. Aborting download.')
            return
    print(res)

    logger.info(f'Downloaded data for {len(res)} dates.')
    return(res)
    
    '''output is a list with the following structure:
    [('2018-02-20', array([[[255, 255, 255],
        [255, 255, 255],
        ...,]]]))
    [('2018-02-15', array([[[255, 255, 255],
        [255, 255, 255],
        [255, 255, 255],
        ...,]]]))
    
    res[0][1] gives acces to the img data for the first date.
    res[0][0] gives acces to the first date.'''

while True:
    
    # find oldest file (= oldest request)
    inDir = 'in/'
    if os.listdir(inDir) != []:
        try:
            fileID = min(os.listdir(inDir), key=lambda f: os.path.getctime(f'{inDir}/{f}'))
        except Exception as e:
            logger.info(f'Could not access oldest file: {e}')
            fileID = None
    
    # open file from the /in directory
    # try, since there might not be any file to begin with
    if os.listdir(inDir) != []:
        try:
            with open(f'in/{fileID}', 'rb') as f:
                requestedDict = pickle.load(f)
        except Exception as e:
            logger.info(f'Failed to open the input file or assign dictionary. {e}')
            requestedDict = None
            
        
        if requestedDict == None:
            logger.info(f'empty dictionary.')
        elif requestedDict['user_id'] == userOld and requestedDict['last_visit'] == timeOld:
            logger.info(f'Waiting for a new request.')
        else:
            logger.info(f'Timelapse request from {requestedDict["user_id"]} at {requestedDict["last_visit"]} for {requestedDict["sat"]} at {requestedDict["location"]}.')
            start = time.time()
            sendVid(fileID, requestedDict)
            end = time.time()
            duration = end - start
            logger.info(f'elapsed time to create video: {duration}')
            
            userOld = requestedDict['user_id']
            timeOld = requestedDict['last_visit']
            
        
    time.sleep(5.0)

