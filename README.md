# Twitcham ~ Telegram bot for Twitch subscribers

This bot is able to check if a Telegram user is a subscriber in a Twitch channel. However, the repository is no longer maintained and you can just start from this to build your personal bot. The quality of code is not very good, since I wrote it in one-two days one year ago.

## Dependencies

The bot uses [MongoDB](https://www.mongodb.com/) as database with the [PyMongo](https://pymongo.readthedocs.io/en/stable/) library. The external libraries needed are in the __requirements.txt__ file while the others are installed with [Anaconda](https://www.anaconda.com/products/individual) by default.

## Folders

As you can see, there are two folders: [bot](./bot) and [automatic_check](./automatic_check). In the first folder there are all the files needed to run the bot, while in the second one there are the files needed to run the auto-checker for the bot.

## Simple setup

I recommend to use some process manager like [pm2](https://pm2.keymetrics.io/) in order to avoid any problem in case of failure. In order to run the code you need to setup some variables:

  - [bot.py](./bot/bot.py): replace `tokenBotId` with your development token bot and production token bot ([line 69](https://github.com/aedoardo/telegram-twitch-sub-bot/blob/main/bot/bot.py#L69)), replace `clientID` with your client id provided by Twitch ([line 70](https://github.com/aedoardo/telegram-twitch-sub-bot/blob/main/bot/bot.py#L70)), replace the parameters for the database connection ([line 71](https://github.com/aedoardo/telegram-twitch-sub-bot/blob/main/bot/bot.py#L71));
  - [commands.py](./bot/commands.py): replace `clientID` with your client id provided by Twitch ([line 521](https://github.com/aedoardo/telegram-twitch-sub-bot/blob/main/bot/commands.py#L521)), replace `clientSecret` with your client secret provided by Twitch ([line 522](https://github.com/aedoardo/telegram-twitch-sub-bot/blob/main/bot/commands.py#L522));
  - [messages.py](./bot/messages.py): replace the same as __commands.py__ file at lines: [45](https://github.com/aedoardo/telegram-twitch-sub-bot/blob/main/bot/messages.py#L45), [46](https://github.com/aedoardo/telegram-twitch-sub-bot/blob/main/bot/messages.py#L46);
  - [sub_checker.py](./automatic_check/modules/sub_checker.py): replace the same as __commands.py__ file at lines: [37](https://github.com/aedoardo/telegram-twitch-sub-bot/blob/main/automatic_check/modules/sub_checker.py#L37), [38](https://github.com/aedoardo/telegram-twitch-sub-bot/blob/main/automatic_check/modules/sub_checker.py#L38), [98](https://github.com/aedoardo/telegram-twitch-sub-bot/blob/main/automatic_check/modules/sub_checker.py#L98). At lines [212](https://github.com/aedoardo/telegram-twitch-sub-bot/blob/main/automatic_check/sub_checker.py#L212), [328](https://github.com/aedoardo/telegram-twitch-sub-bot/blob/main/automatic_check/modules/sub_checker.py#L328), [337](https://github.com/aedoardo/telegram-twitch-sub-bot/blob/main/automatic_check/modules/sub_checker.py#L337) and [340](https://github.com/aedoardo/telegram-twitch-sub-bot/blob/main/automatic_check/modules/sub_checker.py#L340) replace `botIdAndToken` with your bot id and token (as reported in Telegram APIs);
  - [main.py](./automatic_check/main.py): replace MongoDB connection parameters with yours.


Just run `python bot.py` and you will se your bot running. Run `python main.py` to run the auto checker.

## Database table

The database **IS NOT OPTIMIZED**. This is an example of data:
```json
{
    "_id": {
        "$oid": "5ff09030cd55d6d9f378d460"
    },
    "groups": ["list of groups id"],
    "twitch_username": "user_twitch_username",
    "twitch_id": "user_twitch_id",
    "last_access_ts": 1632839210,
    "last_access": "2021-9-28 15:26:50",
    "telegram_id": "telegram_id as integer",
    "verified_date": "2021-1-2 16:24:32",
    "verified_ts": 1609601072,
    "group_users": {
        "chat_id": [{
            "telegram_id": "telegram_id as integer",
            "twitch_id": "twitch_id"
        }],
    },
    "group_user": [],
    "access_token": "access_token_twitch",
    "refresh_token": "refresh_token_twitch",
    "registered_access": "2021-1-2 16:24:42",
    "invitationLink": "used only with single group and not multigroup",
    "telegram_group_active": true,
    "telegram_group_id": {
        "group id": {
            "invitationLink": "group invitation link",
            "isActive": true,
            "automaticCheck": true
        },
    },
    "groups_users_to_kick": {}
}
```
The `group_users` column is a column with all the groups registered by the user and each key as a value a list with all users' `twitch id` and `telegram id`.

