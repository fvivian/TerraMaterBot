# Telegram Bot in Earth Observation

This bot allows the Telegram user to request an image from either Sentinel-1, Sentinel-2 or Sentinel-3 of his current location or any other location he chooses. Upon receiving the location data, the bot looks for the most recent imagery with the least possible cloud coverage and sends it to the user along with a link to Sinergise's EO Browser (https://apps.sentinel-hub.com/eo-browser/).

First, the user has to send /start to @TerraMaterBot in order to initialize the bot. It creates the user's chat ID along with other default settings. To receive an image, the user has to either send a command in the form of /s1, /s2, or /s3 (/s5p is currently offline) or tap on the button on the custom keyboard. For further instructions, /help may be used.

![](https://github.com/fvivian/TerraMaterBot/master/TerraMaterV3_img2.PNG)
