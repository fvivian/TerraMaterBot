# -*- coding: utf-8 -*-

import json
import logging
import os
import pickle
import socket
import sys
import threading
import time
from datetime import datetime

import requests

import telegram as tl
from telegram.ext import CommandHandler, ConversationHandler,\
                         Filters, MessageHandler, RegexHandler, Updater
from telegram.ext.dispatcher import run_async

from geopy.geocoders import Nominatim

hostname, DATA = socket.gethostname(), os.getcwd()
geolocator = Nominatim()
CONVERSATION, = range(1)

# Enable logging
logformat = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(format=logformat,
                    filename=f'{DATA}/logTerraMater.log',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

entry_keyboard = [['/S1', '/S2', '/S3', '/S5P'],
                  [tl.KeyboardButton('location', request_location=True), '/help']]
entry_markup = tl.ReplyKeyboardMarkup(entry_keyboard)

def generate_browser_url(sat, date, lon, lat):
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
        return 'NYI'

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
    elif sat == 'S5P':
        pass
    else:
        logger.info(f'Unknown satellite {sat}')

    try:
        jres = json.loads(requests.get(url, params, timeout=5).content)
    except requests.exceptions.Timeout:
        logger.error(f'Request to Finder timed out.')
        return None
    except Exception as e:
        logger.error(f'Could not obtain result from Finder for {sat}, {lon}/{lat}; exception was {e}')
        return None

    if len(jres['features']) > 1:
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
        logger.info(preview)
        date = j['properties']['startDate'].split('T')[0]
        return (date, preview, generate_browser_url(sat, date, lon, lat))
    else:
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
				'/help: display this message.\n'
				'/start: display the initial welcoming message.\n\n'
				'You can send me your current location by pressing the location button below or you can send me any location '
				'you like by choosing "Location" in the attachment menu. '
				'Additionly, you can send names of cities, places, streets or similar. You can even try voice input.\n'
				'To switch between normal keyboard and buttons, tap on the keyboard icon next to the entry field.', reply_markup=entry_markup)

    return CONVERSATION


def logaction(satellite, bot, update, user_data):
    msg = update.message
    user = msg.from_user
    logger.info(f'{user.id} requests {satellite} image')
    if 'location' in user_data:
        logger.info(f'{user.id} is at {user_data["location"]}')
    else:
        logger.info(f'{user.id} has no location')

@run_async
def request_image(satellite, bot, update, user_data):
    user_data['last_visit'] = datetime.now()
    if 'location' in user_data:
        lon, lat = user_data['location']
    else:
        logger.info(f'{update.message.from_user.id} has no location')
        update.message.reply_text('Please send me a location first.')
        return

    result = get_current_image(satellite, lon, lat)

    logger.info(f'Got a result for user {update.message.from_user.id}; {result}')

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
                logger.error(f'Preview not valid: {preview}')
                logger.error(e)
        else:
            update.message.reply_text('Unfortunately, there is no preview.')
        update.message.reply_text(
           text=f'Browse it here in <a href="{url}">EO Browser</a>.',
           parse_mode=tl.ParseMode.HTML,
           disable_web_page_preview=True)
    else:
        update.message.reply_text('I do not find an image here.')
        update.message.reply_text('The system might be busy.')


def s1(bot, update, user_data):
    logaction('S1', bot, update, user_data)
    request_image('S1', bot, update, user_data)
    return CONVERSATION


def s2(bot, update, user_data):
    logaction('S2', bot, update, user_data)
    request_image('S2', bot, update, user_data)
    return CONVERSATION


def s3(bot, update, user_data):
    logaction('S3', bot, update, user_data)
    request_image('S3', bot, update, user_data)
    return CONVERSATION


def s5p(bot, update, user_data):
    logaction('S5P', bot, update, user_data)
    # request_image('S5P', bot, update, user_data)
    update.message.reply_text('Sentinel 5P is not there just yet.')
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
    user_data['last_visit'] = datetime.now()
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
        update.message.reply_text(f'I believe this is at lon: {"%.2f" % ulon}, lat: {"%.2f" % ulat}.',
                                  reply_markup=entry_markup)
        bot.sendLocation(chat_id=update.message.chat.id, latitude=ulat, longitude=ulon)
        update.message.reply_text(f'If this is the location you were looking for, get an image by using one of the buttons below.'
				   'If this is not what you were looking for, re-send a location name or your location by using the button below.')
    else:
        update.message.reply_text('I can\'t find out where this is.',
                                  reply_markup=entry_markup)
    return CONVERSATION 

def echo(bot, update, user_data):
    '''Echo the user message.'''
    msg = update.message
    user = msg.from_user
    logger.info(f'{user.id} sends {update.message.text}')
    get_and_respond_to_location(bot, update, user_data)

def error(bot, update, error):
    '''Log Errors caused by Updates.'''
    logger.warning(f'Update "{update}" caused error "{error}"')


def main():

    def load_state():
        try:
            with open(f'{DATA}/backup/conversationsV3', 'rb') as f:
                conv_handler.conversations = pickle.load(f)
            with open(f'{DATA}/backup/userdataV3', 'rb') as f:
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
            logger.info(f'Conv State to save is {conv_handler.conversations}')
            logger.info(f'User State to save is {dp.user_data}')
            # Before pickling
            resolved = conv_handler.conversations.copy()
            try:
                with open(f'{DATA}/backup/conversationsV3', 'wb+') as f:
                    pickle.dump(resolved, f)
                with open(f'{DATA}/backup/userdataV3', 'wb+') as f:
                    pickle.dump(dp.user_data, f)
            except Exception as e:
                logger.error(f'Could not save state: {e}')
                logger.error(f'Conversations: {conv_handler.conversations}')
                logger.error(sys.exc_info()[0])
            if backupWait == 1440: # for backing up userdata every 24 hours (1 step/min * 60 min/h * 24 h/day)
                backuptime = datetime.today().isoformat()[:-7].replace(':', '')
                f = open(f'{DATA}/backup/userdataV3{backuptime}', 'wb+')
                pickle.dump(dp.user_data, f)
                f.close()
                backupWait = 0
                

    # Start the bot.
    logger.info(f'Starting the bot ... on {hostname}')

    # Create the EventHandler and pass it your bot's token.
    updater = Updater(os.environ['TOKEN'])

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    entries = [CommandHandler('start', start, pass_user_data=True)]

    commands = [
        CommandHandler('start', start, pass_user_data=True),
        CommandHandler('s1', s1, pass_user_data=True),
        CommandHandler('s2', s2, pass_user_data=True),
        CommandHandler('s3', s3, pass_user_data=True),
        CommandHandler('s5p', s5p, pass_user_data=True),
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
