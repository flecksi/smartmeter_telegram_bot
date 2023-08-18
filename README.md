# smartmeter_telegram_bot
This is a telegram-bot which posts a summary of power consumption from smartmeter-readings.

At the moment, it only works with the web-api from the energy-provider of the city of Graz, Austria (https://github.com/dreautall/stromnetzgraz).

A few environment variables are needed to run the bot:
(they can be put into a .env file or set as environment variables)
```
TELEGRAM_BOT_TOKEN 
TELEGRAM_CHAT_ID 
SNGRAZ_EMAIL
SNGRAZ_PASSWORD 
TIMEZONE 
```

The command to send to the bot is (adding the command to the bot can be done manually usin gthe /botfather bot from telegram, but that is optional):
```
/get_consumption
```

And it returns a message like this:
```
<BOTNAME>, [18.08.2023 at 23:26:44]:
trying to connect to SNGraz...

authenticated at SNGraz, getting data...

installation_id=<INST_ID> (<ADDRESS>), meter_id=<METER_ID> (<M_SHORTNAME>).

fetching data...

fetched data, processing...

processing done: 29 days (2023-07-19 to 2023-08-17)
 > 907kWh/Year (yesterday)
 > 901kWh/Year (last week)
 > 775kWh/Year (last 29 days)
```

See https://docs.python-telegram-bot.org/en/stable/index.html for more information on telegram bots. (you have to chat with /botfather to create a new bot and get a token, then start a chat with the bot and get the chat_id)

## Next things to do:
- add a linechart with yesterday's power consumption (maybe also show the other days behind it)
- add barchart with the daily power consumption of the last days to see a trend
- add a dockerfile
- add a cronjob to run the bot every day
- add a docker-compose file to run the bot and the cronjob