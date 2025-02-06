import sys
import os
# make protocol.py importable
currentdir = os.path.dirname(os.path.abspath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir) 

import discord
from discord_cog import LanguageCog
from client_hook import ClientHookServer

import config
from store import Store

def main():
    store = Store()

    server = ClientHookServer(store)

    bot = discord.Bot(intents=discord.Intents.all())
    bot.add_cog(LanguageCog(bot, server, store))

    bot.loop.create_task(server.run())
    bot.run(config.BOT_TOKEN)

if __name__ == '__main__':
    main()