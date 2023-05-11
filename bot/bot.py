import logging
import random
import string
import datetime
import discord
from discord.ext import commands
import sqlite3
from dotenv import load_dotenv
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

TOKEN = os.environ['TOKEN']
ADMIN_USER_ID = os.environ['ADMIN_USER_ID']

# inherit bot instead of client
class Bot(commands.Bot):
    def __init__(self, intents, command_prefix='!'):
        super().__init__(intents=intents, command_prefix=command_prefix)
        self.db_conn = sqlite3.connect('database.db')
        self.db_cursor = self.db_conn.cursor()

    @staticmethod
    def create_instance() -> 'Bot':
        intents = discord.Intents.default()
        intents.message_content = True
        return Bot(intents=intents)
    
    def run(self) -> None:
        super().run(TOKEN)

    async def on_ready(self) -> None:
        guilds_names = ', '.join([f'"{guild.name}"' for guild in self.guilds])
        logging.info(f'{self.user} is now Connected and Running on Discord servers: {guilds_names}!')

    @commands.command(name='forge')
    async def generate_code(self, ctx, duration: str):
        try:
            # check if the user has the role of admin or owner
            if not (ctx.author.id == ADMIN_USER_ID or ctx.author.guild_permissions.administrator):
                await ctx.send('You are not allowed to use this command.')
                return
            
            # check if user exists in the database and add them if not
            creator_uid = ctx.author.id
            self.db_cursor.execute("SELECT * FROM users WHERE discord_id = ?", (creator_uid,))
            if not self.db_cursor.fetchone():
                self.db_cursor.execute("INSERT INTO users (discord_id, discord_name) VALUES (?, ?)", (creator_uid, ctx.author.name))
                self.db_conn.commit()
            
            # check if the duration is valid
            self.db_cursor.execute("SELECT duration, unit FROM subscription_durations")
            availables_durations = self.db_cursor.fetchall()
            duration, unit, err_msg = self.get_duration(duration, availables_durations)
            if err_msg:
                await ctx.send(err_msg)
                return
            self.db_cursor.execute("SELECT id FROM subscription_durations WHERE duration = ? AND unit = ?", (duration, unit))
            duration_id = self.db_cursor.fetchone()[0]

            # generate a unique code
            code = self.get_code(12)
            self.db_cursor.execute("SELECT * FROM unique_codes WHERE code = ?", (code,))
            while self.db_cursor.fetchone():
                code = self.get_code(12)

            # generate an expiry date
            expiry_date = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime('%Y-%m-%d')

            # insert the new unique code in the database
            new_unique_code_record = (code, duration_id, expiry_date, creator_uid)
            self.db_cursor.execute("INSERT INTO unique_codes (code, duration_id, expiry_date, creator_uid) VALUES (?, ?, ?, ?)", new_unique_code_record)
            self.db_conn.commit()

            await ctx.send(f'Code generated: {code}')

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(self.get_error_message())


    @commands.command(name='claim')
    async def redeem_code(self, ctx, code: str):
        try:
            pass # do something...
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(self.get_error_message())

    @commands.command(name='bless')
    async def bless(self, ctx, user: discord.Member):
        try:
            pass # do something...
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(self.get_error_message())

    @commands.command(name='curse') 
    async def bless(self, ctx, user: discord.Member):
        try:
            pass # do something...
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(self.get_error_message())

    @commands.command(name='hermes_wisdom') 
    async def bless(self, ctx, user: discord.Member):
        try:
            pass # do something...
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(self.get_error_message())

    
    def get_duration(self, duration: str, availables_durations: list) -> tuple[int, str, str]:
        availables_durations_str = [f'{duration}{unit[0]}' for duration, unit in availables_durations]
        if duration in availables_durations_str:
            duration_unit = availables_durations[availables_durations_str.index(duration)]
            return duration_unit[0], duration_unit[1], ''
        else:
            err_msg = 'Invalid duration. Please use the following format: 1d, 3d, 7d, 14d, 1m, 3m, 6m, 12m.'
            return 0, '', err_msg


    def get_code(self, l: int) -> str:
        unique_digits = string.digits + string.ascii_uppercase
        random_code = ''.join(random.choice(unique_digits) for _ in range(l))
        return f'{random_code[:l//3]}-{random_code[l//3:2*l//3]}-{random_code[2*l//3:]}'


    def get_error_message(self) -> str:
        hermes_error_messages = [
            "My apologies, mortal. It appears that even the swift Hermes can stumble. Let's attempt that command once more.",
            "By the wings of Hermes! An unexpected hindrance has occurred. Fear not, and try again after a short while.",
            "It appears Hermes is momentarily detained on Mount Olympus. Kindly retry your request later.",
        ]
        return random.choice(hermes_error_messages)
    
    async def send_private_error_notification(self, username: str, command: str, error_message: str):
        owner_id = ADMIN_USER_ID
        owner = await self.fetch_user(owner_id)
        await owner.send(f"An error occurred (u: {username}, c: {command}): {error_message}")

    async def close(self) -> None:
        if self.db_conn:
            self.db_conn.close()
        await super().close()
        logging.info('Bot closed!')
        
