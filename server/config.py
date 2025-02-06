import os
import discord
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
LANG_CHANNEL_ROLE = int(os.getenv('LANG_CHANNEL_ROLE'))
PL_GUILD_ID = int(os.getenv('PL_GUILD_ID'))

# unused, no need to set
TEST_GUILDS = [guild_id.strip() for guild_id in os.getenv('TEST_GUILDS', '').split(',') if len(guild_id.strip()) > 0]

WS_HOST = 'localhost'
WS_PORT = 1717

CLIENTS_STORE = 'data/clients.shelve'

DISCORD_OK_COLOR = discord.Color(0x0099FF)
DISCORD_ERR_COLOR = discord.Color.red()

EVAL_TIMEOUT_MS: int = 5000
ERROR_MSG_DELETE_AFTER_MS: int|None = 30000

MAX_EMBED_DESCRIPTION_SIZE = 4096
MAX_EMBED_FIELD_SIZE = 1024