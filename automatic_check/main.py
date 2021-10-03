from modules.core import Core
from modules.sub_checker import SubChecker
from pymongo import MongoClient
import aioschedule
import asyncio
import time

if __name__ == "__main__":
    debug = False
    if debug:
        client = MongoClient("mongodb://127.0.0.1:27017/")
    else:
        client = MongoClient('mongodb://127.0.0.1:27017/', username="your_user", password="your_password", authSource='your_database')
    users_table = client["streamers-telegram-groups"]["users"]
    core = Core(users_table)
    sub_checker = SubChecker(users_table)

    #aioschedule.every(60).seconds.do(sub_checker.do_checker)
    aioschedule.every().day.at("00:00").do(sub_checker.do_checker)
    #aioschedule.every(10).minutes.do(sub_checker.do_checker)
    aioschedule.every().day.at("05:00").do(sub_checker.kick_user_action)
    # aioschedule.every(60).days.do(sub_checker.do_checker)
    # aioschedule.every(15).seconds.do(sub_checker.kick_user_action)

    loop = asyncio.get_event_loop()
    print("AUTO-CHECKER INIZIALIZZATO.")
    while True:
        loop.run_until_complete(aioschedule.run_pending())
        time.sleep(0.1)
