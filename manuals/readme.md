This is manual about telegram buttons, prefixes and functions.

# Start conversation:
After /start interaction with bot first time, bot sends you default char greeting with option menu:
![Image1](https://github.com/innightwolfsleep/llm_telegram_bot/manual/manuals/telegram_bot_start_option.PNG)
To get first answer just write something (but not single emoji or sticker)
![Image1](https://github.com/innightwolfsleep/llm_telegram_bot/manual/manuals/telegram_bot_message.PNG)
Here you are! Answer with message buttons!

# Buttons:
![Image1](https://github.com/innightwolfsleep/llm_telegram_bot/manual/manuals/telegram_bot_message_narrow.png)
Message buttons. There can be only one message in conversation with "message buttons", so message keyboard always moves to last bot message.
- "▶Next" - this button call next message from bot, like an empty input from you.
- "➡Continue" - seems like Next button, but call not new message - but continuing of current.
- "⬅Del word" - delete last word in current message, if you want "correct" your character answer.
- "♻Regenerate" - last message will be generated again, so result can be different. 
- "✖Cutoff" - last message to be deleted. Message keyboard moves to previous bot answer.
- "⚙Options" - call option menu
![Image1](https://github.com/innightwolfsleep/llm_telegram_bot/manual/manuals/telegram_bot_start_option_narrow.PNG)
Option buttons can be called in any moment, multiply times.
- "💾Save"
- "🎭Chars"
- "⚠Reset"
- "🇯🇵Language"
- "🔈Voice"
- "🔧Presets"
- "🔨Model"
- "❌Close"


# How to maximize your conversation?
- Use prefixes
- Use "Regenerate", "Cutoff" and "Next" buttons if conversation goes wrong way! 
- Do not forget about save/load.
- 

- session for all users are separative (by chat_id)
- local session history - conversation won't be lost if server restarts. Separated history between users and chars.
- nice "X typing" during generating (users will not think that bot stucking)
- buttons: continue previous message, regenerate last message, remove last messages from history, reset history button, new char loading menu
- you can load new characters from text-generation-webui\characters with button
- you can load new model during conversation with button
- chatting # prefix for impersonate: "#You" or "#Castle guard" or "#Alice thoughts about me"
- "!" prefix to replace last bot message
- "++" prefix permanently replace bot name during chat (switch conversation to another character)
- "📷" prefix to make photo via SD api. Write like "📷Chiharu Yamada", not single "📷"
- save/load history in chat by downloading/forwarding to chat .json file
- integrated auto-translate (you can set model/user language parameter) 
- voice generating ([silero](https://github.com/snakers4/silero-models)), en and ru variants
- translation_as_hidden_text option in .cfg - if you want to learn english with bot)))
- telegram_users.txt - list of permitted users (if empty - permit for all)
- antiflood - one message per 15 sec from one user


