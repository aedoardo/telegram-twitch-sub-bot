import os
import sys
import requests
import asyncio
import time
from datetime import timedelta, date, datetime
from modules.core import Core


class SubChecker:

    def __init__(self, _db):
        self.core = Core(_db)
        self.data = None
        self.db = _db
        self.groups_to_alert = {}
        self.cache_usernames = {}
        self.kicking_queue = []

    @staticmethod
    def log_exception(e):
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(e, exc_type, fname, exc_tb.tb_lineno)

    def renew_access_token(self, refresh_token):
        """
        :param refresh_token: refresh token
        :return: False if fail, else a tuple with a boolean flag True and the new access token and the refresh token.
        """
        try:
            url_request = "https://id.twitch.tv/oauth2/token"  # endpoint url API

            data_request = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": "Twitch ClientID",
                "client_secret": "Twitch ClientSecret"
            }  # to refresh the token

            request_response = self.do_request("post", url_request, request_headers=None,
                                               request_data=data_request)  # send the request

            if "access_token" not in request_response:
                return False, None, None
            else:
                return True, request_response["access_token"], request_response["refresh_token"]
        except Exception as e:
            self.logException(e)
            return False, None, None

    @staticmethod
    def do_request(request_type, request_url, request_headers={}, request_data=[]):
        if request_type == "post":
            return requests.post(request_url, data=request_data).json()
        elif request_type == "get":
            return requests.get(request_url, headers=request_headers).json()
        return False

    async def check(self, users, infos):
        try:
            streamer_groups = set()
            users_list = list(users)  # trasformo in lista le chiavi del dizionario utente.
            while len(users_list) > 0:
                tmp_users = users_list[0:100]
                if len(tmp_users) <= 0:
                    break

                users_list = users_list[100:]  # cancelliamo i primi 100 utenti.

                # costruiamo il set di id twitch.
                set_twitch_ids = set()
                for user in tmp_users:
                    if len(users[user]) > 0:
                        if users[user][0]["twitch_id"] != infos["twitch_id"]:
                            set_twitch_ids.add(users[user][0]["twitch_id"])

                headers = {
                    "Client-ID": "Twitch ClientID",
                    "Authorization": "Bearer " + str(infos["access_token"])
                }

                url = "https://api.twitch.tv/helix/subscriptions?broadcaster_id=" + str(infos["twitch_id"]) \
                      + "&user_id=" + '&user_id='.join([*set_twitch_ids]) + '&first=' + str(len(set_twitch_ids))

                response = self.do_request("get", url, request_headers=headers)  # do the request.
                if "data" not in response:
                    is_ok, new_at, new_rt = self.renew_access_token(infos["refresh_token"])
                    #print(is_ok, new_at, infos["twitch_id"])
                    if is_ok:
                        self.db.update_one({"twitch_id": infos["twitch_id"]}, {
                            "$set": {
                                "access_token": new_at,
                                "refresh_token": new_rt
                            }
                        })
                        headers = {
                            "Client-ID": "Twitch ClientID",
                            "Authorization": "Bearer " + str(new_at)
                        }
                        response = self.do_request("get", url, request_headers=headers)
                    else:
                        print("# 1 Non ho potuto controllare lo streamer: " + str(infos["twitch_id"]))
                        continue  # exit from checks.

                if "data" not in response:
                    #print(response)
                    print(headers, url)
                    print("#2 Non ho potuto controllare lo streamer: " + str(infos["twitch_id"]))
                    continue  # (br)exit from checks.

                set_data_twitch_ids = {_["user_id"] for _ in response["data"]}  # users with a sub.

                for k in tmp_users:
                    if len(users[k]) <= 0:
                        continue

                    user_telegram_id = users[k][0]["telegram_id"]
                    user_twitch_id = users[k][0]["twitch_id"]

                    if int(user_telegram_id) == infos["telegram_id"]:
                        continue

                    if user_twitch_id not in set_data_twitch_ids:
                        for user_group in users[k]:
                            if "kick_info" in user_group:
                                if str(user_group["group_id"]) not in self.groups_to_alert:
                                    self.groups_to_alert[str(user_group["group_id"])] = {}
                                    streamer_groups.add((str(user_group["group_id"])))

                                kick_info = user_group["kick_info"]
                                if not kick_info["is_to_kick"] or kick_info["date"] is None:  # check if it is none
                                    # it is the first time that he has not the sub, so calculate the date to kick.
                                    kicking_date = (date.today() + timedelta(days=2)).strftime("%d/%m/%Y")
                                    self.groups_to_alert[str(user_group["group_id"])][str(user_group["telegram_id"])] = \
                                        kicking_date
                                else:
                                    self.groups_to_alert[str(user_group["group_id"])][str(user_group["telegram_id"])] = \
                                        kick_info["date"]
                            elif user_group["twitch_id"] not in set_data_twitch_ids:
                                # the user has not a sub!!
                                if str(user_group["group_id"]) not in self.groups_to_alert:
                                    self.groups_to_alert[str(user_group["group_id"])] = {}
                                    streamer_groups.add((str(user_group["group_id"])))

                                kicking_date = (date.today() + timedelta(days=2)).strftime("%d/%m/%Y")
                                self.groups_to_alert[str(user_group["group_id"])][
                                    str(user_group["telegram_id"])] = kicking_date
                            else:
                                if infos["kick_info"] is not None and str(user_group["group_id"]) in infos["kick_info"] and str(user_group["telegram_id"]) in infos["kick_info"][str(user_group["group_id"])]:
                                    if user_group["twitch_id"] in set_data_twitch_ids:
                                        del infos["kick_info"][str(user_group["group_id"])][
                                            str(user_group["telegram_id"])]

            to_update = {}
            for key_group in infos["telegram_group_id"]:
                if str(key_group) in self.groups_to_alert:
                    to_update[str(key_group)] = self.groups_to_alert[str(key_group)]

            #print(to_update)
            self.db.update_one({
                "twitch_id": infos["twitch_id"]
            }, {
                "$set": {
                    "groups_users_to_kick": to_update
                }
            })
            await self.send_kicking_alert(infos, streamer_groups)
            # await self.send_kicking_alert(infos, streamer_groups)
        except Exception as e:
            self.log_exception(e)
            return None

    @asyncio.coroutine
    async def send_kicking_alert(self, infos, groups):
        try:
            for group in groups:
                if len(self.groups_to_alert[group]) > 0:
                    message = " 🚀 *Report giornaliero* 🚀 \n \n "
                    maj_two_days = []
                    min_two_days = []
                    for user in self.groups_to_alert[group]:
                        if int(user) == infos["telegram_id"]:
                            continue

                        if user not in self.cache_usernames:
                            get_user = self.db.find_one({"telegram_id": int(user)})
                            if get_user is None:
                                continue
                            else:
                                self.cache_usernames[user] = get_user["twitch_username"]

                        date_difference = datetime.strptime(self.groups_to_alert[group][user],
                                                            "%d/%m/%Y") - datetime.strptime(
                            date.today().strftime("%d/%m/%Y"), "%d/%m/%Y")
                        if date_difference.days >= 2:
                            maj_two_days.append((str(user), self.cache_usernames[user]))
                        else:
                            min_two_days.append((str(user), self.cache_usernames[user]))

                    if len(maj_two_days) > 0:
                        message += "Gli abbonamenti di: " + ', '.join(
                            "[" + j[1] + "](tg://user?id=" + j[0] + ")" for j in
                            maj_two_days) + " sono *scaduti* ⚠️ . \n \n _Fra 48h sarete allontanati dal gruppo nel caso in cui non rinnovaste_. \n \n "

                    if len(min_two_days) > 0:
                        message += "Gli abbonamenti di: " + ', '.join(
                            "[" + j[1] + "](tg://user?id=" + j[0] + ")" for j in
                            min_two_days) + " sono *scaduti* più di un giorno fa ⚠️ . \n \n _Fra meno di 48h sarete allontanati dal gruppo nel caso in cui non rinnovaste_."

                try:
                    url = "https://api.telegram.org/botIdAndToken/sendMessage?chat_id=" + str(
                        group) + "&text=" + message + "&parse_mode=markdown"
                    r = self.do_request("get", url)
                    time.sleep(0.1)
                except Exception as e:
                    self.log_exception(e)
                    print("erroruccio.")

                del self.groups_to_alert[group]  # delete it from the list

        except Exception as e:
            self.log_exception(e)
            return None

    @asyncio.coroutine
    async def do_checker(self):
        try:
            if self.core is not None:
                self.data = self.core.load_data()
                print("COMINCIA IL CONTROLLO " + str(date.today().strftime("%d/%m/%Y %H:%M:%S")))
                await asyncio.gather(
                    *[self.check(self.data[streamer]["users"], self.data[streamer]["infos"]) for streamer in self.data])
            else:
                print("Core is None")
        except Exception as e:
            self.log_exception(e)
            return None

    @asyncio.coroutine
    async def kick_user_action(self):
        try:
            streamers = self.db.find({"telegram_group_id": {"$exists": True}})
            await asyncio.gather(*[self.do_kick_action(streamer) for streamer in streamers])

        except Exception as e:
            self.log_exception(e)
            return None

    @asyncio.coroutine
    async def do_kick_action(self, streamer):
        try:
            is_multi_group = type(streamer["telegram_group_id"]).__name__ == "dict"
            if not is_multi_group:
                return None

            new_streamer_kicks = {}

            if "groups_users_to_kick" not in streamer:
                return None

            if "groups_users_to_kick" in streamer and type(
                    streamer["groups_users_to_kick"]).__name__ != "dict" or "groups_users_to_kick" in streamer and \
                    streamer["groups_users_to_kick"] is None:
                return None

            #print(streamer["twitch_username"])
            for group in streamer["groups_users_to_kick"]:
                if "automaticCheck" in streamer["telegram_group_id"][str(group)] and \
                        streamer["telegram_group_id"][str(group)]["automaticCheck"]:
                    kicked_users = []
                    new_streamer_kicks[str(group)] = {}
                    groups_users = streamer["group_users"][str(group)]
                    for user in streamer["groups_users_to_kick"][group]:
                        date_difference = datetime.strptime(streamer["groups_users_to_kick"][group][user],
                                                            "%d/%m/%Y") - datetime.strptime(
                            date.today().strftime("%d/%m/%Y"), "%d/%m/%Y")
                        if user not in self.cache_usernames:
                            get_user = self.db.find_one({"telegram_id": int(user)})
                            self.cache_usernames[user] = get_user["twitch_username"]
                        if date_difference.days <= 0:
                            # kick user
                            if user in self.cache_usernames:
                                # self.bot_kick_user(user, str(group))
                                is_in_group = list(
                                    filter(lambda g: g["telegram_id"] == int(user), groups_users))
                                if len(is_in_group) > 0:
                                    twitch_id = is_in_group[0]["twitch_id"]
                                    index_in_list = groups_users.index({
                                        "telegram_id": int(user),
                                        "twitch_id": twitch_id
                                    })
                                    if index_in_list > 0:
                                        streamer["group_users"][str(group)].pop(index_in_list)
                                        kicked_users.append((self.cache_usernames[user], user))
                                        self.bot_kick_user(user, group)

                        else:
                            new_streamer_kicks[str(group)][user] = streamer["groups_users_to_kick"][group][user]

                    await self.send_kick_message_summary(kicked_users, str(group))

                    # update the users to kick.
                    self.db.update_one({
                        "twitch_id": streamer["twitch_id"]
                    }, {
                        "$set": {
                            "groups_users_to_kick": new_streamer_kicks,
                            "group_users": streamer["group_users"]
                        }
                    })

        except Exception as e:
            self.log_exception(e)

    @asyncio.coroutine
    async def send_kick_message_summary(self, users, group):
        try:
            if len(users) > 0:
                message = " 🚀 *Report utenti rimossi* 🚀 \n \n "
                if len(users) > 1:
                    message += "" + ', '.join("[" + j[0] + "](tg://user?id=" + j[1] + ")" for j in
                                              users) + " sono stati allontanati dal gruppo poiché non hanno rinnovato i loro abbonamenti ⚠️ . \n \n "
                else:
                    message += "" + ', '.join("[" + j[0] + "](tg://user?id=" + j[1] + ")" for j in
                                              users) + " è stato allontanato dal gruppo poiché non ha rinnovato il proprio abbonamento ⚠️ . \n \n "

                url = "https://api.telegram.org/botIdAndToken/sendMessage?chat_id=" + str(
                    group) + "&text=" + message + "&parse_mode=markdown"
                r = self.do_request("get", url)
                time.sleep(0.1)
        except Exception as e:
            self.log_exception(e)

    def bot_kick_user(self, telegram_id, group_id):
        try:
            url = "https://api.telegram.org/botIdAndToken/kickChatMember?chat_id=" + str(
                group_id) + "&user_id=" + str(telegram_id)
            r = self.do_request("get", url)
            url = "https://api.telegram.org/botIdAndToken/unbanChatMember?chat_id=" + str(
                group_id) + "&user_id=" + str(telegram_id)
            r = self.do_request("get", url)
            time.sleep(0.1)
        except Exception as e:
            self.log_exception(e)
