import logging
import random
import string
import datetime
from datetime import timedelta
import discord
from discord.ext import commands
import sqlite3
from dotenv import load_dotenv
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

ADMIN_USER_ID = os.environ['ADMIN_USER_ID']

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'


class VIPCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_conn = sqlite3.connect('database.db')
        self.db_cursor = self.db_conn.cursor()

    @commands.command(name='forge')
    async def generate_code(self, ctx, duration: str = '1m'):
        try:
            # check if the user has the role of admin or owner
            if not ctx.author.guild_permissions.administrator:
                await ctx.send('You are not allowed to use this command.')
                return
            
            # check if user exists in the database and add them if not
            creator_uid = ctx.author.id
            username = ctx.author.name + "#" + ctx.author.discriminator
            self.check_and_add_user(creator_uid, username)
            
            # check if the duration is valid
            self.db_cursor.execute("SELECT duration, unit FROM sub_durations")
            available_durations = self.db_cursor.fetchall()
            duration_value, duration_unit, err_msg = self.get_duration(duration, available_durations)
            if err_msg:
                await ctx.send(err_msg)
                return
            self.db_cursor.execute("SELECT id FROM sub_durations WHERE duration = ? AND unit = ?", (duration_value, duration_unit))
            duration_id = self.db_cursor.fetchone()[0]

            # generate a unique code
            code = self.get_code(12)
            self.db_cursor.execute("SELECT redeemed, expiry_date FROM unique_codes WHERE code = ?", (code,))
            code_record = self.db_cursor.fetchone()
            while code_record:
                if not code_record[0] and datetime.datetime.strptime(code_record[1], DATETIME_FORMAT) < datetime.datetime.now():
                    self.db_cursor.execute("DELETE FROM unique_codes WHERE code = ?", (code,))
                    self.db_conn.commit()
                code = self.get_code(12)
                self.db_cursor.execute("SELECT redeemed, expiry_date FROM unique_codes WHERE code = ?", (code,))
                code_record = self.db_cursor.fetchone()

            # generate an expiry date
            expiry_date = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime(DATETIME_FORMAT)

            # insert the new unique code in the database
            new_unique_code_record = (code, duration_id, expiry_date, creator_uid)
            self.db_cursor.execute("INSERT INTO unique_codes (code, duration_id, expiry_date, creator_uid) VALUES (?, ?, ?, ?)", new_unique_code_record)
            self.db_conn.commit()


            if duration_value > 1:
                duration_unit += 's'
            await ctx.send(f'Code generated: {code}\nDuration: {duration_value} {duration_unit}\nExpiry date: {expiry_date}')

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(self.get_error_message())


    @commands.command(name='claim')
    async def redeem_code(self, ctx, code: str):
        try:
            # check if the user has the role of admin or owner (amins can not claim codes)
            if ctx.author.guild_permissions.administrator:
                await ctx.send('You are not allowed to use this command.')
                return
            
            # check if the code exists in the database and whether it has been claimed or not
            self.db_cursor.execute("SELECT id, redeemed, expiry_date, duration_id FROM unique_codes WHERE code = ?", (code,))
            code_record = self.db_cursor.fetchone()
            if not code_record:
                await ctx.send('This code does not exist.')
                return
            elif code_record[1]:
                await ctx.send('This code has already been claimed.')
                return
            
            # check if the code is expired
            expiry_date = datetime.datetime.strptime(code_record[2], DATETIME_FORMAT)
            if expiry_date < datetime.datetime.now():
                await ctx.send('This code is expired.')
                return
            
            # check if user exists in the database and add them if not
            claimer_uid = ctx.author.id
            username = ctx.author.name + "#" + ctx.author.discriminator
            self.check_and_add_user(claimer_uid, username)

            # get the user_id
            user_id = self.get_user_id(claimer_uid)

            # get the duration record from the database
            self.db_cursor.execute("SELECT id, duration, unit FROM sub_durations WHERE id = ?", (code_record[3],))
            duration_record = self.db_cursor.fetchone()

            # check if the user already has a subscription and if so, if end_date is not expired yet and still active, then update the end_date, otherwise insert a new subscription
            active_subscriptions = self.get_active_subscriptions(user_id, 'Code')
            if active_subscriptions:
                new_end_date = self.extend_subscription(active_subscriptions[-1], duration_record)
                subscription_id = active_subscriptions[-1]['id']
            else:
                self.insert_new_subscription(user_id, duration_record)
                subscription_id = self.get_subscription_id(user_id)
                
            # mark the code as redeemed
            self.mark_code_as_redeemed(code_record[0], subscription_id)
            
            # Change user role to VIP if not already
            if not discord.utils.get(ctx.author.roles, name='VIP'):
                await ctx.author.add_roles(discord.utils.get(ctx.guild.roles, name='VIP'))

            if active_subscriptions:
                await ctx.send(f'Your subscription has been extended to {new_end_date}. Enjoy!')
            else:
                await ctx.send(f'Your subscription has been actiaved. Enjoy!')
                
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(self.get_error_message())

    @commands.command(name='bless')
    async def bless(self, ctx, member: discord.Member, duration: str = '1m'):
        try:
            # check if the user has the role of admin or owner (amins can not claim codes)
            if not ctx.author.guild_permissions.administrator:
                await ctx.send('You are not allowed to use this command.')
                return
            
            # check if user (member not ctx) exists in the database and add them if not
            member_uid = member.id
            username = member.name + "#" + member.discriminator
            self.check_and_add_user(member_uid, username)

            # check if the duration is valid
            self.db_cursor.execute("SELECT duration, unit FROM sub_durations")
            available_durations = self.db_cursor.fetchall()
            duration_value, duration_unit, err_msg = self.get_duration(duration, available_durations)
            if err_msg:
                await ctx.send(err_msg)
                return
            self.db_cursor.execute("SELECT id FROM sub_durations WHERE duration = ? AND unit = ?", (duration_value, duration_unit))
            duration_id = self.db_cursor.fetchone()[0]

            # get the user_id
            user_id = self.get_user_id(member_uid)

            duration_record = (duration_id, duration_value, duration_unit)

            # check if the user already has a subscription and if so, if end_date is not expired yet and still active, then update the end_date, otherwise insert a new subscription
            active_subscriptions = self.get_active_subscriptions(user_id, 'Manual')
            if active_subscriptions:
                new_end_date = self.extend_subscription(active_subscriptions[-1], duration_record)
            else:
                self.insert_new_subscription(user_id, duration_record)

            # Change user role to VIP if not already
            if not discord.utils.get(member.roles, name='VIP'):
                await member.add_roles(discord.utils.get(ctx.guild.roles, name='VIP'))

            if active_subscriptions: # mention that the member's subscription have been extended to {date}
                await ctx.send(f'Member {member.name}\'s subscription has been extended to {new_end_date}.')
            else:
                await ctx.send(f'Member {member.name} has been blessed with {duration_value} {duration_unit} of VIP status.')

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(self.get_error_message())

    @commands.command(name='curse') 
    async def curse(self, ctx, member: discord.Member, duration: str = ''):
        try:
            # check if the user has the role of admin or owner (amins can not claim codes)
            if not ctx.author.guild_permissions.administrator:
                await ctx.send('You are not allowed to use this command.')
                return
            
            # check if user (member not ctx) exists in the database and add them if not
            member_uid = member.id
            username = member.name + "#" + member.discriminator
            self.check_and_add_user(member_uid, username)


            if duration:
                # check if the duration is valid
                self.db_cursor.execute("SELECT duration, unit FROM sub_durations")
                available_durations = self.db_cursor.fetchall()
                duration_value, duration_unit, err_msg = self.get_duration(duration, available_durations)
                if err_msg:
                    await ctx.send(err_msg)
                    return
                self.db_cursor.execute("SELECT id FROM sub_durations WHERE duration = ? AND unit = ?", (duration_value, duration_unit))
                duration_id = self.db_cursor.fetchone()[0]
                # TODO: continue later here if duration is provided
            else:
                # remove the user's active subscription by updating the end_date to now and removing the role
                user_id = self.get_user_id(member_uid)
                active_subscriptions = self.get_active_subscriptions(user_id)
                if active_subscriptions:
                    curse_date = datetime.datetime.now() - timedelta(minutes=1)
                    curse_date = curse_date.strftime("%Y-%m-%d %H:%M:%S")
                    for sub in active_subscriptions:
                        self.db_cursor.execute("UPDATE subscriptions SET end_date = ? WHERE id = ?", (curse_date, sub["id"]))
                        self.db_conn.commit()
                    await member.remove_roles(discord.utils.get(ctx.guild.roles, name='VIP'))
                    await ctx.send(f'Member {member.name}\'s active subscription has been removed, and thir VIP status has been revoked.')

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(self.get_error_message())

    @commands.command(name='hermes_wisdom') 
    async def hermes_wisdom(self, ctx, user: discord.Member):
        try:
            pass # do something...
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(self.get_error_message())

    @commands.command(name='check')
    async def check(self, ctx):
        try:
            # check if user exists in the database and add them if not
            claimer_uid = ctx.author.id
            username = ctx.author.name + "#" + ctx.author.discriminator
            self.check_and_add_user(claimer_uid, username)

            vip_role = discord.utils.get(ctx.guild.roles, name='VIP')

            # get the user_id
            user_id = self.get_user_id(claimer_uid)
            active_subscriptions = self.get_active_subscriptions(user_id)
            if active_subscriptions:
                subscription = active_subscriptions[-1]
                # check if the user has the right role (VIP) and if not, add it
                if not discord.utils.get(ctx.author.roles, name='VIP'):
                    await ctx.author.add_roles(vip_role)
                    await ctx.send(f'You have been reinstated as VIP. Your subscription is active until {subscription["end_date"]}.')
                else:
                    await ctx.send(f'Your subscription is active until {subscription["end_date"]}.')
            else:
                if vip_role in ctx.author.roles:
                    await ctx.author.remove_roles(vip_role)
                await ctx.send(f'You do not have an active subscription.')

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(self.get_error_message())

    @commands.command(name='info')
    async def info(self, ctx, code: str): # send code duration and status
        try:
            # check if the code exists in the database and whether it has been claimed or not
            self.db_cursor.execute("SELECT id, redeemed, expiry_date, duration_id FROM unique_codes WHERE code = ?", (code,))
            code_record = self.db_cursor.fetchone()
            if not code_record:
                await ctx.send('This code does not exist.')
                return
            elif code_record[1]:
                await ctx.send('This code has already been claimed.')
                return
            
            # check if the code is expired
            expiry_date = datetime.datetime.strptime(code_record[2], DATETIME_FORMAT)
            if expiry_date < datetime.datetime.now():
                await ctx.send('This code is expired.')
                return
            
            # get the duration
            self.db_cursor.execute("SELECT duration, unit FROM sub_durations WHERE id = ?", (code_record[3],))
            duration_value, duration_unit = self.db_cursor.fetchone()

            if duration_value > 1:
                duration_unit += 's'

            # semd code redeemed or not, duration and expiry date
            await ctx.send(f'Code: {code}\nDuration: {duration_value} {duration_unit}\nStatus: Unclaimed\nExpiry date: {expiry_date}')

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(self.get_error_message())

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            original = error.original
            if isinstance(original, discord.Forbidden):
                await ctx.send("I do not have permission to perform this action.")
            else:
                raise error
        else:
            raise error
    
    def get_duration(self, duration: str, available_durations: list) -> tuple[int, str, str]:
        available_durations_str = [f'{duration}{unit[0]}' for duration, unit in available_durations]
        if duration in available_durations_str:
            duration_unit = available_durations[available_durations_str.index(duration)]
            return duration_unit[0], duration_unit[1], ''
        else:
            err_msg = 'Invalid duration. Please use the following format: 1d, 3d, 7d, 14d, 1m, 3m, 6m, 12m.'
            return 0, '', err_msg


    def get_code(self, l: int) -> str:
        unique_digits = string.digits + string.ascii_uppercase
        random_code = ''.join(random.choice(unique_digits) for _ in range(l))
        return f'{random_code[:l//3]}-{random_code[l//3:2*l//3]}-{random_code[2*l//3:]}'
    
    def get_user_id(self, discord_uid: int) -> int:
        self.db_cursor.execute("SELECT id FROM users WHERE discord_uid = ?", (discord_uid,))
        user_id = self.db_cursor.fetchone()[0]
        return user_id
    
    def get_subscription_id(self, user_id: int) -> int:
        self.db_cursor.execute("SELECT id FROM subscriptions WHERE user_id = ?", (user_id,))
        subscription_id = self.db_cursor.fetchone()[0]
        return subscription_id

    def check_and_add_user(self, discord_uid: int, username: str) -> None:
        self.db_cursor.execute("SELECT * FROM users WHERE discord_uid = ?", (discord_uid,))
        if not self.db_cursor.fetchone():
            self.db_cursor.execute("INSERT INTO users (discord_uid, username) VALUES (?, ?)", (discord_uid, username))
            self.db_conn.commit()

    def get_active_subscriptions(self, user_id: int, sub_type: str = '') -> list[tuple]:
        if sub_type:
            query = """
            SELECT subscriptions.id, datetime(subscriptions.end_date)
            FROM subscriptions
            JOIN sub_types ON sub_types.id = subscriptions.sub_type_id
            WHERE subscriptions.user_id = ? AND sub_types.name = ?;
            """

            self.db_cursor.execute(query, (user_id, sub_type))
            all_subscriptions = self.db_cursor.fetchall()
        else:
            query = """
            SELECT subscriptions.id, datetime(subscriptions.end_date)
            FROM subscriptions
            JOIN sub_types ON sub_types.id = subscriptions.sub_type_id
            WHERE subscriptions.user_id = ?;
            """

            self.db_cursor.execute(query, (user_id,))
            all_subscriptions = self.db_cursor.fetchall()

        now = datetime.datetime.now()

        active_subscriptions = [
            (sub_id, datetime.datetime.strptime(end_date, DATETIME_FORMAT))
            for sub_id, end_date in all_subscriptions
            if datetime.datetime.strptime(end_date, DATETIME_FORMAT) > now
        ]

        # convert it into dictionary and convert datetime object to string
        active_subscriptions = [{'id': subscription[0], 'end_date': subscription[1].strftime(DATETIME_FORMAT)} for subscription in active_subscriptions]

        return active_subscriptions
    
    def extend_subscription(self, subscription: tuple, duration_record: tuple) -> str:
        current_end_date = datetime.datetime.strptime(subscription['end_date'], DATETIME_FORMAT)

        _, duration_value, duration_unit = duration_record
        if duration_unit == 'day':
            delta = datetime.timedelta(days=duration_value)
        elif duration_unit == 'month':
            delta = datetime.timedelta(days=duration_value * 30)

        # Add the timedelta to the current end_date to get the new_end_date
        new_end_date = current_end_date + delta
        new_end_date_str = new_end_date.strftime(DATETIME_FORMAT)

        # Update the subscription's end_date in the database
        self.db_cursor.execute("UPDATE subscriptions SET end_date = ? WHERE id = ?", (new_end_date_str, subscription['id']))
        self.db_conn.commit()

        return new_end_date_str

    def insert_new_subscription(self, user_id: int, duration_record: tuple) -> None:
        _, duration_value, duration_unit = duration_record
        if duration_unit == 'day':
            delta = datetime.timedelta(days=duration_value)
        elif duration_unit == 'month':
            delta = datetime.timedelta(days=duration_value * 30)

        start_date = datetime.datetime.now()
        end_date = start_date + delta

        # Get the sub_type_id for code
        self.db_cursor.execute("SELECT id FROM sub_types WHERE name = 'Code'")
        sub_type_id = self.db_cursor.fetchone()[0]

        # Insert the new subscription into the database
        new_subscription_record = (start_date.strftime(DATETIME_FORMAT), end_date.strftime(DATETIME_FORMAT), user_id, sub_type_id)
        self.db_cursor.execute("INSERT INTO subscriptions (start_date, end_date, user_id, sub_type_id) VALUES (?, ?, ?, ?)", new_subscription_record)
        self.db_conn.commit()

    def mark_code_as_redeemed(self, code_id, subscription_id) -> None: # in unique_codes.redeemed <- 1, and insert into redeemed_codes a new record
        self.db_cursor.execute("UPDATE unique_codes SET redeemed = 1 WHERE id = ?", (code_id,))
        redepmtion_date = datetime.datetime.now().strftime(DATETIME_FORMAT)
        redeemed_code_record = (redepmtion_date, code_id, subscription_id)
        self.db_cursor.execute("INSERT INTO redeemed_codes (redemption_date, unique_code_id, subscription_id) VALUES (?, ?, ?)", redeemed_code_record)
        self.db_conn.commit()

    def get_error_message(self) -> str:
        hermes_error_messages = [
            "My apologies, mortal. It appears that even the swift Hermes can stumble. Let's attempt that command once more.",
            "By the wings of Hermes! An unexpected hindrance has occurred. Fear not, and try again after a short while.",
            "It appears Hermes is momentarily detained on Mount Olympus. Kindly retry your request later.",
        ]
        return random.choice(hermes_error_messages)
    
    async def send_private_error_notification(self, username: str, command: str, error_message: str):
        owner_id = ADMIN_USER_ID
        owner = await self.bot.fetch_user(owner_id)
        await owner.send(f"An error occurred (u: {username}, c: {command}): {error_message}")

    def close_db_connection(self):
        if self.db_conn:
            self.db_conn.close()

