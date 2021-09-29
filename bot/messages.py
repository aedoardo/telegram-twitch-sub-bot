import requests
import re
import jwt
import sys
import os
from datetime import datetime

class Messages:

    def __init__(self, connection, clientID, debug=False):
        self.client = connection
        self.clientID = clientID
        self._debug = debug

    def echo(self, update, context):
        update.message.reply_text(update.message.text)

    def handleRequest(self, url, headers, get=True, data={}):
        if get:
            req = requests.get(url, headers=headers)
        else:
            req = requests.post(url, data=data)
        return req.json()

    @staticmethod
    def do_request(request_type, request_url, request_headers={}, request_data=[]):
        if request_type == "post":
            return requests.post(request_url, data=request_data).json()
        elif request_type == "get":
            return requests.get(request_url, headers=request_headers).json()

        return False

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

            request_response = self.do_request("post", url_request, request_headers=None, request_data=data_request)
            # send the request

            if "access_token" not in request_response:
                return False, None, None
            else:
                return True, request_response["access_token"], request_response["refresh_token"]
        except Exception as e:
            self.logException(e)
            return False, None, None

    @staticmethod
    def update_user_by_twitch_id(users, twitch_id, fields):
        """
        :param twitch_id: super group chat id
        :param users: users collection
        :param fields: dict, fields to udpate
        :return: updated user.
        """
        return users.update_one({"twitch_id": twitch_id}, {"$set": fields})

    @staticmethod
    def logException(e):
        """
        :param e: Exception
        It prints the reason, type, file and error line that caused the exception.
        """
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(e, exc_type, fname, exc_tb.tb_lineno, datetime.now().strftime("%H:%M:%S"))

    def added_to_group(self, update, context):
        try:
            for member in update.message.new_chat_members:  # foreach new member
                if not member.is_bot:  # if he is not a bot.
                    users = self.client["streamers-telegram-groups"]["users"] if not self._debug else \
                        self.client["streamers-telegram-groups"]["users"]  # users collection
                    telegram_user_id = member.id  # get telegram user id.
                    chat_id = update.message.chat.id  # get the chat_id

                    if chat_id == -1001272931937:
                        print("=======LOGGING=========")
                        print(member)

                    chat_info = context.bot.get_chat(chat_id)
                    chat_administrators = context.bot.get_chat_administrators(chat_id)
                    chat_owner = list(filter(lambda user: user["status"] == "creator", chat_administrators))
                    if len(chat_owner) > 0:
                        chat_owner_id = chat_owner[0].user.id
                    else:
                        return self.kick_user(context, telegram_user_id, chat_id)  # kick him

                    get_group = users.find_one({"telegram_id": chat_owner_id})

                    if get_group is None:
                        return self.kick_user(context, telegram_user_id, chat_id)  # kick him

                    is_multigroup = "telegram_group_id" in get_group and type(
                        get_group["telegram_group_id"]).__name__ != "Int64"

                    if is_multigroup and str(chat_id) in get_group["telegram_group_id"] and not get_group["telegram_group_id"][str(chat_id)]["isActive"]:
                        return None

                    user_account = users.find_one({"telegram_id": telegram_user_id})
                    if chat_id == -1001272931937:
                        print(user_account)
                    if user_account is None:  # mh, you are not registered on twitcham!
                        return self.kick_user(context, telegram_user_id, chat_id)  # kick him


                    headers = {
                        "Client-ID": self.clientID,
                        "Authorization": "Bearer " + get_group["access_token"]
                    }  # headers for request to API

                    url = "https://api.twitch.tv/helix/subscriptions?broadcaster_id=" + str(get_group["twitch_id"]) + \
                          "&user_id=" + str(user_account["twitch_id"])

                    response = self.do_request("get", url, request_headers=headers)
                    if "status" in response:
                        success_request, new_access_token, new_refresh_token = self.renew_access_token(
                            get_group["refresh_token"])

                        if not success_request:  # fu*k, die.
                            return None  # TODO: show some message (?).

                        fields_to_update = {
                            "access_token": new_access_token,
                            "refresh_token": new_refresh_token
                        }  # update the access token and refresh token
                        self.update_user_by_twitch_id(users, get_group["twitch_id"], fields_to_update)  # do the update.

                        headers["Authorization"] = "Bearer " + new_access_token
                        # update the access token in headers and
                        # resend req
                        response = self.do_request("get", url, request_headers=headers)  # oh here we're cool, maybe.

                    if "data" not in response:  # oh :(
                        return None  # error

                    # TODO: re-do all logic for multigroups.

                    if not is_multigroup:
                        is_user_in_group = list(filter(lambda us: us["telegram_id"] == telegram_user_id,
                                                       get_group["group_users"]))  # check if user is in group!
                    else:
                        is_user_in_group = list(filter(lambda us: us["telegram_id"] == telegram_user_id,
                                                       get_group["group_users"][str(chat_id)]))

                    if len(response["data"]) <= 0:  # he is not a subscriber!
                        self.kick_user(context, telegram_user_id, chat_id)  # call the kick function.
                        groups_to_set = set(user_account["groups"]) if "groups" in user_account else None

                        if groups_to_set is not None and chat_id in groups_to_set:
                            # remove the group from the users.
                            groups_to_set = groups_to_set - str(chat_id)
                            # update the groups users
                            self.update_user_by_twitch_id(users, user_account["twitch_id"],
                                                          {"groups": list(groups_to_set)})

                        if len(is_user_in_group) > 0:  # check if he is in the group list.
                            if not is_multigroup:
                                get_index_user_group = get_group["group_users"].index(
                                    {
                                        "telegram_id": telegram_user_id,
                                        "twitch_id": user_account["twitch_id"]
                                    }
                                )
                            else:
                                # multigroups.
                                get_index_user_group = get_group["group_users"][str(chat_id)].index(
                                    {
                                        "telegram_id": telegram_user_id,
                                        "twitch_id": user_account["twitch_id"]
                                    }
                                )

                            if get_index_user_group > -1:
                                if not is_multigroup:
                                    get_group["group_users"].pop(get_index_user_group)  # remove the user
                                else:
                                    get_group["group_users"][str(chat_id)].pop(get_index_user_group)
                                self.update_user_by_twitch_id(users, get_group["twitch_id"],
                                                              {"group_users": get_group["group_users"]})  # save the
                                # new data

                        return None  # return

                    if "groups" not in user_account:
                        # this is the first group where the user join
                        res = self.update_user_by_twitch_id(users, user_account["twitch_id"], {"groups": [chat_id]})
                        if res.matched_count <= 0:
                            self.kick_user(context, telegram_user_id, chat_id)
                            print("Non ho aggiornato: ", user_account)
                            return None
                    elif "groups" in user_account and chat_id not in user_account["groups"]:  # just add.
                        user_account["groups"].append(chat_id)
                        # add to the groups
                        res = self.update_user_by_twitch_id(users, user_account["twitch_id"],
                                                            {"groups": user_account["groups"]})
                        if res.matched_count <= 0:
                            self.kick_user(context, telegram_user_id, chat_id)
                            print("Non ho aggiornato: ", user_account)
                            return None

                    # check if for some reason he was in the group t
                    user_data_info = {
                        "telegram_id": telegram_user_id,
                        "twitch_id": user_account["twitch_id"]
                    }


                    if not is_multigroup and user_data_info not in get_group["group_users"]:
                        # add user
                        get_group["group_users"].append(
                            {
                                "telegram_id": telegram_user_id,
                                "twitch_id": user_account["twitch_id"]
                            }
                        )
                    elif is_multigroup and user_data_info not in get_group["group_users"][str(chat_id)]:
                        get_group["group_users"][str(chat_id)].append(
                            {
                                "telegram_id": telegram_user_id,
                                "twitch_id": user_account["twitch_id"]
                            }
                        )

                    self.update_user_by_twitch_id(users, get_group["twitch_id"],
                                                  {"group_users": get_group[
                                                      "group_users"]})  # done all, update user
                    # members
        except Exception as e:
            self.logException(e)
            chat_id = update.message.chat.id  # get the chat_id
            print(chat_id)
            return None

    @staticmethod
    def kick_user(context, user_id, chat_id):
        context.bot.kickChatMember(chat_id, user_id)
        context.bot.unbanChatMember(chat_id, user_id)
        return
