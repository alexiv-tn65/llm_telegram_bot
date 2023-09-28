import json
import logging
from threading import Lock
from typing import Tuple, Dict

try:
    from extensions.telegram_bot.source.user import TelegramBotUser as User
    from extensions.telegram_bot.source.generator import generator as generator_script
    import extensions.telegram_bot.source.const as const
    from extensions.telegram_bot.source.conf import Config
except ImportError:
    from source.user import TelegramBotUser as User
    from source import generator as generator_script
    import source.const as const
    from source.conf import Config

# Define generator lock to prevent GPU overloading
generator_lock = Lock()


def generate_answer(text_in: str,
                    user: User,
                    bot_mode: str,
                    generation_params: Dict,
                    cfg: Config,
                    name_in="") -> Tuple[str, str]:
    # if generation will fail, return "fail" answer
    answer = const.GENERATOR_FAIL
    # default result action - message
    return_msg_action = const.MSG_SEND
    # if user is default equal to user1
    name_in = user.name1 if name_in == "" else name_in
    # acquire generator lock if we can
    generator_lock.acquire(timeout=cfg.generation_timeout)

    # user_input preprocessing
    try:
        # Preprocessing: actions which return result immediately:
        if text_in[:2] in cfg.permanent_change_name2_prefixes:

            # If user_in starts with perm_prefix - just replace name2
            user.name2 = text_in[2:]
            return_msg_action = const.MSG_SYSTEM
            generator_lock.release()
            return "New bot name: " + user.name2, return_msg_action
        if text_in[:2] in cfg.permanent_change_name1_prefixes:
            # If user_in starts with perm_prefix - just replace name2
            user.name1 = text_in[2:]
            return_msg_action = const.MSG_SYSTEM
            generator_lock.release()
            return "New user name: " + user.name1, return_msg_action
        if text_in[:2] in cfg.permanent_add_context_prefixes:
            # If user_in starts with perm_prefix - just replace name2
            user.context += "\n" + text_in[2:]
            return_msg_action = const.MSG_SYSTEM
            generator_lock.release()
            return "Added to context: " + text_in[2:], return_msg_action
        if text_in[0] in cfg.replace_prefixes:
            # If user_in starts with replace_prefix - fully replace last
            # message
            user.history[-1] = text_in[1:]
            return_msg_action = const.MSG_DEL_LAST
            generator_lock.release()
            return user.history[-1], return_msg_action

        # Preprocessing: actions which not depends on user input:
        if bot_mode in [const.MODE_QUERY]:
            user.history = []

        # Preprocessing: add user_in/names/whitespaces to history in right order depends on mode:

        if bot_mode in [const.MODE_NOTEBOOK]:
            # If notebook mode - append to history only user_in, no
            # additional preparing;
            user.text_in.append(text_in)
            user.history_add("", text_in)
        elif text_in == const.GENERATOR_MODE_IMPERSONATE:
            # if impersonate - append to history only "name1:", no
            # adding "" history line to prevent bug in history sequence,
            # add "name1:" prefix for generation
            user.text_in.append(text_in)
            user.name_in.append(name_in)
            user.history_add("", name_in + ":")
        elif text_in == const.GENERATOR_MODE_NEXT:
            # if user_in is "" - no user text, it is like continue generation
            # adding "" history line to prevent bug in history sequence,
            # add "name2:" prefix for generation
            user.text_in.append(text_in)
            user.name_in.append(name_in)
            user.history_add("", user.name2 + ":")
        elif text_in == const.GENERATOR_MODE_REGENERATE:
            if user.text_in[-1] == const.GENERATOR_MODE_IMPERSONATE:
                user.history[-1] = user.name_in[-1] + ":"
            elif user.text_in[-1][0] in cfg.impersonate_prefixes:
                user.history[-1] = user.name_in[-1] + ":"
            else:
                user.history[-1] = user.name2 + ":"
        elif text_in == const.GENERATOR_MODE_CONTINUE:
            # if user_in is "" - no user text, it is like continue generation
            # adding "" history line to prevent bug in history sequence,
            # add "name2:" prefix for generation
            pass
        elif text_in[0] in cfg.sd_api_prefixes:
            # If user_in starts with prefix - impersonate-like (if you try to get "impersonate view")
            # adding "" line to prevent bug in history sequence, user_in is
            # prefix for bot answer
            user.text_in.append(text_in)
            user.name_in.append(name_in)
            if len(text_in) == 1:
                user.history_add("", cfg.sd_api_prompt_self)
            else:
                user.history_add("", cfg.sd_api_prompt_of.replace("OBJECT", text_in[1:].strip()))
            return_msg_action = const.MSG_SD_API
        elif text_in[0] in cfg.impersonate_prefixes:
            # If user_in starts with prefix - impersonate-like (if you try to get "impersonate view")
            # adding "" line to prevent bug in history sequence, user_in is
            # prefix for bot answer

            user.text_in.append(text_in)
            user.name_in.append(text_in[1:])
            user.history_add("", text_in[1:] + ":")

        else:
            # If not notebook/impersonate/continue mode then ordinary chat preparing
            # add "name1&2:" to user and bot message (generation from name2
            # point of view);
            user.text_in.append(text_in)
            user.name_in.append(name_in)
            user.history.append(name_in + ": " + text_in)
            user.history.append(user.name2 + ":")
    except Exception as exception:
        generator_lock.release()
        logging.error("generate_answer (prepare text part)" + str(exception))

    # Text processing with LLM
    try:
        # Set eos_token and stopping_strings.
        stopping_strings = generation_params["stopping_strings"].copy()
        eos_token = generation_params["eos_token"]
        if bot_mode in [const.MODE_CHAT, const.MODE_CHAT_R, const.MODE_ADMIN]:
            stopping_strings += [
                "\n" + name_in + ":",
                "\n" + user.name1 + ":",
                "\n" + user.name2 + ":",
            ]

        # adjust context/greeting/example
        if user.context.strip().endswith("\n"):
            context = f"{user.context.strip()}"
        else:
            context = f"{user.context.strip()}\n"
        if len(user.example) > 0:
            example = user.example + "\n<START>\n"
        else:
            example = ""
        if len(user.greeting) > 0:
            greeting = "\n" + user.name2 + ": " + user.greeting
        else:
            greeting = ""
        # Make prompt: context + example + conversation history
        prompt = ""
        available_len = generation_params["truncation_length"]
        context_len = generator_script.get_tokens_count(context)
        available_len -= context_len
        if available_len < 0:
            available_len = 0
            logging.info("telegram_bot - CONTEXT IS TOO LONG!!!")

        conversation = [example, greeting] + user.history

        for s in reversed(conversation):
            s = "\n" + s if len(s) > 0 else s
            s_len = generator_script.get_tokens_count(s)
            if available_len >= s_len:
                prompt = s + prompt
                available_len -= s_len
            else:
                break
        prompt = context + prompt.replace("\n\n", "\n")
        # Generate!
        answer = generator_script.get_answer(
            prompt=prompt,
            generation_params=generation_params,
            user=json.loads(user.to_json()),
            eos_token=eos_token,
            stopping_strings=stopping_strings,
            default_answer=answer,
            turn_template=user.turn_template,
        )
        # If generation result zero length - return  "Empty answer."
        if len(answer) < 1:
            answer = const.GENERATOR_EMPTY_ANSWER
        # Final return
        if answer not in [const.GENERATOR_EMPTY_ANSWER, const.GENERATOR_FAIL]:
            # if everything ok - add generated answer in history and return
            # last
            for end in stopping_strings:
                if answer.endswith(end):
                    answer = answer[: -len(end)]
            user.history[-1] = user.history[-1] + " " + answer
        generator_lock.release()
        return user.history[-1], return_msg_action
    except Exception as exception:
        logging.error("generate_answer (generator part)" + str(exception))
        # anyway, release generator lock. Then return
        generator_lock.release()
        return_msg_action = const.MSG_SYSTEM
        return user.history[-1], return_msg_action
