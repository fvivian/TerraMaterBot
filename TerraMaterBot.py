# -*- coding: utf-8 -*-
"""
Created on Thu Apr 19 10:11:51 2018

@author: Administrator
"""

import numpy as np
import json
import logging
import os
import pickle
from pyproj import Proj, transform
import matplotlib
matplotlib.use('Agg')
from mpl_toolkits.basemap import Basemap, cm
import matplotlib.pyplot as plt
from PIL import Image
import io
import socket
import sys
import threading
import datetime
import time
import requests
import uuid
import telegram as tl
from telegram.ext import CommandHandler, ConversationHandler,\
                         Filters, MessageHandler, RegexHandler, Updater
from telegram.ext.dispatcher import run_async
from rasterio.io import MemoryFile

from geopy.geocoders import Nominatim
import certifi
import ssl
import geopy.geocoders


ctx = ssl.create_default_context(cafile=certifi.where())
geopy.geocoders.options.default_ssl_context = ctx
hostname, DATA = socket.gethostname(), os.getcwd()
geolocator = Nominatim(user_agent='myApp')
CONVERSATION, = range(1)

# import all the necessary tokens/IDs:
with open('configFips.cfg') as f:
    tokens = json.loads(f.read())


# Enable logging
logformat = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(format=logformat,
                    filename=f'logTerraMater.log',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

#subprocess.call('python createVid.py')

entry_keyboard = [['/S1', '/S2', '/S3', '/S5P'],
                  [tl.KeyboardButton('location', request_location=True), '/timelapse', '/help']]
entry_markup = tl.ReplyKeyboardMarkup(entry_keyboard)

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
        #date = datetime.date.today() - datetime.timedelta(1)
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


# Define a few command handlers. These usually take the two arguments bot and
# update. Error handlers also receive the raised TelegramError object in error.


def start(bot, update, user_data):
    '''Send a message when the command /start is issued.'''
    user = update.message.from_user
    logger.info(f'Starting conversation with {user.id}')
    update.message.reply_text('Salve, I am Terra Mater, ancient roman goddess of the Earth. '
				'I can show you Sentinel images from all over the globe if you just send your location '
				'or a location of your interest. For that purpose, tap on the button on the bottom or '
				'use the Attachment menu. If you want to change the source of the image tap on '
				'one of the buttons below. '
				'For further instructions please use /help.', reply_markup=entry_markup)
    return CONVERSATION


def help(bot, update):
    '''Send a message when the command /help is issued.'''
    update.message.reply_text('I accept the following entries:\n'
				'/S1: request a Sentinel-1 GRD IW image from your chosen location.\n'
				'/S2: request a Sentinel-2 MSI image from your chosen location.\n'
				'/S3: request a Sentinel-3 OLCI image from your chosen location.\n'
				'/S5P: request a Sentinel-5P image from your chosen location.\n\n'
                                '/timelapse: request an animated GIF of a time lapse for Sentinel-2 or -3.\n'
				'/help: display this message.\n'
				'/start: display the initial welcoming message.\n\n'
				'You can send me your current location by pressing the location button below or you can send me any location '
				'you like by choosing "Location" in the attachment menu. '
				'Additionly, you can send names of cities, places, streets or similar. You can even try voice input.\n'
				'To switch between normal keyboard and buttons, tap on the keyboard icon next to the entry field.', reply_markup=entry_markup)

    return CONVERSATION


def logaction(request, bot, update, user_data):
    msg = update.message
    user = msg.from_user
    if 'location' in user_data:
        logger.info(f'{user.id} requests {request} at {user_data["location"]}')
    else:
        logger.info(f'{user.id} requests {request} but has no location')

@run_async
def request_image(satellite, bot, update, user_data):
    user_data['last_visit'] = datetime.datetime.now()
    if 'location' in user_data:
        lon, lat = user_data['location']
    else:
        logger.info(f'{update.message.from_user.id} has no location')
        update.message.reply_text('Please send me a location first.')
        return

    result = get_current_image(satellite, lon, lat)

    if result is not None:
        date, preview, url = result
        cf = ('cloudfree ' if satellite is 'S2' else '')
        reply = f'The latest {satellite} {cf}image was acquired on {date}'
        update.message.reply_text(reply)
        if preview is not None:
            try:
                update.message.reply_photo(photo=f'{preview}')
            except Exception as e:
                update.message.reply_text('No good preview is available. I\'ll see to this being fixed.')
                logger.error(f'Preview not valid: {preview}. Exception: {e}.')
        else:
            update.message.reply_text('Unfortunately, there is no preview.')
            
        update.message.reply_text(text=f'Browse it here in <a href="{url}">EO Browser</a>.',
                                  parse_mode=tl.ParseMode.HTML,
                                  disable_web_page_preview=True)
    else:
        update.message.reply_text('Unfortunately, there is no answer from the server, '
                                  'the system might be busy.')
    
    
def s1(bot, update, user_data):
    user_data['sat'] = 'S1'
    logaction('S1', bot, update, user_data)
    request_image('S1', bot, update, user_data)
    return CONVERSATION


def s2(bot, update, user_data):
    user_data['sat'] = 'S2'
    logaction('S2', bot, update, user_data)
    request_image('S2', bot, update, user_data)
    return CONVERSATION


def s3(bot, update, user_data):
    user_data['sat'] = 'S3'
    logaction('S3', bot, update, user_data)
    update.message.reply_text('Sentinel 3 OCLI image was requested and might take a few seconds to be sent to you.')
    request_image('S3', bot, update, user_data)
    return CONVERSATION


def s5p(bot, update, user_data):
    user_data['sat'] = 'S5P'
    logaction('S5P', bot, update, user_data)
    entry_keyboard = [['/CO', '/NO2']]
    rep_markup = tl.ReplyKeyboardMarkup(entry_keyboard) 
    update.message.reply_text('Please choose a trace gas.', reply_markup=rep_markup)
    return CONVERSATION

def NO2(bot, update, user_data):
    user_data['trace_gas'] = 'NO2'
    update.message.reply_text('Thank you. Creating the Sentinel-5P NO2 image might take a few seconds.', reply_markup=entry_markup)
    request_S5Pimage(bot, update, user_data)
    return CONVERSATION

def CO(bot, update, user_data):
    user_data['trace_gas'] = 'CO'
    update.message.reply_text('Thank you. Creating the Sentinel-5P CO image might take a few seconds.', reply_markup=entry_markup)
    request_S5Pimage(bot, update, user_data)
    return CONVERSATION

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
    xC,yC = transform(inProj,outProj, lon, lat)
    reso = 2e3
    k = 1
    width = 980*k
    height= 540*k
    xmin = xC - width*reso/2
    xmax = xC + width*reso/2
    ymin = yC - height*reso/2
    ymax = yC + height*reso/2
    print(user_data)
    ID = tokens['wms_token']['sentinel5p']
    URL = 'http://services.eocloud.sentinel-hub.com/v1/wms/'+ID
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
              'bbox': str(xmin)+', '+str(ymin)+', '+str(xmax)+', '+str(ymax)}
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
    ma1 = np.ma.masked_values(imgTiff, 0, copy=False)
    ma = np.ma.masked_where(ma1 < 0 , ma1, copy=False)
    lons, lats = m.makegrid(nx, ny) # get lat/lons of ny by nx evenly space grid.
    x, y = m(lons, lats) # compute map proj coordinates.
    cs = m.contourf(x,y,np.flip(ma,0), cmap=plt.cm.jet)
    cbar = m.colorbar(cs,location='bottom',pad="5%")
    cbar.set_label(params['layers']+r' in $mol / cm^2$ '+f'at lon = {"%.1f" % lon}, lat = {"%.1f" % lat}')
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
    return CONVERSATION

def gif(bot, update, user_data, job_queue):
    user_id = update.message.from_user.id
    user_data['last_visit'] = datetime.datetime.now()
    user_data['user_id'] = user_id   
    
    
    if 'location' in user_data:
        lon, lat = user_data['location']
        logger.info(f'{user_id} requested GIF for {lon}, {lat}.')
    else:
        logger.info(f'{user_id} has no location')
        update.message.reply_text('Please send me a location first.')
        return
    
    if 'sat' not in user_data:
        logger.info(f'{user_id} requested GIF but has not chosen a satellite.')
        update.message.reply_text('You have not chosen a satellite yet. '
                                  'Please choose between Sentinel-2 and Sentinel-3.')
        return
    
    elif user_data['sat'] == 'S1' or user_data['sat'] == 'S5P':
        logger.info(f'{user_id} requested GIF but has S1 or S5P as chosen satellite.')
        update.message.reply_text(f'You have chosen {user_data["sat"]} which is not supported yet. '
                                  'Please choose between Sentinel-2 and Sentinel-3.')
        return
    
    cf = ('cloudfree ' if user_data['sat'] is 'S2' else '')
    update.message.reply_text(f'You requested a {user_data["sat"]} time lapse video. '
                              'Creating the file might take a few minutes. '
                              f'The animation will include the latest ten {cf}images. '
                              'You can send image requests in the meantime.')
    #request_gif(bot, update, user_data)
    filename = uuid.uuid4()
    with open(f'in/{filename}', 'wb+') as f:
        pickle.dump(user_data, f)

    job_queue.run_repeating(check_for_animation, interval=11.0, first=0, context=filename)
    return CONVERSATION
    
def check_for_animation(bot, job):

    if os.path.isfile(f'in/{job.context}TIMEDOUT'):
        job.schedule_removal()
        with open(f'in/{job.context}TIMEDOUT', 'rb') as f:
            user_data = pickle.load(f) 
        bot.send_message(chat_id=user_data['user_id'], text='I\'m sorry I could not create a time lapse video. The server did not respond in time.')
        logger.info(f'{job.context} was removed due to a time out.')
        os.remove(f'in/{job.context}TIMEDOUT')
        return CONVERSATION
    elif os.path.isfile(f'in/{job.context}EMPTY'):
        job.schedule_removal()
        with open(f'in/{job.context}EMPTY', 'rb') as f:
            user_data = pickle.load(f) 
        bot.send_message(chat_id=user_data['user_id'], text='I\'m sorry I could not create a time lapse video. There are not enough images that meet the requirements.')
        logger.info(f'{job.context} was removed due to too few usable images.')
        os.remove(f'in/{job.context}EMPTY')
        return CONVERSATION
    else:
        with open(f'in/{job.context}', 'rb') as f:
            user_data = pickle.load(f)

    try:
        with open(f'out/{job.context}DONE.mp4', 'rb') as f:
            bot.send_video(chat_id=user_data['user_id'], video=f)
        job.schedule_removal()
        os.remove(f'out/{job.context}DONE.mp4')
        os.remove(f'in/{job.context}')
        logger.info(f'Timelapse for {user_data["user_id"]} at {user_data["last_visit"]} was sent and then removed.')
        sent = True
    except Exception as e:
        last_error = e
        job.interval -= 0.05
        sent = False
        
    if job.interval <= 10. and sent == False:
            job.schedule_removal()
            bot.send_message(chat_id=user_data['user_id'], text='I\'m sorry I could not create a time lapse video.')
            logger.info(f'Could not send video: {last_error}.')
            os.remove(f'in/{job.context}')
    
    return CONVERSATION

def location(bot, update, user_data):
    msg = update.message
    user = msg.from_user
    ulon, ulat = msg.location.longitude, msg.location.latitude
    user_data['location'] = (ulon, ulat)  # new
    logger.info(f'Location of {user.id}: {ulon}, {ulat}')
    msg.reply_text(f'Very good! Now select a satellite to get an image!')
    return CONVERSATION

@run_async
def get_and_respond_to_location(bot, update, user_data):
    user = update.message.from_user
    user_data['last_visit'] = datetime.datetime.now()
    try:
        location = geolocator.geocode(update.message.text)
    except Exception as e:
        logger.info(f'Geolocator returned an error for {update.message.text}')
        logger.error(e)
        location = None
    if location is not None:
        logger.info(location)
        ulat, ulon = location[1]
        logger.info(f'{user.id} is at ({ulon}, {ulat})')
        user_data['location'] = (ulon, ulat)
        update.message.reply_text(f'I believe this is at lon: {"%.1f" % ulon}, lat: {"%.1f" % ulat}.',
                                  reply_markup=entry_markup)
        bot.sendLocation(chat_id=update.message.chat.id, latitude=ulat, longitude=ulon)
        update.message.reply_text(f'If this is the location you were looking for, get an image by using one of the buttons below. '
				   'If this is not what you were looking for, re-send a location name or your location by using the button below.')
    else:
        update.message.reply_text('I can\'t find out where this is. Try again or send '
                                  'a location via the location button or the attachment menu.',
                                  reply_markup=entry_markup)
    return CONVERSATION 

def echo(bot, update, user_data):
    '''Echo the user message.'''
    msg = update.message
    user = msg.from_user
    logger.info(f'{user.id} sends {update.message.text}')
    if update.message.text != 'CO' and update.message.text != 'NO2':
        get_and_respond_to_location(bot, update, user_data)

def error(bot, update, error):
    '''Log Errors caused by Updates.'''
    logger.warning(f'Update "{update}" caused error "{error}"')


def main():

    def load_state():
        try:
            with open(f'{DATA}/backup/conversationsV4', 'rb') as f:
                conv_handler.conversations = pickle.load(f)
            with open(f'{DATA}/backup/userdataV4', 'rb') as f:
                dp.user_data = pickle.load(f)
        except FileNotFoundError:
            logger.error('Data file(s) for restoring state not found')
        except Exception as e:
            logger.error(f'Unexpeted error: {e}')
        logger.info(f'Restoring conversations: {conv_handler.conversations}')
        logger.info(f'Restoring user data: {dp.user_data}')

    def save_state():
        backupWait = 0
        while True:
            time.sleep(60)
            backupWait += 1
            #logger.info(f'Conv State to save is {conv_handler.conversations}')
            #logger.info(f'User State to save is {dp.user_data}')
            # Before pickling
            resolved = conv_handler.conversations.copy()
            try:
                with open(f'{DATA}/backup/conversationsV4', 'wb+') as f:
                    pickle.dump(resolved, f)
                with open(f'{DATA}/backup/userdataV4', 'wb+') as f:
                    pickle.dump(dp.user_data, f)
            except Exception as e:
                logger.error(f'Could not save state: {e}')
                logger.error(f'Conversations: {conv_handler.conversations}')
                logger.error(sys.exc_info()[0])
            if backupWait == 1440: # for backing up userdata every 24 hours (1 step/min * 60 min/h * 24 h/day)
                backuptime = datetime.datetime.today().isoformat()[:-7].replace(':', '')
                f = open(f'{DATA}/backup/userdataV3{backuptime}', 'wb+')
                pickle.dump(dp.user_data, f)
                f.close()
                backupWait = 0
                

    # Start the bot.
    logger.info(f'Starting the bot ... on {hostname}')

    # Create the EventHandler and pass it your bot's token.
    updater = Updater(tokens['bot_token'])
    #job = updater.job_queue

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    entries = [CommandHandler('start', start, pass_user_data=True)]

    commands = [
        CommandHandler('start', start, pass_user_data=True),
        CommandHandler('s1', s1, pass_user_data=True),
        CommandHandler('s2', s2, pass_user_data=True),
        CommandHandler('s3', s3, pass_user_data=True),
        CommandHandler('s5p', s5p, pass_user_data=True),
        CommandHandler('timelapse', gif, pass_user_data=True, pass_job_queue=True),
        CommandHandler('NO2', NO2, pass_user_data=True),
        CommandHandler('CO', CO, pass_user_data=True),
        MessageHandler(Filters.location, location, pass_user_data=True),
        MessageHandler(Filters.text, echo, pass_user_data=True)]

    conv_handler = ConversationHandler(
        entry_points=(entries + commands),
        states={
            CONVERSATION: commands
        },
        fallbacks=[MessageHandler(Filters.text, echo),
                   RegexHandler('^(.*)', help),
                   CommandHandler('help', help)]
    )
    dp.add_handler(conv_handler)

    load_state()  # restore state
    dp.add_error_handler(error)  # log all errors
    threading.Thread(target=save_state).start()  # save state periodically
    updater.start_polling()  # start the Bot
    # Run until Ctrl-C, SIGINT, SIGTERM or SIGABRT is received.
    updater.idle()


if __name__ == '__main__':
    main()
