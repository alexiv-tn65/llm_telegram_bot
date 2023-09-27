# settings
generation_timeout = 600
# Supplementary structure
replace_prefixes = ["!", "-"]  # Prefix to replace last message
impersonate_prefixes = ["#", "+"]  # Prefix for "impersonate" message
# Prefix for persistence "impersonate" message
permanent_change_name1_prefixes = ["--"]
permanent_change_name2_prefixes = ["++"]
permanent_add_context_prefixes = ["=="]
# Prefix for replace username "impersonate" message
permanent_user_prefixes = ["+="]
permanent_contex_add = ["+-"]  # Prefix for adding string to context
# Prefix for sd api generation
sd_api_prefixes = [
    "📷",
    "📸",
    "📹",
    "🎥",
    "📽",
]
sd_api_prompt_of = "Detailed description of OBJECT:"
sd_api_prompt_self = "Detailed description of appearance, surroundings and what doing right now: "

# html tags fot ordinary text
html_tag = ["<pre>", "</pre>"]
# html tags for translated text
translate_html_tag = ['<span class="tg-spoiler">', "</span>"]
# Language list for translator
language_dict = {
    "en": "🇬🇧",
    "ru": "🇷🇺",
    "ja": "🇯🇵",
    "fr": "🇫🇷",
    "es": "🇪🇸",
    "de": "🇩🇪",
    "th": "🇹🇭",
    "tr": "🇹🇷",
    "it": "🇮🇹",
    "hi": "🇮🇳",
    "zh-CN": "🇨🇳",
    "ar": "🇸🇾",
}

default_messages_template = {  # dict of messages templates for various situations. Use _VAR_ replacement
    "mem_lost": "<b>MEMORY LOST!</b>\nSend /start or any text for new session.",  # refers to non-existing
    "retyping": "<i>_NAME2_ retyping...</i>",  # added when "regenerate button" working
    "typing": "<i>_NAME2_ typing...</i>",  # added when generating working
    "char_loaded": "_NAME2_ LOADED!\n_GREETING_ ",  # When new char loaded
    "preset_loaded": "LOADED PRESET: _OPEN_TAG__CUSTOM_STRING__CLOSE_TAG_",  # When new char loaded
    "model_loaded": "LOADED MODEL: _OPEN_TAG__CUSTOM_STRING__CLOSE_TAG_",  # When new char loaded
    "mem_reset": "MEMORY RESET!\n_GREETING_",  # When history cleared
    "hist_to_chat": "To load history - forward message to this chat",  # download history
    "hist_loaded": "_NAME2_ LOADED!\n_GREETING_\n\nLAST MESSAGE:\n_CUSTOM_STRING_",  # load history
}