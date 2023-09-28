import io
import json
import logging
import os.path
import time
from os import listdir
from pathlib import Path
from re import split, sub
from threading import Thread, Event
from typing import Dict

import backoff
import urllib3
from deep_translator import GoogleTranslator as Translator
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaAudio
from telegram.constants import CHATACTION_TYPING
from telegram.error import BadRequest, NetworkError
from telegram.ext import (
    CallbackContext,
    Filters,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
)
from telegram.ext import Updater

try:
    import extensions.telegram_bot.source.text_process as tp
    import extensions.telegram_bot.source.const as const
    from extensions.telegram_bot.source.conf import Config
    from extensions.telegram_bot.source.user import TelegramBotUser as User
    from extensions.telegram_bot.source.silero import Silero as Silero
    from extensions.telegram_bot.source.sd_api import SdApi as SdApi
except ImportError:
    import source.text_process as tp
    import source.const as const
    from source.conf import Config
    from source.user import TelegramBotUser as User
    from source.silero import Silero as Silero
    from source.sd_api import SdApi as SdApi


class TelegramBotWrapper:
    # Config keeper
    cfg: Config = Config()

    # Set dummy obj for telegram updater
    updater: Updater = None

    # dict of User data dicts, here stored all users' session info.
    users: Dict[int, User] = {}

    def __init__(self, config_file_path="configs/app_config.json"):
        """Init telegram bot class. Use run_telegram_bot() to initiate bot.

        Args
            config_file_path: path to config file
        """
        # Set main config file
        self.config_file_path = config_file_path
        # Set internal config vars
        self.history_dir_path = "history"
        self.characters_dir_path = "characters"
        self.presets_dir_path = "presets"
        self.token_file_path = "telegram_token.txt"
        self.admins_file_path = "telegram_admins.txt"
        self.users_file_path = "telegram_users.txt"
        self.generator_params_file_path = "generator_params.json"
        self.user_rules_file_path = "telegram_user_rules.json"
        self.sd_api_url = "http://127.0.0.1:7860"
        self.sd_config_file_path = "sd_config.json"
        self.proxy_url = ""
        # Set bot mode
        self.bot_mode = "admin"
        self.user_name_template = ""  # template for username. "" - default (You), FIRSTNAME, LASTNAME, USERNAME, ID
        self.generator_script = ""  # mode loaded from config
        self.model_path = ""
        # Set default character json file
        self.default_char = "Example.yaml"
        self.default_preset = "LLaMA-Creative.txt"
        # Set translator
        self.model_lang = "en"
        self.user_lang = "en"
        # Load config_file_path if existed, overwrite current config vars
        self.load_config_file(self.config_file_path)
        # Load user generator parameters
        if os.path.exists(self.generator_params_file_path):
            with open(self.generator_params_file_path, "r") as params_file:
                self.generation_params = json.loads(params_file.read())
        else:
            logging.error("Cant find generator_params_file")
            self.generation_params = {}
        # Load preset
        self.load_preset(self.default_preset)
        # Load user rules
        if os.path.exists(self.user_rules_file_path):
            with open(self.user_rules_file_path, "r") as user_rules_file:
                self.user_rules = json.loads(user_rules_file.read())
        else:
            logging.error("Cant find user_rules_file_path: " + self.user_rules_file_path)
            self.user_rules = {}
        # Silero initiate
        self.silero = Silero()
        # SdApi initiate
        self.SdApi = SdApi(self.sd_api_url, self.sd_config_file_path)
        # generator initiate
        logging.info("Generator script: " + str(self.generator_script) + "\n" + json.dumps(self.generation_params))
        tp.generator_script.init(
            self.generator_script,
            self.model_path,
            n_ctx=self.generation_params.get("chat_prompt_size", 1024),
            n_gpu_layers=self.generation_params.get("n_gpu_layers", 0),
        )

    def load_config_file(self, config_file_path: str):
        if os.path.exists(config_file_path):
            with open(config_file_path, "r") as config_file_path:
                config = json.loads(config_file_path.read())
                self.bot_mode = config.get("bot_mode", self.bot_mode)
                self.user_name_template = config.get("user_name_template", self.user_name_template)
                self.generator_script = config.get("generator_script", self.generator_script)
                self.model_path = config.get("model_path", self.model_path)
                self.default_preset = config.get("default_preset", self.default_preset)
                self.default_char = config.get("default_char", self.default_char)
                self.model_lang = config.get("model_lang", self.model_lang)
                self.user_lang = config.get("user_lang", self.user_lang)
                self.characters_dir_path = config.get("characters_dir_path", self.characters_dir_path)
                self.presets_dir_path = config.get("presets_dir_path", self.presets_dir_path)
                self.history_dir_path = config.get("history_dir_path", self.history_dir_path)
                self.token_file_path = config.get("token_file_path", self.token_file_path)
                self.admins_file_path = config.get("admins_file_path", self.admins_file_path)
                self.users_file_path = config.get("users_file_path", self.users_file_path)
                self.generator_params_file_path = config.get(
                    "generator_params_file_path", self.generator_params_file_path
                )
                self.user_rules_file_path = config.get("user_rules_file_path", self.user_rules_file_path)
                self.sd_api_url = config.get("sd_api_url", self.sd_api_url)
                self.sd_config_file_path = config.get("sd_config_file_path", self.sd_config_file_path)
                self.cfg.translation_as_hidden_text = config.get(
                    "translation_as_hidden_text", self.cfg.translation_as_hidden_text
                )
                self.proxy_url = config.get("proxy_url", self.proxy_url)
        else:
            logging.error("Cant find config_file " + config_file_path)

    # =============================================================================
    # Run bot with token! Initiate updater obj!
    def run_telegram_bot(self, bot_token="", token_file_name=""):
        """
        Start the Telegram bot.
        :param bot_token: (str) The Telegram bot token. If not provided, try to read it from `token_file_name`.
        :param token_file_name: (str) The name of the file containing the bot token. Default is `None`.
        :return: None
        """
        request_kwargs = {
            "proxy_url": self.proxy_url,
        }
        if not bot_token:
            token_file_name = token_file_name or self.token_file_path
            with open(token_file_name, "r", encoding="utf-8") as f:
                bot_token = f.read().strip()
        self.updater = Updater(token=bot_token, use_context=True, request_kwargs=request_kwargs)
        self.updater.dispatcher.add_handler(CommandHandler("start", self.cb_start_command)),
        self.updater.dispatcher.add_handler(MessageHandler(Filters.text, self.cb_get_message))
        self.updater.dispatcher.add_handler(
            MessageHandler(
                Filters.document.mime_type("application/json"),
                self.cb_get_json_document,
            )
        )
        self.updater.dispatcher.add_handler(CallbackQueryHandler(self.cb_opt_button))
        self.updater.start_polling()
        Thread(target=self.no_sleep_callback).start()
        logging.info("Telegram bot started!" + str(self.updater))

    def no_sleep_callback(self):
        while True:
            try:
                self.updater.bot.send_message(chat_id=99999999999, text="One message every minute")
            except BadRequest:
                pass
            except Exception as error:
                logging.error(error)
            time.sleep(60)

    # =============================================================================
    # Handlers
    def cb_start_command(self, upd, context):
        Thread(target=self.thread_welcome_message, args=(upd, context)).start()

    def cb_get_message(self, upd, context):
        Thread(target=self.thread_get_message, args=(upd, context)).start()

    def cb_opt_button(self, upd, context):
        Thread(target=self.thread_push_button, args=(upd, context)).start()

    def cb_get_json_document(self, upd, context):
        Thread(target=self.thread_get_json_document, args=(upd, context)).start()

    # =============================================================================
    # Additional telegram actions
    def thread_welcome_message(self, upd: Update, context: CallbackContext):
        chat_id = upd.effective_chat.id
        if not self.check_user_permission(chat_id):
            return False
        self.init_check_user(chat_id)
        send_text = self.make_template_message("char_loaded", chat_id)
        context.bot.send_message(
            text=send_text,
            chat_id=chat_id,
            reply_markup=self.get_options_keyboard(chat_id),
            parse_mode="HTML",
        )

    def get_user_telegram_name(self, upd: Update) -> str:
        message = upd.message or upd.callback_query.message
        user_name = self.user_name_template.replace("FIRSTNAME", message.from_user.first_name or "")
        user_name = user_name.replace("LASTNAME", message.from_user.last_name or "")
        user_name = user_name.replace("USERNAME", message.from_user.username or "")
        user_name = user_name.replace("ID", str(message.from_user.id) or "")
        return user_name

    def make_template_message(self, request: str, chat_id: int, custom_string="") -> str:
        # create a message using default_messages_template or return
        # UNKNOWN_TEMPLATE
        if chat_id in self.users:
            user = self.users[chat_id]
            if request in const.DEFAULT_MESSAGE_TEMPLATE:
                msg = const.DEFAULT_MESSAGE_TEMPLATE[request]
                msg = msg.replace("_CHAT_ID_", str(chat_id))
                msg = msg.replace("_NAME1_", user.name1)
                msg = msg.replace("_NAME2_", user.name2)
                msg = msg.replace("_CONTEXT_", user.context)
                msg = msg.replace(
                    "_GREETING_",
                    self.prepare_text(user.greeting, user, "to_user"),
                )
                msg = msg.replace(
                    "_CUSTOM_STRING_",
                    self.prepare_text(custom_string, user, "to_user"),
                )
                msg = msg.replace("_OPEN_TAG_", self.cfg.html_tag[0])
                msg = msg.replace("_CLOSE_TAG_", self.cfg.html_tag[1])
                return msg
            else:
                return const.UNKNOWN_TEMPLATE
        else:
            return const.UNKNOWN_USER

    # =============================================================================
    # Work with history! Init/load/save functions
    def parse_characters_dir(self) -> list:
        char_list = []
        for f in listdir(self.characters_dir_path):
            if f.endswith((".json", ".yaml", ".yml")):
                char_list.append(f)
        return char_list

    def parse_presets_dir(self) -> list:
        preset_list = []
        for f in listdir(self.presets_dir_path):
            if f.endswith(".txt") or f.endswith(".yaml"):
                preset_list.append(f)
        return preset_list

    def init_check_user(self, chat_id):
        if chat_id not in self.users:
            # Load default
            self.users.update({chat_id: User()})
            self.users[chat_id].load_character_file(
                characters_dir_path=self.characters_dir_path,
                char_file=self.default_char,
            )
            self.users[chat_id].load_user_history(f"{self.history_dir_path}/{str(chat_id)}.json")
            self.users[chat_id].find_and_load_user_char_history(chat_id, self.history_dir_path)

    def thread_get_json_document(self, upd: Update, context: CallbackContext):
        chat_id = upd.message.chat.id
        user = self.users[chat_id]
        if not self.check_user_permission(chat_id):
            return False
        self.init_check_user(chat_id)
        default_user_file_path = str(Path(f"{self.history_dir_path}/{str(chat_id)}.json"))
        with open(default_user_file_path, "wb") as f:
            context.bot.get_file(upd.message.document.file_id).download(out=f)
        user.load_user_history(default_user_file_path)
        if len(user.history) > 0:
            last_message = user.history[-1]
        else:
            last_message = "<no message in history>"
        send_text = self.make_template_message("hist_loaded", chat_id, last_message)
        context.bot.send_message(
            chat_id=chat_id,
            text=send_text,
            reply_markup=self.get_options_keyboard(chat_id),
            parse_mode="HTML",
        )

    def start_send_typing_status(self, context: CallbackContext, chat_id: int) -> Event:
        typing_active = Event()
        typing_active.set()
        Thread(target=self.thread_typing_status, args=(context, chat_id, typing_active)).start()
        return typing_active

    def thread_typing_status(self, context: CallbackContext, chat_id: int, typing_active: Event):
        limit_counter = int(self.cfg.generation_timeout / 5)
        while typing_active.is_set() and limit_counter > 0:
            context.bot.send_chat_action(chat_id=chat_id, action=CHATACTION_TYPING)
            time.sleep(5)
            limit_counter -= 1

    def check_user_permission(self, chat_id):
        # Read admins list
        if os.path.exists(self.users_file_path):
            with open(self.users_file_path, "r") as users_file:
                users_list = users_file.read().split()
        else:
            users_list = []
        # check
        if str(chat_id) in users_list or len(users_list) == 0:
            return True
        else:
            return False

    def check_user_flood(self, user: User):
        if time.time() - self.cfg.flood_avoid_delay > user.last_msg_timestamp:
            user.last_msg_timestamp = time.time()
            return True
        else:
            return False

    def check_user_rule(self, chat_id, option):
        if os.path.exists(self.user_rules_file_path):
            with open(self.user_rules_file_path, "r") as user_rules_file:
                self.user_rules = json.loads(user_rules_file.read())
        option = sub(r"[0123456789-]", "", option)
        if option.endswith(const.BTN_OPTION):
            option = const.BTN_OPTION
        # Read admins list
        if os.path.exists(self.admins_file_path):
            with open(self.admins_file_path, "r") as admins_file:
                admins_list = admins_file.read().split()
        else:
            admins_list = []
        # check admin rules
        if str(chat_id) in admins_list or self.bot_mode == const.MODE_ADMIN:
            return bool(self.user_rules[option][const.MODE_ADMIN])
        else:
            return bool(self.user_rules[option][self.bot_mode])

    # =============================================================================
    # answer generator

    def prepare_text(self, original_text: str, user: User, direction="to_user"):
        text = original_text
        # translate
        if self.model_lang != user.language:
            try:
                if direction == "to_model":
                    text = Translator(source=user.language, target=self.model_lang).translate(text)
                elif direction == "to_user":
                    text = Translator(source=self.model_lang, target=user.language).translate(text)
            except Exception as e:
                text = "can't translate text:" + str(text)
                logging.error("translator_error" + str(e))
        # Add HTML tags and other...
        if direction not in ["to_model", "no_html"]:
            text = text.replace("#", "&#35;").replace("<", "&#60;").replace(">", "&#62;")
            original_text = original_text.replace("#", "&#35;").replace("<", "&#60;").replace(">", "&#62;")
            if self.model_lang != user.language and direction == "to_user" \
                    and self.cfg.translation_as_hidden_text == "on":
                text = (
                        self.cfg.html_tag[0]
                        + original_text
                        + self.cfg.html_tag[1]
                        + "\n"
                        + self.cfg.translate_html_tag[0]
                        + text
                        + self.cfg.translate_html_tag[1]
                )
            else:
                text = self.cfg.html_tag[0] + text + self.cfg.html_tag[1]
        return text

    @backoff.on_exception(
        backoff.expo,
        (urllib3.exceptions.HTTPError, urllib3.exceptions.ConnectTimeoutError, NetworkError),
        max_time=60,
    )
    def send_sd_image(self, upd: Update, context: CallbackContext, answer, user_text):
        chat_id = upd.message.chat.id
        user = self.users[chat_id]
        try:
            file_list = self.SdApi.txt_to_image(answer)
            answer = answer.replace(self.cfg.sd_api_prompt_of.replace("OBJECT", user_text[1:].strip()), "")
            for char in ["[", "]", "{", "}", "(", ")", "*", '"', "'"]:
                answer = answer.replace(char, "")
            answer = self.prepare_text(answer, user)
            if len(file_list) > 0:
                for image_path in file_list:
                    if os.path.exists(image_path):
                        with open(image_path, "rb") as image_file:
                            context.bot.send_photo(caption=answer, chat_id=chat_id, photo=image_file)
                        os.remove(image_path)
        except Exception as e:
            logging.error("send_sd_image: " + str(e))
            context.bot.send_message(text=answer, chat_id=chat_id)

    @backoff.on_exception(
        backoff.expo,
        (urllib3.exceptions.HTTPError, urllib3.exceptions.ConnectTimeoutError, NetworkError),
        max_time=60,
    )
    def clean_last_message_markup(self, context: CallbackContext, chat_id: int):
        if chat_id in self.users and len(self.users[chat_id].msg_id) > 0:
            last_msg = self.users[chat_id].msg_id[-1]
            try:
                context.bot.editMessageReplyMarkup(chat_id=chat_id, message_id=last_msg, reply_markup=None)
            except Exception as exception:
                logging.error("last_message_markup_clean: " + str(exception))

    @backoff.on_exception(
        backoff.expo,
        (urllib3.exceptions.HTTPError, urllib3.exceptions.ConnectTimeoutError, NetworkError),
        max_time=60,
    )
    def send_message(self, context: CallbackContext, chat_id: int, text: str):
        user = self.users[chat_id]
        text = self.prepare_text(text, user, "to_user")
        if user.silero_speaker == "None" or user.silero_model_id == "None":
            message = context.bot.send_message(
                text=text,
                chat_id=chat_id,
                parse_mode="HTML",
                reply_markup=self.get_chat_keyboard(),
            )
            return message
        else:
            if ":" in text:
                audio_text = ":".join(text.split(":")[1:])
            else:
                audio_text = text
            audio_path = self.silero.get_audio(text=audio_text, user_id=chat_id, user=user)
            if audio_path is not None:
                with open(audio_path, "rb") as audio:
                    message = context.bot.send_audio(
                        chat_id=chat_id,
                        audio=audio,
                        caption=text,
                        filename=f"{user.name2}_to_{user.name1}.wav",
                        parse_mode="HTML",
                        reply_markup=self.get_chat_keyboard(),
                    )
            else:
                message = context.bot.send_message(
                    text=text,
                    chat_id=chat_id,
                    parse_mode="HTML",
                    reply_markup=self.get_chat_keyboard(),
                )
                return message
            return message

    @backoff.on_exception(
        backoff.expo,
        (urllib3.exceptions.HTTPError, urllib3.exceptions.ConnectTimeoutError, NetworkError),
        max_time=60,
    )
    def edit_message(
            self,
            context: CallbackContext,
            upd: Update,
            chat_id: int,
            text: str,
            message_id: int,
    ):
        user = self.users[chat_id]
        text = self.prepare_text(text, user, "to_user")
        if upd.callback_query.message.text is not None:
            context.bot.editMessageText(
                text=text,
                chat_id=chat_id,
                parse_mode="HTML",
                message_id=message_id,
                reply_markup=self.get_chat_keyboard(),
            )
        if (
                upd.callback_query.message.audio is not None
                and user.silero_speaker != "None"
                and user.silero_model_id != "None"
        ):
            if ":" in text:
                audio_text = ":".join(text.split(":")[1:])
            else:
                audio_text = text
            audio_path = self.silero.get_audio(text=audio_text, user_id=chat_id, user=user)
            if audio_path is not None:
                with open(audio_path, "rb") as audio:
                    media = InputMediaAudio(media=audio, filename=f"{user.name2}_to_{user.name1}.wav")
                    context.bot.edit_message_media(
                        chat_id=chat_id,
                        media=media,
                        message_id=message_id,
                        reply_markup=self.get_chat_keyboard(),
                    )
        if upd.callback_query.message.caption is not None:
            context.bot.editMessageCaption(
                chat_id=chat_id,
                caption=text,
                parse_mode="HTML",
                message_id=message_id,
                reply_markup=self.get_chat_keyboard(),
            )

    # =============================================================================
    # Message handler
    def thread_get_message(self, upd: Update, context: CallbackContext):
        # Extract user input and chat ID
        user_text = upd.message.text
        chat_id = upd.message.chat.id
        self.init_check_user(chat_id)
        user = self.users[chat_id]
        if not self.check_user_permission(chat_id):
            return False
        if not self.check_user_flood(user):
            return False
        # Send "typing" message
        typing = self.start_send_typing_status(context, chat_id)
        try:
            if self.check_user_rule(chat_id=chat_id, option=const.GET_MESSAGE) is not True:
                return False
            # Generate answer and replace "typing" message with it
            if user_text not in self.cfg.sd_api_prefixes:
                user_text = self.prepare_text(user_text, user, "to_model")
            answer, system_message = tp.generate_answer(text_in=user_text, user=user, bot_mode=self.bot_mode,
                                                        generation_params=self.generation_params, cfg=self.cfg,
                                                        name_in=self.get_user_telegram_name(upd))
            if system_message == const.MSG_SYSTEM:
                context.bot.send_message(text=answer, chat_id=chat_id)
            elif system_message == const.MSG_SD_API:
                self.send_sd_image(upd, context, answer, user_text)
            else:
                if system_message == const.MSG_DEL_LAST:
                    context.bot.deleteMessage(chat_id=chat_id, message_id=user.msg_id[-1])
                message = self.send_message(text=answer, chat_id=chat_id, context=context)
                # Clear buttons on last message (if they exist in current
                # thread)
                self.clean_last_message_markup(context, chat_id)
                # Add message ID to message history
                user.msg_id.append(message.message_id)
                # Save user history
                user.save_user_history(chat_id, self.history_dir_path)
        except Exception as e:
            logging.error(str(e))
            raise e
        finally:
            typing.clear()

    # =============================================================================
    # button
    def thread_push_button(self, upd: Update, context: CallbackContext):
        upd.callback_query.answer()
        chat_id = upd.callback_query.message.chat.id
        msg_id = upd.callback_query.message.message_id
        option = upd.callback_query.data
        if not self.check_user_permission(chat_id):
            return False
        # Send "typing" message
        typing = self.start_send_typing_status(context, chat_id)
        try:
            if chat_id not in self.users:
                self.init_check_user(chat_id)
            if msg_id not in self.users[chat_id].msg_id and option in [
                const.BTN_NEXT,
                const.BTN_CONTINUE,
                const.BTN_DEL_WORD,
                const.BTN_REGEN,
                const.BTN_CUTOFF,
            ]:
                send_text = self.make_template_message("mem_lost", chat_id)
                context.bot.editMessageText(
                    text=send_text,
                    chat_id=chat_id,
                    message_id=msg_id,
                    reply_markup=None,
                    parse_mode="HTML",
                )
            else:
                self.handle_button_option(option, chat_id, upd, context)
                self.users[chat_id].save_user_history(chat_id, self.history_dir_path)
        except Exception as e:
            logging.error("thread_push_button " + str(e))
        finally:
            typing.clear()

    def handle_button_option(self, option, chat_id, upd, context):
        if option == const.BTN_RESET and self.check_user_rule(chat_id, option):
            self.on_reset_history_button(upd=upd, context=context)
        elif option == const.BTN_CONTINUE and self.check_user_rule(chat_id, option):
            self.on_continue_message_button(upd=upd, context=context)
        elif option == const.BTN_IMPERSONATE and self.check_user_rule(chat_id, option):
            self.on_impersonate_button(upd=upd, context=context)
        elif option == const.BTN_NEXT and self.check_user_rule(chat_id, option):
            self.on_next_message_button(upd=upd, context=context)
        elif option == const.BTN_DEL_WORD and self.check_user_rule(chat_id, option):
            self.on_delete_word_button(upd=upd, context=context)
        elif option == const.BTN_REGEN and self.check_user_rule(chat_id, option):
            self.on_regenerate_message_button(upd=upd, context=context)
        elif option == const.BTN_CUTOFF and self.check_user_rule(chat_id, option):
            self.on_cutoff_message_button(upd=upd, context=context)
        elif option == const.BTN_DOWNLOAD and self.check_user_rule(chat_id, option):
            self.on_download_json_button(upd=upd, context=context)
        elif option == const.BTN_OPTION and self.check_user_rule(chat_id, option):
            self.show_options_button(upd=upd, context=context)
        elif option == const.BTN_DELETE and self.check_user_rule(chat_id, option):
            self.on_delete_pressed_button(upd=upd, context=context)
        elif option.startswith(const.BTN_CHAR_LIST) and self.check_user_rule(chat_id, option):
            self.keyboard_characters_button(upd=upd, context=context, option=option)
        elif option.startswith(const.BTN_CHAR_LOAD) and self.check_user_rule(chat_id, option):
            self.load_character_button(upd=upd, context=context, option=option)
        elif option.startswith(const.BTN_PRESET_LIST) and self.check_user_rule(chat_id, option):
            self.keyboard_presets_button(upd=upd, context=context, option=option)
        elif option.startswith(const.BTN_PRESET_LOAD) and self.check_user_rule(chat_id, option):
            self.load_presets_button(upd=upd, context=context, option=option)
        elif option.startswith(const.BTN_MODEL_LIST) and self.check_user_rule(chat_id, option):
            self.on_keyboard_models_button(upd=upd, context=context, option=option)
        elif option.startswith(const.BTN_MODEL_LOAD) and self.check_user_rule(chat_id, option):
            self.on_load_model_button(upd=upd, context=context, option=option)
        elif option.startswith(const.BTN_LANG_LIST) and self.check_user_rule(chat_id, option):
            self.on_keyboard_language_button(upd=upd, context=context, option=option)
        elif option.startswith(const.BTN_LANG_LOAD) and self.check_user_rule(chat_id, option):
            self.on_load_language_button(upd=upd, context=context, option=option)
        elif option.startswith(const.BTN_VOICE_LIST) and self.check_user_rule(chat_id, option):
            self.on_keyboard_voice_button(upd=upd, context=context, option=option)
        elif option.startswith(const.BTN_VOICE_LOAD) and self.check_user_rule(chat_id, option):
            self.on_load_voice_button(upd=upd, context=context, option=option)

    def show_options_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        history_tokens = -1
        context_tokens = -1
        greeting_tokens = -1
        try:
            history_tokens = tp.generator_script.get_tokens_count("\n".join(user.history))
            context_tokens = tp.generator_script.get_tokens_count("\n".join(user.context))
            greeting_tokens = tp.generator_script.get_tokens_count("\n".join(user.greeting))
        except Exception as e:
            logging.error("options_button tokens_count" + str(e))

        send_text = f"""{user.name2} ({user.char_file}),
Conversation length: {str(len(user.history))} messages, ({history_tokens} tokens).
Context:{context_tokens}, greeting:{greeting_tokens} tokens.
Voice: {user.silero_speaker}
Language: {user.language}"""
        context.bot.send_message(
            text=send_text,
            chat_id=chat_id,
            reply_markup=self.get_options_keyboard(chat_id),
            parse_mode="HTML",
        )

    @staticmethod
    def on_delete_pressed_button(upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        message_id = upd.callback_query.message.message_id
        context.bot.deleteMessage(chat_id=chat_id, message_id=message_id)

    def on_impersonate_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        self.clean_last_message_markup(context, chat_id)
        answer, _ = tp.generate_answer(text_in=const.GENERATOR_MODE_IMPERSONATE, user=user, bot_mode=self.bot_mode,
                                       generation_params=self.generation_params, cfg=self.cfg,
                                       name_in=self.get_user_telegram_name(upd))
        message = self.send_message(text=answer, chat_id=chat_id, context=context)
        user.msg_id.append(message.message_id)
        user.save_user_history(chat_id, self.history_dir_path)

    def on_next_message_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        self.clean_last_message_markup(context, chat_id)
        answer, _ = tp.generate_answer(text_in=const.GENERATOR_MODE_NEXT, user=user, bot_mode=self.bot_mode,
                                       generation_params=self.generation_params, cfg=self.cfg,
                                       name_in=self.get_user_telegram_name(upd))
        message = self.send_message(text=answer, chat_id=chat_id, context=context)
        user.msg_id.append(message.message_id)
        user.save_user_history(chat_id, self.history_dir_path)

    def on_continue_message_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        message = upd.callback_query.message
        user = self.users[chat_id]
        # get answer and replace message text!
        answer, _ = tp.generate_answer(text_in=const.GENERATOR_MODE_CONTINUE, user=user, bot_mode=self.bot_mode,
                                       generation_params=self.generation_params, cfg=self.cfg,
                                       name_in=self.get_user_telegram_name(upd))
        self.edit_message(
            text=answer,
            chat_id=chat_id,
            message_id=message.message_id,
            context=context,
            upd=upd,
        )
        user.change_last_message(history_answer=answer)
        user.save_user_history(chat_id, self.history_dir_path)

    def on_delete_word_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]

        # get and change last message
        last_message = user.history[-1]
        last_word = split(r"\n+| +", last_message)[-1]
        if len(last_word) == 0:
            last_word = " "
        new_last_message = last_message[: -(len(last_word))]
        new_last_message = new_last_message.strip()
        # If there is previous message - add buttons to previous message
        if user.msg_id:
            self.edit_message(
                text=new_last_message,
                chat_id=chat_id,
                message_id=user.msg_id[-1],
                context=context,
                upd=upd,
            )
        user.change_last_message(history_answer=new_last_message)
        user.save_user_history(chat_id, self.history_dir_path)

    def on_regenerate_message_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        user = self.users[chat_id]
        # get answer and replace message text!
        answer, _ = tp.generate_answer(text_in=const.GENERATOR_MODE_REGENERATE, user=user, bot_mode=self.bot_mode,
                                       generation_params=self.generation_params, cfg=self.cfg,
                                       name_in=self.get_user_telegram_name(upd))
        self.edit_message(
            text=answer,
            chat_id=chat_id,
            message_id=msg.message_id,
            context=context,
            upd=upd,
        )
        user.save_user_history(chat_id, self.history_dir_path)

    def on_cutoff_message_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        # Edit or delete last message ID (strict lines)
        last_msg_id = user.msg_id[-1]
        context.bot.deleteMessage(chat_id=chat_id, message_id=last_msg_id)
        # Remove last message and bot answer from history
        user.truncate_last_mesage()
        # If there is previous message - add buttons to previous message
        if user.msg_id:
            message_id = user.msg_id[-1]
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=self.get_chat_keyboard(),
            )
        user.save_user_history(chat_id, self.history_dir_path)

    def on_download_json_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id

        if chat_id not in self.users:
            return

        user_file = io.StringIO(self.users[chat_id].to_json())
        send_caption = self.make_template_message("hist_to_chat", chat_id)
        context.bot.send_document(
            chat_id=chat_id,
            caption=send_caption,
            document=user_file,
            filename=self.users[chat_id].name2 + ".json",
        )

    def on_reset_history_button(self, upd: Update, context: CallbackContext):
        # check if it is a callback_query or a command
        if upd.callback_query:
            chat_id = upd.callback_query.message.chat.id
        else:
            chat_id = upd.message.chat.id
        if chat_id not in self.users:
            return
        user = self.users[chat_id]
        if user.msg_id:
            self.clean_last_message_markup(context, chat_id)
        user.reset()
        user.load_character_file(self.characters_dir_path, user.char_file)
        send_text = self.make_template_message("mem_reset", chat_id)
        context.bot.send_message(
            chat_id=chat_id,
            text=send_text,
            reply_markup=self.get_options_keyboard(chat_id),
            parse_mode="HTML",
        )

    # =============================================================================
    # switching keyboard
    def on_load_model_button(self, upd: Update, context: CallbackContext, option: str):
        if tp.generator_script.get_model_list is not None:
            model_list = tp.generator_script.get_model_list()
            model_file = model_list[int(option.replace(const.BTN_MODEL_LOAD, ""))]
            chat_id = upd.effective_chat.id
            send_text = "Loading " + model_file + ". 🪄"
            message_id = upd.callback_query.message.message_id
            context.bot.editMessageText(
                text=send_text,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML",
            )
            try:
                tp.generator_script.load_model(model_file)
                send_text = self.make_template_message(
                    request="model_loaded", chat_id=chat_id, custom_string=model_file
                )
                context.bot.editMessageText(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=send_text,
                    parse_mode="HTML",
                    reply_markup=self.get_options_keyboard(chat_id),
                )
            except Exception as e:
                logging.error("model button error: " + str(e))
                context.bot.editMessageText(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="Error during " + model_file + " loading. ⛔",
                    parse_mode="HTML",
                    reply_markup=self.get_options_keyboard(chat_id),
                )
                raise e

    def on_keyboard_models_button(self, upd: Update, context: CallbackContext, option: str):
        if tp.generator_script.get_model_list() is not None:
            chat_id = upd.callback_query.message.chat.id
            msg = upd.callback_query.message
            model_list = tp.generator_script.get_model_list()
            if option == const.BTN_MODEL_LIST + const.BTN_OPTION:
                context.bot.editMessageReplyMarkup(
                    chat_id=chat_id,
                    message_id=msg.message_id,
                    reply_markup=self.get_options_keyboard(chat_id),
                )
                return
            shift = int(option.replace(const.BTN_MODEL_LIST, ""))
            characters_buttons = self.get_switch_keyboard(
                opt_list=model_list,
                shift=shift,
                data_list=const.BTN_MODEL_LIST,
                data_load=const.BTN_MODEL_LOAD,
            )
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id,
                message_id=msg.message_id,
                reply_markup=characters_buttons,
            )

    def load_presets_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        preset_char_num = int(option.replace(const.BTN_PRESET_LOAD, ""))
        self.default_preset = self.parse_presets_dir()[preset_char_num]
        self.load_preset(preset=self.default_preset)
        user = self.users[chat_id]
        send_text = f"""{user.name2},
        Conversation length{str(len(user.history))} messages.
        Voice: {user.silero_speaker}
        Language: {user.language}
        New preset: {self.default_preset}"""
        message_id = upd.callback_query.message.message_id
        context.bot.editMessageText(
            text=send_text,
            message_id=message_id,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=self.get_options_keyboard(chat_id),
        )

    def load_preset(self, preset):
        preset_path = self.presets_dir_path + "/" + preset
        if os.path.exists(preset_path):
            with open(preset_path, "r") as preset_file:
                for line in preset_file.readlines():
                    name, value = line.replace("\n", "").replace("\r", "").replace(": ", "=").split("=")
                    if name in self.generation_params:
                        if type(self.generation_params[name]) == int:
                            self.generation_params[name] = int(float(value))
                        elif type(self.generation_params[name]) == float:
                            self.generation_params[name] = float(value)
                        elif type(self.generation_params[name]) == str:
                            self.generation_params[name] = str(value)
                        elif type(self.generation_params[name]) == bool:
                            self.generation_params[name] = bool(value)
                        elif type(self.generation_params[name]) == list:
                            self.generation_params[name] = list(value.split(","))

    def keyboard_presets_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        #  if "return char markup" button - clear markup
        if option == const.BTN_PRESET_LIST + const.BTN_OPTION:
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id,
                message_id=msg.message_id,
                reply_markup=self.get_options_keyboard(chat_id),
            )
            return
        #  get keyboard list shift
        shift = int(option.replace(const.BTN_PRESET_LIST, ""))
        preset_list = self.parse_presets_dir()
        characters_buttons = self.get_switch_keyboard(
            opt_list=preset_list,
            shift=shift,
            data_list=const.BTN_PRESET_LIST,
            data_load=const.BTN_PRESET_LOAD,
            keyboard_colum=3,
        )
        context.bot.editMessageReplyMarkup(chat_id=chat_id, message_id=msg.message_id, reply_markup=characters_buttons)

    def load_character_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        char_num = int(option.replace(const.BTN_CHAR_LOAD, ""))
        char_list = self.parse_characters_dir()
        self.clean_last_message_markup(context, chat_id)
        self.init_check_user(chat_id)
        char_file = char_list[char_num]
        self.users[chat_id].load_character_file(characters_dir_path=self.characters_dir_path, char_file=char_file)
        #  If there was conversation with this char - load history
        self.users[chat_id].find_and_load_user_char_history(chat_id, self.history_dir_path)
        if len(self.users[chat_id].history) > 0:
            send_text = self.make_template_message("hist_loaded", chat_id, self.users[chat_id].history[-1])
        else:
            send_text = self.make_template_message("char_loaded", chat_id)
        context.bot.send_message(
            text=send_text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=self.get_options_keyboard(chat_id),
        )

    def keyboard_characters_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        #  if "return char markup" button - clear markup
        if option == const.BTN_CHAR_LIST + const.BTN_OPTION:
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id,
                message_id=msg.message_id,
                reply_markup=self.get_options_keyboard(chat_id),
            )
            return
        #  get keyboard list shift
        shift = int(option.replace(const.BTN_CHAR_LIST, ""))
        char_list = self.parse_characters_dir()
        if shift == -9999 and self.users[chat_id].char_file in char_list:
            shift = char_list.index(self.users[chat_id].char_file)
        #  create chars list
        characters_buttons = self.get_switch_keyboard(
            opt_list=char_list,
            shift=shift,
            data_list=const.BTN_CHAR_LIST,
            data_load=const.BTN_CHAR_LOAD,
        )
        context.bot.editMessageReplyMarkup(chat_id=chat_id, message_id=msg.message_id, reply_markup=characters_buttons)

    def on_load_language_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        lang_num = int(option.replace(const.BTN_LANG_LOAD, ""))
        language = list(self.cfg.language_dict.keys())[lang_num]
        self.users[chat_id].language = language
        send_text = f"""{user.name2},
        Conversation length{str(len(user.history))} messages.
        Voice: {user.silero_speaker}
        Language: {user.language} (NEW)"""
        message_id = upd.callback_query.message.message_id
        context.bot.editMessageText(
            text=send_text,
            message_id=message_id,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=self.get_options_keyboard(chat_id),
        )

    def on_keyboard_language_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        #  if "return char markup" button - clear markup
        if option == const.BTN_LANG_LIST + const.BTN_OPTION:
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id,
                message_id=msg.message_id,
                reply_markup=self.get_options_keyboard(chat_id),
            )
            return
        #  get keyboard list shift
        shift = int(option.replace(const.BTN_LANG_LIST, ""))
        #  create list
        lang_buttons = self.get_switch_keyboard(
            opt_list=list(self.cfg.language_dict.keys()),
            shift=shift,
            data_list=const.BTN_LANG_LIST,
            data_load=const.BTN_LANG_LOAD,
            keyboard_colum=4,
        )
        context.bot.editMessageReplyMarkup(chat_id=chat_id, message_id=msg.message_id, reply_markup=lang_buttons)

    def on_load_voice_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        male = Silero.voices[user.language]["male"]
        female = Silero.voices[user.language]["female"]
        voice_dict = ["None"] + male + female
        voice_num = int(option.replace(const.BTN_VOICE_LOAD, ""))
        user.silero_speaker = voice_dict[voice_num]
        user.silero_model_id = Silero.voices[user.language]["model"]
        send_text = f"""{user.name2},
        Conversation length{str(len(user.history))} messages.
        Voice: {user.silero_speaker} (NEW)
        Language: {user.language}"""
        message_id = upd.callback_query.message.message_id
        context.bot.editMessageText(
            text=send_text,
            message_id=message_id,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=self.get_options_keyboard(chat_id),
        )

    def on_keyboard_voice_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        #  if "return char markup" button - clear markup
        if option == const.BTN_VOICE_LIST + const.BTN_OPTION:
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id,
                message_id=msg.message_id,
                reply_markup=self.get_options_keyboard(chat_id),
            )
            return
        #  get keyboard list shift
        shift = int(option.replace(const.BTN_VOICE_LIST, ""))
        #  create list
        user = self.users[chat_id]
        male = list(map(lambda x: x + "🚹", Silero.voices[user.language]["male"]))
        female = list(map(lambda x: x + "🚺", Silero.voices[user.language]["female"]))
        voice_dict = ["🔇None"] + male + female
        voice_buttons = self.get_switch_keyboard(
            opt_list=list(voice_dict),
            shift=shift,
            data_list=const.BTN_VOICE_LIST,
            data_load=const.BTN_VOICE_LOAD,
            keyboard_colum=4,
        )
        context.bot.editMessageReplyMarkup(chat_id=chat_id, message_id=msg.message_id, reply_markup=voice_buttons)

    # =============================================================================
    # load characters char_file from ./characters

    def get_options_keyboard(self, chat_id=0):
        keyboard_raw = []
        # get language
        if chat_id in self.users:
            language = self.users[chat_id].language
        else:
            language = "en"
        language_flag = self.cfg.language_dict[language]
        # get voice
        if chat_id in self.users:
            voice_str = self.users[chat_id].silero_speaker
            if voice_str == "None":
                voice = "🔇"
            else:
                voice = "🔈"
        else:
            voice = "🔇"

        if self.check_user_rule(chat_id, const.BTN_DOWNLOAD):
            keyboard_raw.append(InlineKeyboardButton(text="💾Save", callback_data=const.BTN_DOWNLOAD))
        # if self.check_user_rule(chat_id, const.BTN_LORE):
        #    keyboard_raw.append(InlineKeyboardButton(
        #        text="📜Lore", callback_data=const.BTN_LORE))
        if self.check_user_rule(chat_id, const.BTN_CHAR_LIST):
            keyboard_raw.append(InlineKeyboardButton(text="🎭Chars", callback_data=const.BTN_CHAR_LIST + "-9999"))
        if self.check_user_rule(chat_id, const.BTN_RESET):
            keyboard_raw.append(InlineKeyboardButton(text="⚠Reset", callback_data=const.BTN_RESET))
        if self.check_user_rule(chat_id, const.BTN_LANG_LIST):
            keyboard_raw.append(
                InlineKeyboardButton(
                    text=language_flag + "Language",
                    callback_data=const.BTN_LANG_LIST + "0",
                )
            )
        if self.check_user_rule(chat_id, const.BTN_VOICE_LIST):
            keyboard_raw.append(InlineKeyboardButton(text=voice + "Voice", callback_data=const.BTN_VOICE_LIST + "0"))
        if self.check_user_rule(chat_id, const.BTN_PRESET_LIST) and tp.generator_script.generator.preset_change_allowed:
            keyboard_raw.append(InlineKeyboardButton(text="🔧Presets", callback_data=const.BTN_PRESET_LIST + "0"))
        if self.check_user_rule(chat_id, const.BTN_MODEL_LIST) and tp.generator_script.generator.model_change_allowed:
            keyboard_raw.append(InlineKeyboardButton(text="🔨Model", callback_data=const.BTN_MODEL_LIST + "0"))
        if self.check_user_rule(chat_id, const.BTN_DELETE):
            keyboard_raw.append(InlineKeyboardButton(text="❌Close", callback_data=const.BTN_DELETE))
        return InlineKeyboardMarkup([keyboard_raw])

    def get_chat_keyboard(self, chat_id=0):
        keyboard_raw = []
        if self.check_user_rule(chat_id, const.BTN_IMPERSONATE):
            keyboard_raw.append(InlineKeyboardButton(text="🥸Impersonate", callback_data=const.BTN_IMPERSONATE))
        if self.check_user_rule(chat_id, const.BTN_NEXT):
            keyboard_raw.append(InlineKeyboardButton(text="▶Next", callback_data=const.BTN_NEXT))
        if self.check_user_rule(chat_id, const.BTN_CONTINUE):
            keyboard_raw.append(InlineKeyboardButton(text="➡Continue", callback_data=const.BTN_CONTINUE))
        if self.check_user_rule(chat_id, const.BTN_DEL_WORD):
            keyboard_raw.append(InlineKeyboardButton(text="⬅Del word", callback_data=const.BTN_DEL_WORD))
        if self.check_user_rule(chat_id, const.BTN_REGEN):
            keyboard_raw.append(InlineKeyboardButton(text="♻Regenerate", callback_data=const.BTN_REGEN))
        if self.check_user_rule(chat_id, const.BTN_CUTOFF):
            keyboard_raw.append(InlineKeyboardButton(text="✖Cutoff", callback_data=const.BTN_CUTOFF))
        if self.check_user_rule(chat_id, const.BTN_OPTION):
            keyboard_raw.append(InlineKeyboardButton(text="⚙Options", callback_data=const.BTN_OPTION))
        return InlineKeyboardMarkup([keyboard_raw])

    def get_switch_keyboard(
            self,
            opt_list: list,
            shift: int,
            data_list: str,
            data_load: str,
            keyboard_rows=6,
            keyboard_colum=2,
    ):
        # find shift
        opt_list_length = len(opt_list)
        keyboard_length = keyboard_rows * keyboard_colum
        if shift >= opt_list_length - keyboard_length:
            shift = opt_list_length - keyboard_length
        if shift < 0:
            shift = 0
        # append list
        characters_buttons = []
        column = 0
        for i in range(shift, keyboard_length + shift):
            if i >= len(opt_list):
                break
            if column == 0:
                characters_buttons.append([])
            column += 1
            if column >= keyboard_colum:
                column = 0
            characters_buttons[-1].append(
                InlineKeyboardButton(text=f"{opt_list[i]}", callback_data=f"{data_load}{str(i)}")
            )
            i += 1
        # add switch buttons
        begin_shift = 0
        l_shift = shift - keyboard_length
        l_shift3 = shift - keyboard_length * 3
        r_shift = shift + keyboard_length
        r_shift3 = shift + keyboard_length * 3
        end_shift = opt_list_length - keyboard_length
        switch_buttons = [
            InlineKeyboardButton(text="⏮", callback_data=data_list + str(begin_shift)),
            InlineKeyboardButton(text="⏪", callback_data=data_list + str(l_shift3)),
            InlineKeyboardButton(text="◀", callback_data=data_list + str(l_shift)),
            InlineKeyboardButton(text="🔺", callback_data=data_list + const.BTN_OPTION),
            InlineKeyboardButton(text="▶", callback_data=data_list + str(r_shift)),
            InlineKeyboardButton(text="⏩", callback_data=data_list + str(r_shift3)),
            InlineKeyboardButton(text="⏭", callback_data=data_list + str(end_shift)),
        ]
        characters_buttons.append(switch_buttons)
        # add new keyboard to message!
        return InlineKeyboardMarkup(characters_buttons)
