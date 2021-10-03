import os
import sys


class Core:

    def __init__(self, _users):
        self.users = _users  # database users table
        self.data_loaded = dict()

    @staticmethod
    def log_exception(e):
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(e, exc_type, fname, exc_tb.tb_lineno)

    @staticmethod
    def is_multi_group(group):
        """
        :param group: users object
        :return: boolean, True if is a multigroup else no.
        """
        return type(group["telegram_group_id"]).__name__ == "dict"

    def load_data(self):
        try:
            groups_list = self.users.find({"telegram_group_id": {"$exists": True}})  # load all groups.

            for group in groups_list:
                is_multi_group = self.is_multi_group(group)  # check if it is a multigroup


                if not is_multi_group:
                    continue  # skip this iteration if it is not a group.

                streamer_id = group["twitch_id"]  # get the streamer id.
                streamer_groups = group["telegram_group_id"]  # load streamer groups

                final_group_users = {}

                for sub_group in streamer_groups:
                    tmp_group = streamer_groups[str(sub_group)]  # data group.

                    if streamer_id not in self.data_loaded:  # if he wasn't initialized, initialize it now.
                        self.data_loaded[streamer_id] = {"users": [], "infos": {}}

                    if "automaticCheck" in tmp_group and tmp_group["automaticCheck"]:
                        # we have to add the users inside this group.
                        print("CONTROLLO: " + group["twitch_username"])
                        users_to_kick = None  # check if some user is to kick.
                        if "groups_users_to_kick" in group:
                            if group["groups_users_to_kick"] is not None and str(sub_group) in group["groups_users_to_kick"]:
                                users_to_kick = group["groups_users_to_kick"][str(sub_group)]

                        users_list = group["group_users"][str(sub_group)]  # prendo la lista di utenti
                        for user in users_list:

                            if user["telegram_id"] != group["telegram_id"]:

                                if user["telegram_id"] not in final_group_users:
                                    final_group_users[user["telegram_id"]] = []

                                data_to_append = {
                                    "group_id": sub_group, "twitch_id": user["twitch_id"], "telegram_id": user["telegram_id"]}  # queste sono le info da appendere alla lista utenti.
                                if users_to_kick is not None:
                                    data_to_append["kick_info"] = {
                                        "is_to_kick": str(user["telegram_id"]) in users_to_kick,
                                        "date": users_to_kick[str(user["telegram_id"])] if str(
                                            user["telegram_id"]) in users_to_kick else None}

                                final_group_users[user["telegram_id"]].append(data_to_append)

                self.data_loaded[streamer_id]["users"] = final_group_users
                self.data_loaded[streamer_id]["infos"]["access_token"] = group["access_token"]
                self.data_loaded[streamer_id]["infos"]["refresh_token"] = group["refresh_token"]
                self.data_loaded[streamer_id]["infos"]["telegram_id"] = group["telegram_id"]
                self.data_loaded[streamer_id]["infos"]["twitch_id"] = group["twitch_id"]
                self.data_loaded[streamer_id]["infos"]["kick_info"] = group[
                    "groups_users_to_kick"] if "groups_users_to_kick" in group else None
                self.data_loaded[streamer_id]["infos"]["telegram_group_id"] = group["telegram_group_id"]

            return self.data_loaded
        except Exception as e:
            self.log_exception(e)
