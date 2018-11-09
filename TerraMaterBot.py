# -*- coding: utf-8 -*-
"""
Created on Thu Apr 19 10:11:51 2018

@author: Administrator
"""


import json
import logging
import os
import pickle
import socket
import sys
import threading
import datetime
import time
import uuid
import telegram as tl
from telegram.ext import CommandHandler, ConversationHandler, \
    Filters, MessageHandler, RegexHandler, Updater
from telegram.ext.dispatcher import run_async
import requests
from geopy.geocoders import Nominatim
import certifi
import ssl
import geopy.geocoders

import utils_bot

ctx = ssl.create_default_context(cafile=certifi.where())
geopy.geocoders.options.default_ssl_context = ctx
hostname = socket.gethostname()
geolocator = Nominatim(user_agent='myApp')
CONVERSATION, = range(1)

# import all the necessary tokens/IDs:
with open('config_bot.cfg') as f:
    tokens = json.loads(f.read())

# Enable logging
logformat = '%(asctime)s - %(name)s - %(levelname)s in %(filename)s, line %(lineno)d - %(message)s'
logging.basicConfig(format=logformat,
                    filename=f'logTerraMater.log',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

entry_keyboard = [['/S1', '/S2', '/S3', '/S5P'],
                  [tl.KeyboardButton('location', request_location=True), '/help']]
entry_markup = tl.ReplyKeyboardMarkup(entry_keyboard)


# Define a few command handlers. These usually take the two arguments bot and
# update. Error handlers also receive the raised TelegramError object in error.


def start(bot, update, user_data):
    """Send a message when the command /start is issued."""
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
    """Send a message when the command /start is issued."""
    update.message.reply_text('I accept the following entries:\n'
                              '/S1: request a Sentinel-1 GRD IW image from your chosen location.\n'
                              '/S2: request a Sentinel-2 MSI image from your chosen location.\n'
                              '/S3: request a Sentinel-3 OLCI image from your chosen location.\n'
                              '/S5P: request a Sentinel-5P image from your chosen location.\n\n'
                              #'/timelapse: request an animated GIF of a time lapse for Sentinel-2 or -3.\n'
                              '/help: display this message.\n'
                              '/start: display the initial welcoming message.\n\n'
                              'You can send me your current location by pressing the location button below or you can send me any location '
                              'you like by choosing "Location" in the attachment menu. '
                              'Additionly, you can send names of cities, places, streets or similar. You can even try voice input.\n'
                              'To switch between normal keyboard and buttons, tap on the keyboard icon next to the entry field.',
                              reply_markup=entry_markup)

    return CONVERSATION


def log_action(request, bot, update, user_data):
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
    url = utils_bot.generate_browser_url('S2', None, lon, lat)

    try:
        date = utils_bot.get_image_date(satellite, lon, lat)
        cf = ('cloudfree ' if satellite is 'S2' else '')
        update.message.reply_text(f'The latest {satellite} {cf}image was acquired on {date}')
        img_url = utils_bot.create_wms_image_url(satellite, lon, lat)
        update.message.reply_photo(photo=img_url)
        update.message.reply_text(text=f'Browse it here in the <a href="{url}">EO Browser</a>.',
                                  parse_mode=tl.ParseMode.HTML,
                                  disable_web_page_preview=True)
    #except requests.exceptions.Timeout:
    #    update.message.reply_text('Unfortunately, the connection to the WMS server timed out. Please try again later.')
    #    logger.exception('Connection to WMS server for f{satellite} timed out. URL: {img_url}.')
    except Exception as e:
        update.message.reply_text('I\'m afraid I couldn\'t open the image for unkown reasons. Please try again later.')
        logger.exception(f'Could not get/open image from the WMS server. Exception: {e}. URL: {img_url}.')


def s1(bot, update, user_data):
    user_data['sat'] = 'S1'

    if 'location' not in user_data:
        logger.info(f'{update.message.from_user.id} has no location')
        update.message.reply_text('Please send me a location first.')
        return

    log_action('S1', bot, update, user_data)
    request_image('S1', bot, update, user_data)
    return CONVERSATION


def s2(bot, update, user_data):
    user_data['sat'] = 'S2'
    if 'location' not in user_data:
        logger.info(f'{update.message.from_user.id} has no location')
        update.message.reply_text('Please send me a location first.')
        return
    log_action('S2', bot, update, user_data)
    request_image('S2', bot, update, user_data)
    return CONVERSATION


def s3(bot, update, user_data):
    user_data['sat'] = 'S3'
    if 'location' not in user_data:
        logger.info(f'{update.message.from_user.id} has no location')
        update.message.reply_text('Please send me a location first.')
        return
    log_action('S3', bot, update, user_data)
    request_image('S3', bot, update, user_data)
    return CONVERSATION


def s5p(bot, update, user_data):
    user_data['sat'] = 'S5P'
    if 'location' not in user_data:
        logger.info(f'{update.message.from_user.id} has no location')
        update.message.reply_text('Please send me a location first.')
        return
    log_action('S5P', bot, update, user_data)
    rep_markup = tl.ReplyKeyboardMarkup([['/CO', '/NO2']])
    update.message.reply_text('Please choose a trace gas.', reply_markup=rep_markup)
    return CONVERSATION


def NO2(bot, update, user_data):
    user_data['trace_gas'] = 'NO2'
    update.message.reply_text('Thank you. Creating the Sentinel-5P NO2 image might take a few seconds.',
                              reply_markup=entry_markup)
    lon, lat = user_data['location']
    url = utils_bot.generate_browser_url('S5P', None, lon, lat, no2=True)
    try:
        img = utils_bot.get_current_S5P_image(lon, lat, user_data['trace_gas'])
        #date= utils.get_latest_image_date('S5P', lon, lat, gas=user_data['trace_gas'])
        #update.message.reply_text(f'The latest Sentinel-5P image was acquired on {date}')
        update.message.reply_photo(photo=img, reply_markup=entry_markup)
        update.message.reply_text(text=f'Browse it here in <a href="{url}">EO Browser</a>.',
                                  parse_mode=tl.ParseMode.HTML,
                                  disable_web_page_preview=True)
    except requests.exceptions.Timeout:
        update.message.reply_text('Unfortunately, the connection to the WMS server timed out. Please try again later.')
        logger.exception('Connection to WMS server for f{satellite} timed out.')
    except Exception as e:
        update.message.reply_text('I\'m afraid I couldn\'t open the image for unkown reasons. Please try again later.')
        logger.exception(f'Could not get/open image from the WMS server. Exception: {e}')

    return CONVERSATION


def CO(bot, update, user_data):
    user_data['trace_gas'] = 'CO'
    update.message.reply_text('Thank you. Creating the Sentinel-5P CO image might take a few seconds.',
                              reply_markup=entry_markup)
    lon, lat = user_data['location']
    url = utils_bot.generate_browser_url('S5P', None, lon, lat, no2=False)
    try:
        img = utils_bot.get_current_S5P_image(lon, lat, user_data['trace_gas'])
        #date= utils.get_latest_image_date('S5P', lon, lat, gas=user_data['trace_gas'])
        #update.message.reply_text(f'The latest Sentinel-5P image was acquired on {date}')
        update.message.reply_photo(photo=img, reply_markup=entry_markup)
        update.message.reply_text(text=f'Browse it here in <a href="{url}">EO Browser</a>.',
                                  parse_mode=tl.ParseMode.HTML,
                                  disable_web_page_preview=True)
    except requests.exceptions.Timeout:
        update.message.reply_text('Unfortunately, the connection to the WMS server timed out. Please try again later.')
        logger.exception('Connection to WMS server for f{satellite} timed out.')
    except Exception as e:
        update.message.reply_text('I\'m afraid I couldn\'t open the image for unkown reasons. Please try again later.')
        logger.exception(f'Could not get/open image from the WMS server. Exception: {e}')

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
    # request_gif(bot, update, user_data)
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
        bot.send_message(chat_id=user_data['user_id'],
                         text='I\'m sorry I could not create a time lapse video. The server did not respond in time.')
        logger.info(f'{job.context} was removed due to a time out.')
        os.remove(f'in/{job.context}TIMEDOUT')
        return CONVERSATION
    elif os.path.isfile(f'in/{job.context}EMPTY'):
        job.schedule_removal()
        with open(f'in/{job.context}EMPTY', 'rb') as f:
            user_data = pickle.load(f)
        bot.send_message(chat_id=user_data['user_id'],
                         text='I\'m sorry I could not create a time lapse video. There are not enough images that meet the requirements.')
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
        logger.exception(f'Geolocator returned an error for {update.message.text}')
        location = None
    if location is not None:
        logger.info(location)
        ulat, ulon = location[1]
        logger.info(f'{user.id} is at ({ulon}, {ulat})')
        user_data['location'] = (ulon, ulat)
        update.message.reply_text(f'I believe this is at lon: {"%.1f" % ulon}, lat: {"%.1f" % ulat}.',
                                  reply_markup=entry_markup)
        bot.sendLocation(chat_id=update.message.chat.id, latitude=ulat, longitude=ulon)
        update.message.reply_text(
            f'If this is the location you were looking for, get an image by using one of the buttons below. '
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
            with open(f'backup/conversationsV5', 'rb') as f:
                conv_handler.conversations = pickle.load(f)
            with open(f'backup/userdataV5', 'rb') as f:
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
            # logger.info(f'Conv State to save is {conv_handler.conversations}')
            # logger.info(f'User State to save is {dp.user_data}')
            # Before pickling
            resolved = conv_handler.conversations.copy()
            try:
                with open(f'backup/conversationsV5', 'wb+') as f:
                    pickle.dump(resolved, f)
                with open(f'backup/userdataV5', 'wb+') as f:
                    pickle.dump(dp.user_data, f)
            except Exception as e:
                logger.error(f'Could not save state: {e}')
                logger.error(f'Conversations: {conv_handler.conversations}')
                logger.error(sys.exc_info()[0])
            if backupWait == 1440:  # for backing up userdata every 24 hours (1 step/min * 60 min/h * 24 h/day)
                backuptime = datetime.datetime.today().isoformat()[:-7].replace(':', '')
                f = open(f'backup/userdataV5{backuptime}', 'wb+')
                pickle.dump(dp.user_data, f)
                f.close()
                backupWait = 0

    # Start the bot.
    logger.info(f'Starting the bot ... on {hostname}')

    # Create the EventHandler and pass it your bot's token.
    updater = Updater(tokens['bot_token'])
    # job = updater.job_queue

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    entries = [CommandHandler('start', start, pass_user_data=True)]

    commands = [
        CommandHandler('start', start, pass_user_data=True),
        CommandHandler('s1', s1, pass_user_data=True),
        CommandHandler('s2', s2, pass_user_data=True),
        CommandHandler('s3', s3, pass_user_data=True),
        CommandHandler('s5p', s5p, pass_user_data=True),
        #CommandHandler('timelapse', gif, pass_user_data=True, pass_job_queue=True),
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
