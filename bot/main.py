import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import asyncio
from cogs.vipcog import VIPCommand
import cogs.vipcog




logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

TOKEN = os.environ['TOKEN']

async def main():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.messages = True
    intents.members = True
    bot = commands.Bot(command_prefix='/', intents=intents)
    # vip_command = VIPCommand(bot)
    bot.load_extension('cogs.vipcog')

    @bot.event
    async def on_ready() -> None:
        guilds_names = ', '.join([f'"{guild.name}"' for guild in bot.guilds])
        logging.info(f'{bot.user} is now Connected and Running on Discord servers: {guilds_names}!')

    @bot.command()
    async def test(ctx):
        await ctx.send("Test command worked!")

    # await bot.add_cog(vip_command)
    await bot.start(TOKEN)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass