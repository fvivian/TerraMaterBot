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

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import logging
import uuid
import requests
import shutil
import os
import json

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


# Define a few command handlers. These usually take the two arguments bot and
# update. Error handlers also receive the raised TelegramError object in error.
def start(bot, update):
    '''upon starting the bot, each user gets its own dictionary, including chat id,
    chosen satellite etc.'''


    update.message.reply_text('Salve, I am Terra Mater, ancient roman goddess of the '
                              'Earth. I can show you images from all over the globe '
                              'if you just send your location or a location of your '
                              'interest. If you want to change the source of the image '
                              'use /sentinel1, /sentinel2, or /sentinel3 respectively. '
                              'To see your current setting, use /test. If you cannot '
                              'receive any answer to your location, try /start first.')


    global user

    userID = update.message.from_user['id']    
    params_eocurl = {'dataset': 'ESA-DATASET',
                      'maxRecords': 50,
                      'cloudCover': '[0,10]',
                      'sortOrder': 'descending',
                      'sortParam': 'startDate'}

    try:
        user[userID] = ['Sentinel2', 'Sentinel-2%20L1C', params_eocurl, '1_TRUE_COLOR']
    except (KeyError, NameError):
        user = {userID: ['Sentinel2', 'Sentinel-2%20L1C', params_eocurl, '1_TRUE_COLOR']}

    return(user)

#==============================================================================================
    # SATELLITE SPECIFICATION FUNCTIONS
#==============================================================================================


def sentinel1(bot, update):

    userID = update.message.from_user['id']
    params_eocurl = {'dataset': 'ESA-DATASET',
                      'maxRecords': 50,
                      'sortOrder': 'descending',
                      'sortParam': 'startDate'}
    user[userID] = ['Sentinel1', 'Sentinel-1%20GRD%20IW', params_eocurl, '1_VV_ORTHORECTIFIED']

def sentinel2(bot, update):

    userID = update.message.from_user['id']
    params_eocurl = {'dataset': 'ESA-DATASET',
                      'maxRecords': 50,
                      'cloudCover': '[0,10]',
                      'sortOrder': 'descending',
                      'sortParam': 'startDate'}
    user[userID] = ['Sentinel2', 'Sentinel-2%20L1C', params_eocurl, '1_TRUE_COLOR']

def sentinel3(bot, update):

    userID = update.message.from_user['id']
    params_eocurl = {'dataset': 'ESA-DATASET',
                      'maxRecords': 50,
                      'sortOrder': 'descending',
                      'sortParam': 'startDate'}
    user[userID] = ['Sentinel3', 'Sentinel-3%20OLCI', params_eocurl, '1_TRUE_COLOR']

#==============================================================================================
    # GET THE LOCATION AND THE IMAGE
#==============================================================================================

def location(bot, update):

    userID = update.message.from_user['id']
    sat = user[userID][0]
    satInst = user[userID][1]
    user_location = update.message.location
    user[userID][2]['lat'] = user_location.latitude
    user[userID][2]['lon'] = user_location.longitude
    layer = user[userID][3]

    imageDate, latestImage = getLatestImageInfo(user[userID])

    url=latestImage
    resp = requests.get(url, stream=True)
    filename = str(uuid.uuid4())
    introString = "The latest {0} image for this area is from {1}".format(sat, imageDate)   
    if resp.status_code == 200:
        update.message.reply_text(introString)
        with open(filename, 'wb') as f:
            resp.raw.decode_content = True
            shutil.copyfileobj(resp.raw, f)
        with open(filename, 'rb') as f:
            update.message.reply_photo(f)
        f.close()
        os.remove(filename)
    eoBrowserUrl="View in full resolution here: http://apps.sentinel-hub.com/eo-browser/#lat={0}&lng={1}&zoom=10&datasource={2}&time={3}&preset={4}"
    update.message.reply_text(eoBrowserUrl.format(user_location.latitude,
                                                  user_location.longitude,
                                                  satInst,
                                                  imageDate,
                                                  layer))
    return


def getLatestImageInfo(dictIn):

    sat = dictIn[0]

    EOCURL = f'https://finder.eocloud.eu/resto/api/collections/{sat}/search.json'

    params = dictIn[2]

    r1 = requests.get(EOCURL, params)
    js = json.loads(r1.content)

    for j in js['features']:
        date = j['properties']['startDate'].split('T')[0]
        image= j['properties']['thumbnail']
        if image is not None:
            break

    return(date, image)

#==============================================================================================
    # OTHER COMMANDS AND MAIN FUNCTION
#==============================================================================================

def help(bot, update):
    update.message.reply_text('Salve, I am Terra Mater, ancient roman goddess of the '
                              'Earth. I can show you images from all over the globe '
                              'if you just send your location or a location of your '
                              'interest. If you want to change the source of the image '
                              'use /sentinel1, /sentinel2, or /sentinel3 respectively. '
                              'To see your current setting, use /test. If you cannot '
                              'receive any answer to your location, try /start first.')

def test(bot, update):

    userID = update.message.from_user['id']
    update.message.reply_text(f'Your ID: {userID} and the chosen satellite: {user[userID][0]}')

def error(bot, update, error):
    
    logger.warning('Update "%s" caused error "%s"' % (update, error))   

def main():
    #token = getpass.getpass("Telegram Bot Token:")

    # Create the EventHandler and pass it your bot's token.
    filename = 'token.txt'
    with open(filename, 'rb') as f:
        TOKEN = f.read().decode()
    f.close()
    updater = Updater(token=TOKEN)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    #user = {}
    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("test", test))
    dp.add_handler(CommandHandler("sentinel1", sentinel1))
    dp.add_handler(CommandHandler("sentinel2", sentinel2))
    dp.add_handler(CommandHandler("sentinel3", sentinel3))

    # on noncommand i.e message - echo the message on Telegram
    #dp.add_handler(MessageHandler(Filters.text, echo))
    dp.add_handler(MessageHandler(Filters.location, location))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
