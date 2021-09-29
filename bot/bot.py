from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
import logging
from pymongo import MongoClient
from telegram.ext.dispatcher import run_async
from commands import Commands
from messages import Messages
import urllib.parse
import sys
import os

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


class TelegramTwitchBot():

    def __init__(self, token, mongoConnection, clientID):
        self._token = token
        self._mongo = mongoConnection
        self._clientID = clientID
        self._commands = []

    def _loadCommands(self, dp):
        commandsCollection = self._mongo["streamers-telegram-groups"]["botcommands"]
        commandsClass = Commands(self._mongo, self._clientID)
        messagesClass = Messages(self._mongo, self._clientID)

        cursor = commandsCollection.find({})
        for command in cursor:
            self._commands.append(command["name"])
            if command["type"] == "command":
                dp.add_handler(CommandHandler(command["name"], getattr(commandsClass, command["callback"]),
                                              run_async=command["async"]))
            elif command["type"] == "message":
                dp.add_handler(
                    MessageHandler(getattr(Filters, command["filters"]), getattr(messagesClass, command["callback"])))
            elif command["type"] == "buttonCommand":
                dp.add_handler(
                    CallbackQueryHandler(getattr(commandsClass, command["callback"]))
                )

        print("COMMANDS & MESSAGES LOADED {}".format(len(self._commands)))

    def error(self, update, context):
        logger.warning('Update {} caused error {}'.format(update, context.error))

    def _main(self):
        self.updater = Updater(self._token, use_context=True)
        dp = self.updater.dispatcher
        self._loadCommands(dp)
        dp.add_error_handler(self.error)
        self.updater.start_polling()
        self.updater.idle()

def logException(e):
        """
        :param e: Exception
        It prints the reason, type, file and error line that caused the exception.
        """
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(e, exc_type, fname, exc_tb.tb_lineno)

if __name__ == "__main__":
    try:
        debug = False
        tokenBotId = "production token bot" if not debug else "dev token bot"
        clientID = "Twitch ClientID"
        mongoClient = MongoClient('mongodb://127.0.0.1:27017/', username="your_user", password="your_password", authSource='database_name')
        bot = TelegramTwitchBot(tokenBotId, mongoClient, clientID)
        bot._main()
    except Exception as e:
        logException(e)

