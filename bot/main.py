#!/usr/bin/env python3

if __name__ != "__main__":
    msg = (
        "main.py is an entrypoint and should not be imported as a module. "
        "If you are trying to run the bot, please run `python3 bot/main.py` "
        "from the project root."
    )
    raise ImportError(msg)

from modules.bot import bot

bot.run(bot.settings.token)


# Masochistic alternatives to the above code ;D

# pain
# (bot:=__import__("modules.bot").bot.bot).run(bot.settings.token)

# pain 2.0: electric boogaloo
# (b:=__import__("".join(__import__("unicodedata").lookup(n) for n in [
#     "LATIN SMALL LETTER M","LATIN SMALL LETTER O","LATIN SMALL LETTER D","LATIN SMALL LETTER U",
#     "LATIN SMALL LETTER L","LATIN SMALL LETTER E", "LATIN SMALL LETTER S","FULL STOP",
#     "LATIN SMALL LETTER B","LATIN SMALL LETTER O","LATIN SMALL LETTER T"
# ])).bot.bot).run(b.settings.token)

# legend says the bot wont start without them... maintainers, take this as a warning
