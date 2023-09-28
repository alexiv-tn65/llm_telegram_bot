from pydantic import BaseModel, Field
from typing import List, Dict
import logging


# Set logging
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y.%m.%d %I:%M:%S %p",
    level=logging.INFO,
)


class Config(BaseModel):
    flood_avoid_delay: float = Field(default=10.0, description="Delay between new messages to avoid flooding (sec)")
    generation_timeout: int = Field(default=120, description="Timeout for text generator")

    # Single shot prefixes
    replace_prefixes: List = Field(default=["!", "-"], description="Prefix to replace last message")
    impersonate_prefixes: List = Field(default=["#", "+"], description="Prefix for 'impersonate' message")
    # Prefix for persistence "impersonate" message
    permanent_change_name1_prefixes: List = Field(default=["--"], description="Prefix to replace name1")
    permanent_change_name2_prefixes: List = Field(default=["++"], description="Prefix to replace name2")
    permanent_add_context_prefixes: List = Field(default=["=="], description="Prefix to add in context")

    sd_api_prefixes: List = Field(default=["📷", "📸", "📹", "🎥", "📽", ],
                                  description="Prefix to generate image via SD API")
    sd_api_prompt_of: str = "Detailed description of OBJECT:"
    sd_api_prompt_self: str = "Detailed description of appearance, surroundings and what doing right now: "

    html_tag = Field(default=["<pre>", "</pre>"], description="html tags for ordinary text")
    translate_html_tag = Field(default=['<span class="tg-spoiler">', "</span>"],
                               description="html tags for translated text")
    translation_as_hidden_text = Field(default="on", description="if 'on' translation showing after original message "
                                                                 "inside translate_html_tag. "
                                                                 "If 'off' - only translated text.")
    language_dict: Dict[str, str] = Field(default={
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
    }, description="Language list for translator")
