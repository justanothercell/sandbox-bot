import asyncio
import discord
import discord.ext
import discord.ext.tasks
from discord.ext import commands
from discord.commands.context import ApplicationContext
from discord.commands import Option
import io

import re

from client_hook import ClientHookServer
from store import Store, Language, LanguageRegistrationException
import config
import protocol

class Permissions:
    RUN_CLIENT = 0
    EVAL_SCRIPT = 1

ident_pattern = re.compile("^[_a-zA-Z][_a-zA-Z0-9]*$")
def is_identifier(ident: str) -> bool:
    if len(ident) < 3 or len(ident) > 16:
        return False
    return ident_pattern.match(ident) is not None

def text_to_memfile(text: str) -> io.BytesIO:
    file = io.BytesIO()
    file.write(text.encode())
    file.seek(0)
    return file

class LanguageCog(commands.Cog): # command_attrs=dict(guild_ids=config.TEST_GUILDS)
    def __init__(self, bot: discord.Bot, server: ClientHookServer, store: Store):
        self.bot = bot
        self.server = server
        self.store = store
        print(f'Initialized LanguageCog')

    def cog_unload(self):
        print(f'Unloaded LanguageCog')

    @discord.slash_command(description='Sends a new client key as an ephemeral message.')
    async def client_key(self, ctx: ApplicationContext, 
                        name: Option(str, 'The language name identifier', required=True), # type: ignore
                        short: Option(str, 'The language\'s file extension or short form name', required=False)): # type: ignore
        if not isinstance(ctx.channel, discord.abc.GuildChannel) or ctx.guild_id != config.PL_GUILD_ID:
            await self.send_error_message(ctx, 'Invalid channel', 'You need to run this command on the r/ProgrammingLanguages discord!\n(Don\'t worry, the key will only be visible to you)')
            return
        if not await self.has_permissions(ctx.author, Permissions.RUN_CLIENT):
            await self.send_error_message(ctx, 'Invalid permission', 'You need a language channel to create a language client')
            return
        if short is None:
            short = name
        if not is_identifier(name):
            await self.send_error_message(ctx, 'Invalid argument', 'Your language\'s name must be an identifier `[_a-zA-Z][_a-zA-Z0-9]*` between 3 and 16 characters long')
            return
        if not is_identifier(short):
            await self.send_error_message(ctx, 'Invalid argument', 'Your language\'s short form name must be an identifier `[_a-zA-Z][_a-zA-Z0-9]*` between 3 and 16 characters long')
            return
        key = protocol.new_key()
        language = Language(ctx.author.id, name, short, key)
        try:
            old_lang = await self.store.register_lang(language)
        except LanguageRegistrationException as e:
            await self.send_error_message(ctx, 'Cannot register client', e.message)
            return
        if old_lang is not None:
            await self.server.kill_client_conn(old_lang.key) # kill the current one
        embed = discord.Embed(color=config.DISCORD_OK_COLOR, title='Client token', description=f'This is your new client key:\n`{key}`\nDo not share this key with anyone! Any old keys are now disabled.')
        await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(description='Evaluate an expression')
    async def eval(self, ctx: ApplicationContext,
                   language: Option(str, 'The language name', required=True), # type: ignore
                   expression: Option(str, 'The expression to evaluate', required=True), # type: ignore
                   display: Option(bool, 'Display the result for everyone to see', required=False)): # type: ignore
        await self.evaluate(ctx, language, expression, not display)

    @discord.message_command(description='Run the code block in this message')
    async def run(self, ctx: ApplicationContext, message: discord.Message):
        await self.process_run_command(ctx, message, True)
    
    @discord.message_command(description='Run the code block in this message and display the result for all to see')
    async def run_show(self, ctx: ApplicationContext, message: discord.Message):
        await self.process_run_command(ctx, message, False)
    
    async def process_run_command(self, ctx: ApplicationContext, message: discord.Message, ephemeral: bool):
        content = message.system_content.split('```')
        if len(content) < 3:
            await self.send_error_message(ctx, 'No code block', 'Could not find valid codeblock in this message')
            return
        if len(content) > 3:
            await self.send_error_message(ctx, 'Multiple code blocks', 'Multiple code blocks found in this message')
            return
        prefix, code, _ = content
        prefix = prefix.strip()
        lang = None
        if '\n' in code and code[0].isalnum():
            lang, code = code.split('\n', maxsplit=1)
            lang = lang.strip()
        if prefix[-1] == '`':
            split = prefix.rsplit('`')
            if len(split) >= 3:
                *_, langblob, _ = split
                langblob = langblob.strip()
                if langblob.startswith('lang:') or langblob.startswith('language:'):
                    _, lang = langblob.split(':')
        await self.evaluate(ctx, lang, code, ephemeral)

    async def evaluate(self, ctx: ApplicationContext, lang: str, code: str, ephemeral: bool):
        if not await self.has_permissions(ctx.author, Permissions.EVAL_SCRIPT):
            await self.send_error_message(ctx, 'Invalid permission', 'You do not have permission to evaluate code')
            return
        language = await self.store.find_lang(lang)
        if language is None:
            await self.send_error_message(ctx, 'Invalid language', f'No such language `{lang}` registered')
        convo = await self.server.conversation(language.key)
        if convo is None:
            await self.send_error_message(ctx, 'Client offline', f'{language.name}\'s client is currently not available')
            return
        async with convo:
            await convo.send(protocol.EvaluateMessage(convo.id, code))
            response_fut = convo.receive()
            await ctx.defer(ephemeral=ephemeral)
            delete_after = None if ephemeral else config.ERROR_MSG_DELETE_AFTER_MS / 1000.0
            try:
                response: protocol.ResultMessage = await asyncio.wait_for(response_fut, timeout=config.EVAL_TIMEOUT_MS / 1000.0)
            except asyncio.TimeoutError:
                response_fut.close()
                await convo.send(protocol.TimeoutMessage(convo.id))
                await self.send_error_message(ctx, 'Client timeout', f'Client did not finish within allowed timeframe of {config.EVAL_TIMEOUT_MS / 1000.0}s', ephemeral=ephemeral, delete_after=delete_after)
                return
            if response.kind == protocol.ErrorMessage.kind:
                await self.send_error_message(ctx, 'Client error', f'Client experienced exception during evaluation', ephemeral=ephemeral, delete_after=delete_after)
                return
            if response.kind != protocol.ResultMessage.kind:
                await self.send_error_message(ctx, 'Client error', f'Response is invalid', ephemeral=ephemeral, delete_after=delete_after)
                return
            files = []
            if response.success:
                if response.exit_code is None:
                    embed = discord.Embed(color=config.DISCORD_OK_COLOR, title='Evaluation successful')
                else:
                    embed = discord.Embed(color=config.DISCORD_OK_COLOR, title=f'Evaluation finished with code {response.exit_code}')
                if response.stdout is not None:
                    if len(response.stdout) < config.MAX_EMBED_FIELD_SIZE - 10:
                        embed.add_field(name='stdout', value=f'```\n{response.stdout}```')
                    else:
                        if ephemeral:
                            embed.add_field(name='stdout (truncated, run in visible mode to get files)', value=f'```\n...\n{response.stdout[-int(config.MAX_EMBED_FIELD_SIZE/2):].strip()}```')
                        else:
                            embed.add_field(name='stdout (truncated)', value=f'```\n...\n{response.stdout[-int(config.MAX_EMBED_FIELD_SIZE/2):].strip()}```')
                            files.append(discord.File(text_to_memfile(response.stdout), filename='stdout.txt'))
                if response.stderr is not None:
                    if len(response.stderr) < config.MAX_EMBED_FIELD_SIZE - 10:
                        embed.add_field(name='stderr', value=f'```\n{response.stderr}```')
                    else:
                        if ephemeral:
                            embed.add_field(name='stderr (truncated, run in visible mode to get files)', value=f'```\n...\n{response.stderr[-int(config.MAX_EMBED_FIELD_SIZE/2):].strip()}```')
                        else:
                            embed.add_field(name='stderr (truncated)', value=f'```\n...\n{response.stderr[-int(config.MAX_EMBED_FIELD_SIZE/2):].strip()}```')
                            files.append(discord.File(text_to_memfile(response.stderr), filename='stderr.txt'))
            else:
                if response.error is None:
                    embed = discord.Embed(color=config.DISCORD_ERR_COLOR, title='Compilation failed')
                else:
                    if len(response.error) < config.MAX_EMBED_DESCRIPTION_SIZE - 10:
                        embed = discord.Embed(color=config.DISCORD_ERR_COLOR, title='Compilation failed', description=f'```\n{response.error}```')
            if ephemeral:
                await ctx.respond(embed=embed, ephemeral=True)
            else:
                await ctx.respond(embed=embed, files=files, ephemeral=False)

    async def has_permissions(self, member: discord.Member, permission: int):
        match permission:
            case Permissions.RUN_CLIENT:
                if member.get_role(config.LANG_CHANNEL_ROLE) is None:
                    return False
                return True
            case Permissions.EVAL_SCRIPT:
                return True # anyone may eval
    
    async def send_error_message(self, ctx: ApplicationContext, title: str, message: str, ephemeral=True, delete_after=None):
        embed = discord.Embed(color=config.DISCORD_ERR_COLOR, title=title, description=message)
        await ctx.respond(embed=embed, ephemeral=ephemeral, delete_after=delete_after)

    @commands.Cog.listener()
    async def on_ready(self):
        print('=================')
        print(f'{self.bot.user.name} ready')
        print('=================')