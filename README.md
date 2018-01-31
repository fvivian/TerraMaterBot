# Telegram Bot in Earth Observation

## Bot is currently offline.

This bot allows the Telegram user to request an image from either Sentinel-1, Sentinel-2 or Sentinel-3 of his current location or any other location he chooses. Upon receiving the location data, the bot looks for the most recent imagery with the least possible cloud coverage and sends it to the user along with a link to Sinergise's EO Browser (https://apps.sentinel-hub.com/eo-browser/).

First, the user has to send /start to @TerraMaterBot in order to initialize the bot. It creates the user's chat ID along with other default settings. Furthermore, the user can switch between the satellites using /sentinel1, /sentinel2, and /sentinel3. To check what satellite is the current, use /test.

![alt text](https://github.com/fvivian/TelegramBot/blob/master/TerraMater_img.png)
