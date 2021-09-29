import requests
import re
import jwt
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot, ChatMember
from telegram.ext import CallbackQueryHandler
import json
import sys
import os
from datetime import datetime

# TODO: handle the migration from group to supergroup.

class Commands:

    def __init__(self, connection, clientID, debug=False):
        self.client = connection
        self.clientID = clientID
        self._debug = debug
        with open("botcommands.json", mode='r') as f:
            self.botLanguages = json.load(f)

    @staticmethod
    def sendBotMessageText(update, message):
        return update.message.reply_text(message)

    @staticmethod
    def logException(e):
        """
        :param e: Exception
        It prints the reason, type, file and error line that caused the exception.
        """
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(e, exc_type, fname, exc_tb.tb_lineno, datetime.now().strftime("%H:%M:%S"))

    @staticmethod
    def check_update_istance(update):
        """
        :param update: Update object
        :return: return True if it is from button click, else False.
        """
        if getattr(update, "callback_query") and getattr(update.callback_query, "message") is not None:
            return True

        return False

    @staticmethod
    def get_user_data(is_from_button, update):
        """
        :param is_from_button: boolean
        :param update: Update context
        :return: tuple (user_id, is_bot)
        """
        if not is_from_button:  # he wrote manually
            user_id = update.message.from_user.id  # take user's telegram id.
            is_bot = update.message.from_user.is_bot  # check if it is a bot.
        else:
            user_id = update.from_user.id
            is_bot = update.from_user.is_bot

        return user_id, is_bot

    @staticmethod
    def get_chat_data(is_from_button, update):
        """
        :param is_from_button: boolean
        :param update: Update context
        :return: tuple (user_id, is_bot)
        """
        is_super_group = update.message.chat.type == 'supergroup'  # check if it is a super group.
        chat_id = update.message.chat.id

        return is_super_group, chat_id

    @staticmethod
    def find_user_by_telegram_id(users, telegram_id):
        """
        :param users: users collection
        :param telegram_id: integer of user's id telegram.
        :return: return None if not exists, else an object (MongoCollection).
        """
        return users.find_one({"telegram_id": telegram_id})  # search =), think it is optimized bohhh

    @staticmethod
    def find_user_by_twitch_username(users, twitch_username):
        """
        :param users: users collection
        :param twitch_username: integer of user's id telegram.
        :return: return None if not exists, else an object (MongoCollection).
        """
        return users.find_one({"twitch_username": twitch_username})  # search =), think it is optimized bohhh

    @staticmethod
    def update_user_groups(users, telegram_id, group_users):
        return users.update_one({"telegram_id": telegram_id}, {"$set": {"groups": group_users}})

    @staticmethod
    def update_user_by_telegram_id(users, telegram_id, fields):
        """
        :param users: users collection
        :param telegram_id: integer, user's telegram id
        :param fields: dict, fields to udpate
        :return: updated user.
        """
        return users.update_one({"telegram_id": telegram_id}, {"$set": fields})

    @staticmethod
    def update_user_by_chat_id(users, chat_id, fields):
        """
        :param chat_id: super group chat id
        :param users: users collection
        :param fields: dict, fields to udpate
        :return: updated user.
        """
        return users.update_one({"telegram_group_id": chat_id}, {"$set": fields})

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
    def is_only_user(streamer):
        """
        :param streamer: streamer object
        :return: it returns a boolean that check if the user requested is only a
                 user registered without an active telegram group id.
        """

        return streamer is None or streamer is not None and (
                "telegram_group_active" not in streamer or streamer["telegram_group_active"] is False)

    @staticmethod
    def do_request(request_type, request_url, request_headers={}, request_data=[]):
        if request_type == "post":
            return requests.post(request_url, data=request_data).json()
        elif request_type == "get":
            return requests.get(request_url, headers=request_headers).json()

        return False

    @staticmethod
    def send_inline_keyboard_button_message(update, message, markup):
        """
        :param update: Update object
        :param message: str
        :param markup: InlineKeyboardButton
        :return: send a message to user or group with buttons.
        """
        return update.message.reply_text(message, reply_markup=markup)

    def helpCommand(self, update, context):
        """
        :param update: Update object
        :param context: Context callback
        :return: return the start command, help = start.
        """
        return self.start(update, context)

    def build_markup_menu(self, menu):
        menus = self.botLanguages[menu]
        choices = []
        for _ in menus:
            for __ in _:
                choices.append(InlineKeyboardButton(text=__["text"], callback_data=__["callback_data"]))

        # possible buttons choices
        possible_choices = InlineKeyboardMarkup(inline_keyboard=[choices])  # build the Markup
        return possible_choices

    def start(self, update, context):
        """
        :param update: Update object
        :param context: Context callback
        :return: the buttons list commands.
        """
        try:
            is_from_button = self.check_update_istance(update)  # check if arrives from button click
            if is_from_button:  # if it
                # arrives from a button pressed and not from /verifyAccount
                # written by user
                update = update.callback_query  # it is the new update, with the message.

            if getattr(update, "message") is None:
                return None  # idk where here, never (?)

            chat_type = update.message.chat.type  # get the chat type
            is_using_menus = True
            user_id, is_bot = self.get_user_data(is_from_button, update)
            is_user_creator = context.bot.get_chat_member(update.message.chat.id, user_id).status == 'creator'

            if not is_user_creator and chat_type != 'private':  # do not spam into the group.
                return None

            if not is_using_menus:
                if chat_type == "private":  # if it is a private chat with a user take chat private commands
                    availableCommands = self.botLanguages["availableCommandsChatBot"]
                else:  # else other commands.
                    availableCommands = self.botLanguages["availableCommandsChatGroup"]

                message = self.botLanguages["startMessage"]  # default message to show when send the start list buttons

                inline_keyboard_buttons = []
                for _ in availableCommands:
                    # append the command's button
                    inline_keyboard_buttons.append([InlineKeyboardButton(text=_["desc"], callback_data=_["callback"])])

                # possible buttons choices
                possible_choices = InlineKeyboardMarkup(inline_keyboard=inline_keyboard_buttons)  # build the Markup

                return self.send_inline_keyboard_button_message(update, message, possible_choices)  # send the message.
            else:
                if chat_type == "private":
                    availableCommands = self.botLanguages["userMenus"]
                else:
                    availableCommands = self.botLanguages["groupMenus"]

                buttons_list = []
                for _ in availableCommands:
                    for __ in _:
                        buttons_list.append(InlineKeyboardButton(text=__["text"], callback_data=__["callback_data"]))
                        # build the menus in cols, not in rows!!

                possible_choices = InlineKeyboardMarkup(inline_keyboard=[buttons_list])
                message = self.botLanguages["startMessage"]
                return self.send_inline_keyboard_button_message(update, message, possible_choices)

        except Exception as e:
            self.logException(str(e))  # log the exception
            return self.sendBotMessageText(update, "Error #1")  # return an error to the user

    def manage_buttons(self, update, context):
        """
        :param update: Update object
        :param context: Context callback
        :return: return the command clicked by user.
        """
        try:
            query = update.callback_query  # load the query
            data_requested = query.data  # command requested
            menus_list = ["manage_group", "manage_users", "return_back", "manage_user_data", "how_to_join",
                          "automatic_check", "manage_my_info"]
            context.bot.answer_callback_query(update.callback_query.id, text='')  # reply always
            if data_requested in menus_list:
                return self.manage_menus(update, context, data_requested)
            else:
                callback_dict = {
                    "verifyaccount": self.verify_account,
                    "start": self.start,
                    "renew_link": self.renew_invitation_link,
                    "register_group": self.register_group,
                    "check_users": self.check_users,
                    "update_access_to_group": self.update_access_to_group,
                    "set_automatic_check": self.set_automatic_check,
                    "get_my_info": self.get_my_info
                }

                if data_requested not in callback_dict:
                    return None  # invalid command request.

                return callback_dict[data_requested](update, context)
        except Exception as e:
            self.logException(e)
            return self.sendBotMessageText(update, "Error #2")

    def manage_menus(self, update, context, data):
        try:
            if data != "return_back":  # if it is not a return_back button, call the subMenus!
                if data == "how_to_join":
                    return self.sendBotMessageText(update.callback_query, self.botLanguages["howToJoin"])
                submenu = self.botLanguages["subMenus"][data]
                submenu_buttons_list = []
                for i, _ in enumerate(submenu):
                    submenu_buttons_list.append([])
                    for __ in _:
                        submenu_buttons_list[i].append(InlineKeyboardButton(text=__["text"],
                                                                            callback_data=__["callback_data"]
                                                                            )
                                                       )

                submenu_buttons_list.append(
                    [InlineKeyboardButton(text="🔙 " + self.botLanguages["goBackButtonText"],
                                          callback_data="return_back")]
                )
                choices = InlineKeyboardMarkup(inline_keyboard=submenu_buttons_list)
                context.bot.edit_message_reply_markup(
                    chat_id=update.callback_query.message.chat_id,
                    message_id=update.callback_query.message.message_id,
                    reply_markup=choices
                )
            elif data == "return_back":
                menu_type = "userMenus" if update.callback_query.message.chat.type == "private" else "groupMenus"
                markup = self.build_markup_menu(menu_type)
                context.bot.edit_message_reply_markup(
                    chat_id=update.callback_query.message.chat_id,
                    message_id=update.callback_query.message.message_id,
                    reply_markup=markup
                )
        except Exception as e:
            self.logException(e)
            return None

    def get_my_info(self, update, context):
        try:
            is_from_button = self.check_update_istance(update)  # check if arrives from button click
            if is_from_button:  # if it
                # arrives from a button pressed and not from /verifyAccount
                # written by user
                update = update.callback_query  # it is the new update, with the message.

            if getattr(update, "message") is None:
                return None  # idk where here, never (?)

            user_id, is_bot = self.get_user_data(is_from_button, update)  # load user data
            is_super_group, chat_id = self.get_chat_data(is_from_button, update)

            if is_super_group:
                return None

            if is_bot:  # do vuole andà il bot?
                return None  # so we don't do request on database, we save something.

            users = self.client["streamers-telegram-groups"]["users"] if not self._debug else \
                self.client["streamers-telegram-groups"]["users"]  # get the users collection.
            is_registered = users.find_one({"telegram_id": user_id})  # check if user is already registred.

            if is_registered is None:
                return self.sendBotMessageText(update, "Nessuna informazione da mostrare.")  # return this message.

            message = "ℹ️ <b>Le tue informazioni</b> ℹ️\n\n"
            message += "Twitch username: <b>" + str(is_registered["twitch_username"]) + "</b> \n"
            message += "Twitch id: <b>" + str(is_registered["twitch_id"]) + "</b> \n"
            message += "Telegram id: <b>" + str(is_registered["telegram_id"]) + "</b> \n"
            if "registered_access" in is_registered:
                message += "Data di registrazione: <b>" + str(is_registered["registered_access"]) + "</b>"

            return update.message.reply_text(message, parse_mode="html")
        except Exception as e:
            self.logException(e)
            return None

    def set_automatic_check(self, update, context):
        try:
            is_from_button = self.check_update_istance(update)  # is it from a button click?
            if is_from_button:  # if yes, change the update.
                update = update.callback_query

            from_id, is_bot = self.get_user_data(is_from_button, update)  # load user data

            if is_bot:  # check if he's a bot.
                return None  # return none if yes.

            is_super_group, chat_id = self.get_chat_data(is_from_button, update)  # load chat data
            is_user_creator = context.bot.get_chat_member(chat_id, from_id).status == 'creator'  # user's status.

            if not is_user_creator:
                return None  # avoid spam messages =)

            '''
            if str(chat_id) not in {"-1001301271315", "-1001158356636", "-1001424762821", "-1001493430508", "-1001368512384", "-1001254920071"}:
                return self.sendBotMessageText(update, "Questa funzionalità è in alpha mode e non è ancora "
                                                       "disponibile per tutti. Cercheremo di attivarla a tutti il prima"
                                                       " possibile :)!")
            '''

            if not is_super_group:  # :(
                message = self.botLanguages["noSuperGroup"]  # load message from languages
                return self.sendBotMessageText(update, message)  # send message :-D

            users = self.client["streamers-telegram-groups"]["users"] if not self._debug else \
                self.client["streamers-telegram-groups"]["users"]  # load users collection
            my_account = self.find_user_by_telegram_id(users, from_id)  # find my account

            if my_account is None:  # ops not yet registered
                message = self.botLanguages["needVerification"]  # load the message
                return self.sendBotMessageText(update, message)  # send this message argh!

            if "access_token" not in my_account:  # user has verified his account only as twitch user and not as
                # twitch streamer
                return self.sendBotMessageText(update, self.botLanguages["doLoginInWebsite"])

            is_multigroup = "telegram_group_id" in my_account and type(
                my_account["telegram_group_id"]).__name__ == "dict"

            if not is_multigroup:
                self.convert_telegram_group_to_list(update, my_account, from_id, users)
                is_multigroup = True
                my_account = self.find_user_by_telegram_id(users, from_id)  # find my account

            if is_multigroup and str(chat_id) not in my_account["telegram_group_id"]:
                return self.sendBotMessageText(update, "Oops, error. This group is not valid.")

            if "automaticCheck" in my_account["telegram_group_id"][str(chat_id)] and \
                    my_account["telegram_group_id"][str(chat_id)]["automaticCheck"]:
                return self.sendBotMessageText(update, "Il controllo automatico è già attivo in questo gruppo.")

            my_account["telegram_group_id"][str(chat_id)]["automaticCheck"] = True

            fields_to_update = {
                "telegram_group_id": my_account["telegram_group_id"],
            }
            self.update_user_by_telegram_id(users, from_id, fields_to_update)
            return self.sendBotMessageText(update,
                                           self.botLanguages["automaticCheckSaved"])

        except Exception as e:
            self.logException(e)
            return None

    def check_user_subscription_to_streamer(self, access_token, twitch_streamer_id, twitch_user_id, refresh_token,
                                            users):
        """
        :param users: users collection to update in case of refresh token
        :param access_token: the streamer access_token
        :param twitch_user_id: user_id to check sub
        :param twitch_streamer_id: streamer user_id
        :param refresh_token: streamer refresh token
        """
        try:
            headers = {
                "Client-ID": self.clientID,
                "Authorization": "Bearer " + str(access_token)
            }  # the header to send for the request.

            url = "https://api.twitch.tv/helix/subscriptions?broadcaster_id=" + str(twitch_streamer_id) + \
                  "&user_id=" + str(twitch_user_id)  # url to request

            request_response = self.do_request("get", url, request_headers=headers)  # do the get request

            if "status" in request_response:  # then the request is failed, we need maybe to renew the access token.
                success_request, new_access_token, new_refresh_token = self.renew_access_token(refresh_token)  # obtain
                # new data.
                if not success_request:
                    return None  # TODO: send a message to show a general error

                fields_to_update = {
                    "access_token": new_access_token,
                    "refresh_token": new_refresh_token
                }  # update the access token and refresh token
                self.update_user_by_twitch_id(users, twitch_streamer_id, fields_to_update)  # do the update.

                headers[
                    "Authorization"] = "Bearer " + new_access_token  # update the access token in headers and resend req
                request_response = self.do_request("get", url, request_headers=headers)

            return True, request_response
        except Exception as e:
            self.logException(e)  # log the exception
            return False, None

    def join_in_group(self, response, twitch_streamer_id, twitch_streamer_username, twitch_user_id, invitation_link,
                      streamer, update, context):
        try:
            """
            :param context: contex object
            :param streamer: streamer info
            :param update: Update object
            :param invitation_link: string
            :param response: the response from Twitch endpoint API
            :param twitch_streamer_id: streamer twitch id
            :param twitch_user_id: user id joining in streamer group
            :param users: users collection
            :param twitch_streamer_username: username of streamer
            """

            if "data" not in response:
                return None  # TODO: is it necessary? maybe not.

            if len(response[
                       "data"]) <= 0 and twitch_user_id != twitch_streamer_id:  # is not the streamer
                message = self.botLanguages["cantEnterNoSubscriber"]  # get the message
                return self.sendBotMessageText(update, message.format(twitch_streamer_username))  # you are not a sub.

            message = self.botLanguages["joinInGroup"]
            markup = None
            if type(streamer["telegram_group_id"]).__name__ == "dict":
                button_list = []
                for group in streamer["telegram_group_id"]:
                    if streamer["telegram_group_id"][str(group)]["isActive"]:
                        try:
                            group_info = context.bot.get_chat(group)
                            invitation_link = streamer["telegram_group_id"][str(group)]["invitationLink"]
                            button_list.append(
                                [InlineKeyboardButton(text=message.format(group_info.title, twitch_streamer_username),
                                                      url=invitation_link)]
                            )
                            markup = InlineKeyboardMarkup(button_list)
                        except Exception as e:
                            continue

            else:
                message = "Entra nel gruppo di {}"
                markup = InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton(text=message.format(twitch_streamer_username), url=invitation_link)]
                    ]
                )  # prepare the button

            message = self.botLanguages["clickToJoinInGroup"]
            return self.send_inline_keyboard_button_message(update, message, markup=markup)  # send the button
        except Exception as e:
            self.logException(e)
            return None

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

    def search_similar_streamers(self, users, streamer, update):
        """
        :param users: Users collection
        :param streamer: string, twitch username
        :param update: Update object
        """
        regex = re.compile('.*' + streamer + '.*', re.IGNORECASE)  # build the regex rule

        founded_similar_streamers = users.find(
            {"twitch_username": regex,
             "invitationLink": {
                 "$exists": True
             },
             "telegram_group_active": True
             }).limit(20)  # first 20 (max) streamers similar to streamer.

        if founded_similar_streamers.count() <= 0:  # no user founded.
            message = self.botLanguages["noStreamerSimilarFounded"]  # load the message
            return self.sendBotMessageText(update, message.format(streamer))  # send a message, no found users.
        else:
            # we have some similar streamer.
            similar_streamers_list_message = self.botLanguages["similarStreamers"].format(streamer) + '\n'.join(
                [similar["twitch_username"] for similar in
                 founded_similar_streamers])  # build the list of users.

            return self.sendBotMessageText(update, similar_streamers_list_message)

    def verify_account(self, update, context):
        """
        :param update: Update object
        :param context: Context callback
        :return: a button to open the verification link
        """
        try:

            is_from_button = self.check_update_istance(update)  # check if arrives from button click
            if is_from_button:  # if it
                # arrives from a button pressed and not from /verifyAccount
                # written by user
                update = update.callback_query  # it is the new update, with the message.

            if getattr(update, "message") is None:
                return None  # idk where here, never (?)

            user_id, is_bot = self.get_user_data(is_from_button, update)  # load user data
            is_super_group, chat_id = self.get_chat_data(is_from_button, update)

            if is_super_group:
                return None

            if is_bot:  # do vuole andà il bot?
                return None  # so we don't do request on database, we save something.

            users = self.client["streamers-telegram-groups"]["users"] if not self._debug else \
                self.client["streamers-telegram-groups"]["users"]  # get the users collection.
            is_registered = users.find_one({"telegram_id": user_id})  # check if user is already registred.

            if is_registered is not None:
                message = self.botLanguages["userIsAlreadyRegistered"]
                return self.sendBotMessageText(update, message)  # return this message.

            jwt_code = jwt.encode({"tgid": user_id}, "Replace with Random STRING",
                                  algorithm='HS256')  # build the jwt to pass for
            # the user verification on twitch.

            text_message = self.botLanguages["confirmIdentity"]  # load the text message language

            url_message = "https://twitcham.com/telegram?tgid=" + str(jwt_code)  # build the url
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(text=text_message, url=url_message)]
            ])  # building the markup to send

            text_sent = self.botLanguages["verifyAccountMessage"]  # get the message to send in reply_text
            return self.send_inline_keyboard_button_message(update, text_sent, markup)

        except Exception as e:
            self.logException(e)  # log the exception
            return self.sendBotMessageText(update, "Error about verifyAccount")  # return an error to recognize.

    def register_group(self, update, context):
        """
        :param update: Update
        :param context: Context callback
        :return: a new group maybe.
        """
        try:
            is_from_button = self.check_update_istance(update)  # is it from a button click?
            if is_from_button:  # if yes, change the update.
                update = update.callback_query

            from_id, is_bot = self.get_user_data(is_from_button, update)  # load user data

            if is_bot:  # check if he's a bot.
                return None  # return none if yes.

            is_super_group, chat_id = self.get_chat_data(is_from_button, update)  # load chat data
            is_user_creator = context.bot.get_chat_member(chat_id, from_id).status == 'creator'  # user's status.

            if not is_user_creator:
                return None  # avoid spam messages =)

            if not is_super_group:  # :(
                message = self.botLanguages["noSuperGroup"]  # load message from languages
                return self.sendBotMessageText(update, message)  # send message :-D

            users = self.client["streamers-telegram-groups"]["users"] if not self._debug else \
                self.client["streamers-telegram-groups"]["users"]  # load users collection
            my_account = self.find_user_by_telegram_id(users, from_id)  # find my account

            if my_account is None:  # ops not yet registered
                message = self.botLanguages["needVerification"]  # load the message
                return self.sendBotMessageText(update, message)  # send this message argh!

            if "access_token" not in my_account:  # user has verified his account only as twitch user and not as
                # twitch streamer
                return self.sendBotMessageText(update, self.botLanguages["doLoginInWebsite"])

            is_multigroup = "telegram_group_id" in my_account and type(
                my_account["telegram_group_id"]).__name__ == "dict"
            max_reached_groups = len(my_account["telegram_group_id"]) >= 3 if is_multigroup else False

            if is_multigroup and max_reached_groups:
                return self.sendBotMessageText(update, self.botLanguages["reachedMaxGroup"])

            if not is_multigroup and "telegram_group_id" in my_account and my_account["telegram_group_id"] != -1:
                self.convert_telegram_group_to_list(update, my_account, from_id, users)
                add_group = self.add_new_group(my_account, users, from_id, chat_id, update, context, is_new=False)
            else:
                add_group = self.add_new_group(my_account, users, from_id, chat_id, update, context,
                                               is_new="telegram_group_id" in my_account)

            if not isinstance(add_group, bool):
                return None

            message = self.botLanguages["successActivation"]  # get the message to show
            return self.sendBotMessageText(update, message)  # oh, done all cool.

        except Exception as e:
            self.logException(e)  # log the exception
            return self.sendBotMessageText(update, "Error about registering a new group.")

    def renew_invitation_link(self, update, context):
        """
        :param update: Update
        :param context: Context callback
        :return: new invitation link in a message
        """
        try:
            is_from_button = self.check_update_istance(update)  # check if arrives from button click
            if is_from_button:  # if it
                # arrives from a button pressed and not from /verifyAccount
                # written by user
                update = update.callback_query  # it is the new update, with the message.

            if getattr(update, "message") is None:
                return None  # idk where here, never (?)

            user_id, is_bot = self.get_user_data(is_from_button, update)  # load user data

            if is_bot:
                return None

            is_super_group, chat_id = self.get_chat_data(is_from_button, update)  # load chat data
            is_user_creator = context.bot.get_chat_member(chat_id, user_id).status == 'creator'  # user's status.

            if not is_user_creator:  # you are not the creator, you can't pass.
                return None  # TODO: a good return value or function :-D

            if not is_super_group:  # not a supergroup
                message = self.botLanguages["noSuperGroup"]
                return self.sendBotMessageText(update, message)  # TODO: something, it's late.

            new_invitation_link = context.bot.exportChatInviteLink(chat_id)  # get the new chat link
            users = self.client["streamers-telegram-groups"]["users"] if not self._debug else \
                self.client["streamers-telegram-groups"]["users"]  # load users collection.

            my_account = self.find_user_by_telegram_id(users, user_id)

            if "telegram_group_id" in my_account and type(my_account["telegram_group_id"]).__name__ == "Int64":
                fields_to_update = {"invitationLink": new_invitation_link}  # update the links :)
            elif "telegram_group_id" in my_account and type(my_account["telegram_group_id"]).__name__ == "dict":
                my_account["telegram_group_id"][str(chat_id)][
                    "invitationLink"] = new_invitation_link  # update multigroup
                fields_to_update = {"telegram_group_id": my_account["telegram_group_id"]}

            update_count = self.update_user_by_telegram_id(users, my_account["telegram_id"],
                                                           fields_to_update).modified_count  # update the
            # links
            if update_count <= 0:  # no update needed, because no invitation link, must register before.
                return None

            message = self.botLanguages["successRenewLink"]  # load message

            # build the Markup
            possible_choices = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=message,
                                                                                           url=new_invitation_link)]])

            message = self.botLanguages["copyInvitationLink"]
            return self.send_inline_keyboard_button_message(update, message, possible_choices)  # send copy button

        except Exception as e:
            self.logException(e)  # log the exception
            return self.sendBotMessageText(update, "Error about renew link.")

    def join_command(self, update, context):
        """
        :param update: Update object
        :param context: Context callback
        :return: a message with join link
        """
        try:
            is_from_button = self.check_update_istance(update)  # check if arrives from button click
            if is_from_button:  # if it
                # arrives from a button pressed and not from /verifyAccount
                # written by user
                update = update.callback_query  # it is the new update, with the message.

            if getattr(update, "message") is None:
                return None  # idk where here, never (?)

            user_id, is_bot = self.get_user_data(is_from_button, update)  # load user data
            is_super_group, chat_id = self.get_chat_data(is_from_button, update)  # load chat data

            if is_bot or is_super_group:  # if it is a super group we can't spam into it.
                return None

            users = self.client["streamers-telegram-groups"]["users"] if not self._debug else \
                self.client["streamers-telegram-groups"]["users"]  # get the users collection
            my_account = self.find_user_by_telegram_id(users, user_id)  # check if he is registered

            if my_account is None:
                return None  # TODO: send a button to show the verify account?

            if len(context.args) <= 0:
                return self.sendBotMessageText(update, self.botLanguages["noUserSpecified"])  # no streamer param.

            requested_join_streamer = context.args[0]  # this is the twitch streamer that is requested
            if len(requested_join_streamer) <= 0:  # if it is not a valid input return None
                print("noono")
                return None  # TODO: check something, idk.

            streamer_requested = self.find_user_by_twitch_username(users, requested_join_streamer.lower())  # load the
            # streamer's group if it exists

            if self.is_only_user(streamer_requested):  # this streamer doesn't exists.
                return self.search_similar_streamers(users, requested_join_streamer.lower(),
                                                     update)  # send a message with
                # similar users streamer

            twitch_access_token = streamer_requested[
                "access_token"]  # retrieve twitch access token, to build the request.
            twitch_refresh_token = streamer_requested["refresh_token"]  # retrieve twitch refresh token to fix status.

            is_ok, request = self.check_user_subscription_to_streamer(twitch_access_token,
                                                                      streamer_requested["twitch_id"],
                                                                      my_account["twitch_id"],
                                                                      twitch_refresh_token, users)

            if "status" in request:
                success_request, new_access_token, new_refresh_token = self.renew_access_token(
                    streamer_requested["refresh_token"])

                if not success_request:  # fu*k, die.
                    print("not success request :(")
                    return None  # TODO: show some message (?).

                fields_to_update = {
                    "access_token": new_access_token,
                    "refresh_token": new_refresh_token
                }  # update the access token and refresh token
                self.update_user_by_twitch_id(users, streamer_requested["twitch_id"], fields_to_update)  # do the update.


                #headers["Authorization"] = "Bearer " + new_access_token  # update the access token in headers and
                # resend req
                is_ok, request = self.check_user_subscription_to_streamer(new_access_token,
                                                                   streamer_requested["twitch_id"],
                                                                   my_account["twitch_id"],
                                                                   new_refresh_token, users)

                if "status" in request:
                    print("ERROR AUTH TOKEN" + str(streamer_requested["twitch_username"]))
                    return self.sendBotMessageText(update, "Oops, avvisa " + str(streamer_requested["twitch_username"] + " di questo problemino, non posso farti entrare ora :(!"))

            if not is_ok:  # not ok the call.
                return self.sendBotMessageText(update, "Error while joining in group")  # TODO: send some error to user.

            streamer_requested["invitationLink"] = streamer_requested[
                "invitationLink"] if "invitationLink" in streamer_requested else None
            return self.join_in_group(request, streamer_requested["twitch_id"], streamer_requested["twitch_username"],
                                      my_account["twitch_id"], streamer_requested["invitationLink"], streamer_requested,
                                      update, context)
            # call the function
            # to join

        except Exception as e:
            self.logException(e)  # log the exception
            return self.sendBotMessageText(update, "Error about join command")

    def kick_user_by_command(self, update, context, subscriptions_data, set_twitch_ids, users_list, chat_id, users):
        # TODO: new tests for this function, new logic behind.
        try:
            set_data_twitch_ids = {_["user_id"] for _ in subscriptions_data}  # they are all the users with a valid sub.
            users_twitch_ids_to_kick = set_twitch_ids - set_data_twitch_ids  # all the twitch ids to kick.
            kicked_count = 0
            for user in users_twitch_ids_to_kick:
                user_data = list(filter(lambda _: _["twitch_id"] == user, users_list))  # search user data
                if len(user_data) > 0:
                    user_data = user_data[0]  # better

                    context.bot.kickChatMember(chat_id, user_data["telegram_id"])  # kick the user, is like a ban.
                    context.bot.unbanChatMember(chat_id, user_data["telegram_id"])  # unban the user.

                    # we need to delete the user group from the lists of groups.
                    user_db_data = users.find_one({"telegram_id": user_data["telegram_id"]})

                    if "groups" in user_db_data and chat_id in user_db_data["groups"]:
                        user_db_data["groups"].remove(chat_id)  # remove this group, then update.
                        self.update_user_by_telegram_id(users, user_data["telegram_id"],
                                                        {"groups": user_db_data["groups"]})  # update the database.

                    index_user_in_users_list = users_list.index({
                        "telegram_id": user_data["telegram_id"],
                        "twitch_id": user_data["twitch_id"]
                    })  # get the index in the group users.

                    if index_user_in_users_list > -1:
                        users_list.pop(index_user_in_users_list)  # remove popping.

                    kicked_count += 1  # add 1 to kicked count.

            return kicked_count, users_list
        except Exception as e:
            self.logException(e)  # log the exception
            return False

    def check_users(self, update, context):
        try:

            is_from_button = self.check_update_istance(update)  # check if arrives from button click
            if is_from_button:  # if it
                # arrives from a button pressed and not from /verifyAccount
                # written by user
                update = update.callback_query  # it is the new update, with the message.

            if getattr(update, "message") is None:
                return None  # idk where here, never (?)

            user_id, is_bot = self.get_user_data(is_from_button, update)  # load user data
            is_super_group, chat_id = self.get_chat_data(is_from_button, update)  # load chat data
            user_status = context.bot.get_chat_member(chat_id, user_id).status  # get the user status
            if user_status != 'creator' and user_status != 'administrator' or is_bot:  # can't run this command.
                return None

            if not is_super_group:  # if it is not a super group, no run for this command.
                return None  # TODO: show message or no?

            users = self.client["streamers-telegram-groups"]["users"] if not self._debug else \
                self.client["streamers-telegram-groups"]["users"]  # get the users collection
            my_account = self.find_user_by_telegram_id(users, user_id)  # check if he is registered

            if my_account is None or "telegram_group_id" not in my_account:  # he hasn't a group.
                return None  # TODO: show a message?

            if type(my_account[
                        "telegram_group_id"]).__name__ == 'dict':  # if streamer has one group and he's an old
                # streamer.
                load_group_users = my_account["group_users"][str(chat_id)]  # get users list.
            else:
                load_group_users = my_account["group_users"]

            if len(load_group_users) == 1:
                return self.sendBotMessageText(update, "No users to kick.")

            kicked_user = 0
            while len(load_group_users) > 0:  # until there are some users to check loop.
                users_to_check = load_group_users[0:100]  # we can check 100 users at once.

                # set of twitch user ids, without the owner.
                set_twitch_ids = {_["twitch_id"] for _ in users_to_check if _["twitch_id"] != my_account["twitch_id"]}

                # set of telegram user ids, without the owner.
                set_telegram_ids = {_["telegram_id"] for _ in users_to_check if _["telegram_id"] != user_id}

                # we can now slice to next 100 user.
                load_group_users = load_group_users[100:]

                if len(set_twitch_ids) <= 0:
                    break  # we can stop the while loop, no users to check.

                headers = {
                    "Client-ID": self.clientID,
                    "Authorization": "Bearer " + str(my_account["access_token"])
                }  # prepare the request to endpoint API twitch.

                # prepare the url for the request.
                url = "https://api.twitch.tv/helix/subscriptions?broadcaster_id=" + str(my_account["twitch_id"]) \
                      + "&user_id=" + '&user_id='.join([*set_twitch_ids]) + '&first=' + str(len(set_twitch_ids))

                response = self.do_request("get", url, request_headers=headers)  # do the request.

                if "status" in response:  # we got an error in the request, try to renew the token then, if error, die.
                    success_request, new_access_token, new_refresh_token = self.renew_access_token(
                        my_account["refresh_token"])

                    if not success_request:  # fu*k, die.
                        print("not success request :(")
                        return None  # TODO: show some message (?).

                    fields_to_update = {
                        "access_token": new_access_token,
                        "refresh_token": new_refresh_token
                    }  # update the access token and refresh token
                    self.update_user_by_twitch_id(users, my_account["twitch_id"], fields_to_update)  # do the update.

                    headers["Authorization"] = "Bearer " + new_access_token  # update the access token in headers and
                    # resend req
                    response = self.do_request("get", url, request_headers=headers)  # oh here we're cool, maybe.

                if "data" not in response:  # fu** all is wrong.
                    return None  # arghhh! I hope never here.

                if len(response["data"]) == len(set_twitch_ids):  # if length is equal, maybe we can continue
                    # TODO: check better this continue, maybe can skip some user.
                    continue

                is_multigroup = type(my_account["telegram_group_id"]).__name__ != "Int64"

                if is_multigroup and "automaticCheck" in my_account and my_account["telegram_group_id"][str(chat_id)][
                    "automaticCheck"]:
                    return self.sendBotMessageText(update, "Non puoi controllare manualmente gli abbonamenti poiché "
                                                           "hai attivato il controllo automatico.")

                if not is_multigroup:
                    run_command = self.kick_user_by_command(update, context, response["data"], set_twitch_ids,
                                                            my_account["group_users"], chat_id, users)
                else:
                    run_command = self.kick_user_by_command(update, context, response["data"], set_twitch_ids,
                                                            my_account["group_users"][str(chat_id)], chat_id, users)

                if type(run_command) is tuple:  # wah, is it a tuple or a boolean
                    kicked_user += run_command[0]  # count
                    if not is_multigroup:
                        my_account["group_users"] = run_command[1]  # new users list
                    else:
                        my_account["group_users"][str(chat_id)] = run_command[1]

            self.sendBotMessageText(update, "Kicked users: " + str(kicked_user))  # show users kicked count.
            return self.update_user_by_telegram_id(users, user_id, {"group_users": my_account["group_users"]})
        except Exception as e:
            self.logException(e)  # store exception
            return self.sendBotMessageText(update, "Errore about check users.")

    def update_access_to_group(self, update, context):
        try:
            is_from_button = self.check_update_istance(update)  # is it a click?
            if is_from_button:  # if it
                # arrives from a button pressed and not from /verifyAccount
                # written by user
                update = update.callback_query  # it is the new update, with the message.

            if getattr(update, "message") is None:
                return None  # idk where here, never (?)

            user_id, is_bot = self.get_user_data(is_from_button, update)  # load user data

            if is_bot:
                return None

            is_super_group, chat_id = self.get_chat_data(is_from_button, update)  # load chat data
            is_user_creator = context.bot.get_chat_member(chat_id, user_id).status == 'creator'  # user's status.

            if not is_user_creator:  # you are not the creator, you can't pass.
                return None  # TODO: a good return value or function :-D, also if not in permissions users list

            if not is_super_group:  # not a supergroup
                message = self.botLanguages["noSuperGroup"]
                return self.sendBotMessageText(update, message)  # TODO: something, it's late.
            users = self.client["streamers-telegram-groups"]["users"] if not self._debug else \
                self.client["streamers-telegram-groups"]["users"]  # load users collection.

            my_account = self.find_user_by_telegram_id(users, user_id)

            complement_status = False
            if "telegram_group_id" in my_account and type(my_account["telegram_group_id"]).__name__ == "Int64":
                complement_status = not my_account["telegram_group_active"]
                fields_to_update = {"telegram_group_active": complement_status}  # set to false the group
            else:
                my_account["telegram_group_id"][str(chat_id)]["isActive"] = not \
                    my_account["telegram_group_id"][str(chat_id)]["isActive"]
                fields_to_update = {"telegram_group_id": my_account["telegram_group_id"]}

            self.update_user_by_telegram_id(users, my_account["telegram_id"], fields_to_update)

            if not complement_status and type(my_account["telegram_group_id"]).__name__ == "Int64" \
                    or type(my_account["telegram_group_id"]).__name__ != "Int64" \
                    and not my_account["telegram_group_id"][str(chat_id)]["isActive"]:
                message = self.botLanguages["updateGroupStatusNotAvailable"]
            else:
                message = self.botLanguages["updateGroupStatusAvailable"]
            return self.sendBotMessageText(update, message)

        except Exception as e:
            self.logException(e)
            return self.sendBotMessageText(update, "Error about disable access to group.")

    def add_new_group(self, streamer, users, from_id, chat_id, update, context, is_new=True):
        try:
            # need to check if chat_id is inside.
            is_registered = False
            if "telegram_group_id" in streamer and streamer["telegram_group_id"] != -1:
                is_registered = str(chat_id) in streamer["telegram_group_id"]
            else:
                streamer["telegram_group_id"] = dict()

            if is_registered:  # group is registered.
                self.sendBotMessageText(update, "Hai già registrato questo gruppo.")
                return None

            streamer["telegram_group_id"][str(chat_id)] = {
                "invitationLink": context.bot.exportChatInviteLink(chat_id),
                "isActive": True
            }

            if "groups" not in streamer:  # oh cool man, you're joining in a group for the first time and it is yours!
                streamer["groups"] = [chat_id]  # set up, let's update later with only one query.
            else:  # oh man, SUPER-COOL! You was already using Twitcham :O! Just check if you was in this group.
                if chat_id not in streamer["groups"]:  # TODO: is really necessary this if? boh
                    streamer["groups"].append(chat_id)  # wah O(1).

            if "group_users" not in streamer:
                streamer["group_users"] = dict()

            if "group_users" in streamer and str(chat_id) not in streamer["group_users"]:
                # if the streamer is creating the FIRST group, or is adding a NEW group so NO users yet registered.
                streamer["group_users"][str(chat_id)] = [
                    {
                        "telegram_id": from_id,
                        "twitch_id": streamer["twitch_id"]
                    }
                ]
            else:
                # this group already exists.
                act_group = streamer["group_users"][str(chat_id)]
                is_streamer_registered = list(filter(lambda group: group["telegram_id"] == from_id, act_group))
                if len(is_streamer_registered) <= 00:
                    # add the streamer to the group.
                    streamer["group_users"][str(chat_id)].append({
                        "telegram_id": from_id,
                        "twitch_id": streamer["twitch_id"]
                    })

            fields_to_update = {
                "telegram_group_id": streamer["telegram_group_id"],
                "groups": streamer["groups"],
                "group_users": streamer["group_users"],
                "telegram_group_active": True
            }

            self.update_user_by_telegram_id(users, from_id, fields_to_update)
            return True
        except Exception as e:
            self.logException(e)
            return self.sendBotMessageText(update, "Error while adding a new group.")

    def convert_telegram_group_to_list(self, update, streamer, from_id, users):
        try:
            # TODO: pass all users group_users to obj.
            current_telegram_group_id = streamer["telegram_group_id"]
            streamer["telegram_group_id"] = {
                str(current_telegram_group_id): {
                    "invitationLink": streamer["invitationLink"],
                    "isActive": streamer["telegram_group_active"]
                }
            }

            streamer["group_users"] = {
                str(current_telegram_group_id): streamer["group_users"]
            }

            fields_to_update = {
                "telegram_group_id": streamer["telegram_group_id"],
                "group_users": streamer["group_users"]
            }
            self.update_user_by_telegram_id(users, from_id, fields_to_update)
        except Exception as e:
            self.logException(e)
            return self.sendBotMessageText(update, "Error about registering a new group #1.")
