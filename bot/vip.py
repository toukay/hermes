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
import asyncio

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

ADMIN_USER_ID = os.environ['ADMIN_USER_ID']

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'


class VIPCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_conn = sqlite3.connect('database.db')
        self.db_cursor = self.db_conn.cursor()
        self.perm_vips = {}

    @commands.command(name='generate', aliases=['gen', 'forge'], help='Generates a unique code for a VIP subscription.')
    async def generate_code(self, ctx, duration: str = '1m'):
        try:
            # check if the user has the role of admin or owner
            if not ctx.author.guild_permissions.administrator:
                await ctx.send('You are not allowed to use this command.')
                return
            
            # check if user exists in the database and add them if not
            admin_id = ctx.author.id
            username = ctx.author.name + "#" + ctx.author.discriminator
            self.check_and_add_user(admin_id, username)
            
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
            new_unique_code_record = (code, expiry_date, duration_id, admin_id)
            self.db_cursor.execute("INSERT INTO unique_codes (code, expiry_date, duration_id, admin_id) VALUES (?, ?, ?, ?)", new_unique_code_record)
            self.db_conn.commit()


            if duration_value > 1:
                duration_unit += 's'

            # send the code to the user
            # make the code into embed with inline fieds (title : code, field1: duration, field2: expiry date)
            # send message "problem with embeds"
            embed = discord.Embed(title=code)
            embed.add_field(name='Duration', value=f'{duration_value} {duration_unit}', inline=False)
            embed.add_field(name='Expiry date', value=expiry_date, inline=False)
            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(self.get_error_message())


    @commands.command(name='redeem', aliases=['claim'], help='Redeems a unique code for a VIP subscription.')
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
            active_subscriptions = self.get_active_subscriptions(user_id)
            if active_subscriptions:
                new_end_date = self.extend_subscription(active_subscriptions[-1], duration_record, action_type='redeem')
                subscription_id = active_subscriptions[-1]['id']
            else:
                self.insert_new_subscription(user_id, duration_record, action_type='redeem')
                subscription_id = self.get_subscription_id(user_id)
                
            # mark the code as redeemed
            self.mark_code_as_redeemed(code_record[0], subscription_id)
            
            # Change user role to VIP if not already
            if not discord.utils.get(ctx.author.roles, name='VIP'):
                await ctx.author.add_roles(discord.utils.get(ctx.guild.roles, name='VIP'))

            duration_value = duration_record[1]
            duration_unit = duration_record[2]
            if duration_value > 1:
                duration_unit += 's'

            if active_subscriptions:
                embed = discord.Embed(title='Extension', description=f'Your subscription has been extended:')
                embed.add_field(name='By (duration):', value=f'{duration_value} {duration_unit}', inline=False)
                embed.add_field(name='From (old end-date)', value=active_subscriptions[-1]["end_date"], inline=False)
                embed.add_field(name='To (new end-date)', value=new_end_date, inline=False)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title='Activation', description=f'Your subscription has been actiaved:')
                embed.add_field(name='For (duration):', value=f'{duration_value} {duration_unit}', inline=False)
                # embed.add_field(name='Until (end-date)', value=self.get_end_date(user_id), inline=False)
                await ctx.send(f'Your subscription has been actiaved for {duration_value} {duration_unit}. Enjoy!')
                
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(self.get_error_message())

    @commands.command(name='grant', aliases=['bless'], help='Grants a VIP subscription to a user.')
    async def grant(self, ctx, member: discord.Member, duration: str = '1m'):
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

            # check if the user already has a subscription and if so, then update the end_date, otherwise insert a new subscription
            active_subscriptions = self.get_active_subscriptions(user_id)
            if active_subscriptions:
                subscription = active_subscriptions[-1]
                new_end_date = self.extend_subscription(subscription, duration_record, action_type='grant')
            else:
                self.insert_new_subscription(user_id, duration_record, action_type='grant')

            # Change user role to VIP if not already
            if not discord.utils.get(member.roles, name='VIP'):
                await member.add_roles(discord.utils.get(ctx.guild.roles, name='VIP'))
            
            if duration_value > 1:
                duration_unit += 's'

            if active_subscriptions:
                embed = discord.Embed(title='Extension', description=f'Member **{member.name}**\'s subscription has been extended:')
                embed.add_field(name='By (duration):', value=f'{duration_value} {duration_unit}', inline=False)
                embed.add_field(name='From (old end-date)', value=active_subscriptions[-1]["end_date"], inline=False)
                embed.add_field(name='To (new end-date)', value=new_end_date, inline=False)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title='Activation', description=f'Member **{member.name}**\'s subscription has been actiaved:')
                embed.add_field(name='For (duration):', value=f'{duration_value} {duration_unit}', inline=False)
                # embed.add_field(name='Until (end-date)', value=self.get_end_date(user_id), inline=False)
                await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(self.get_error_message())

    @commands.command(name='revoke', aliases=['reduce', 'curse']) 
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
                    embed = discord.Embed(title='Revoke', description=f'Member **{member.name}**\'s subscription has been revoked.')
                    # embed.add_field(name='Until (end-date)', value=curse_date, inline=False)
                    await ctx.send(embed=embed)

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

    @commands.command(name='check', aliases=['status', 'vip'])
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
                remaining_days = (datetime.datetime.strptime(subscription["end_date"], "%Y-%m-%d %H:%M:%S") - datetime.datetime.now()).days
                if not discord.utils.get(ctx.author.roles, name='VIP'):
                    await ctx.author.add_roles(vip_role)
                    embed = discord.Embed(title='Reinstatement', description=f'Your VIP subscription has been reinstated:')
                    embed.add_field(name='Until (end-date)', value=subscription["end_date"], inline=False)
                    embed.add_field(name='Remaining days', value=remaining_days, inline=False)
                else:
                    embed = discord.Embed(title='Status', description=f'Your VIP subscription is active:')
                    embed.add_field(name='Until (end-date)', value=subscription["end_date"], inline=False)
                    embed.add_field(name='Remaining days', value=remaining_days, inline=False)
            else:
                if vip_role in ctx.author.roles:
                    await ctx.author.remove_roles(vip_role)
                embed = discord.Embed(title='Status', description=f'You do not have an active subscription.')

            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(self.get_error_message())

    @commands.command(name='info', aliases=['code', 'validity', 'val'])
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
            embed = discord.Embed(title='Code info', description=code)
            embed.add_field(name='Status', value='Unclaimed', inline=False)
            embed.add_field(name='Duration', value=f'{duration_value} {duration_unit}', inline=False)
            embed.add_field(name='Expiry date', value=expiry_date, inline=False)
            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(self.get_error_message())

    @commands.command(name="keep")
    async def keep(self, ctx, member: discord.Member):
        # Add the member's user ID to the perm_vips dictionary
        self.perm_vips[member.id] = True

        # Inform the user that the member will keep the "Premium" role
        await ctx.send(f"{member.mention} will keep the VIP role. **(Permanently! Database and other features not fully working yet)**")

    # @commands.command(name="get")
    # async def get_users(self, ctx, member: discord.Member):
        

    #     # Inform the user that the member will keep the "Premium" role
    #     await ctx.send(f"{member.mention} will keep the VIP role. **(Permanently! Database and other features not fully working yet)**")

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
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Get the "Premium" role
        vip_role = discord.utils.get(member.guild.roles, name="VIP")

        print(f"{member} joined the server!")

        # check if user (member not ctx) exists in the database and add them if not
        member_uid = member.id
        username = member.name + "#" + member.discriminator
        isNewUser = self.check_and_add_user(member_uid, username)

        # check if member is in the database, if he is don't give hime vip role
        if isNewUser:
            await member.add_roles(vip_role)
            # send him a private message informing him that he has been given the vip role temporarily as a free-trial, and if he paid he will get reinstaited (in an embed)
            owner_role = discord.utils.get(member.guild.roles, name="Owner")
            owner_members = [member for member in member.guild.members if owner_role in member.roles]
            admin_role = discord.utils.get(member.guild.roles, name="Admin")
            admin_members = [member for member in member.guild.members if admin_role in member.roles]

            guild_name = member.guild.name
            # embed = discord.Embed(title=f'{guild_name} VIP role free trial', description=f'You have been given the VIP role temporarily. You will keep it for 5 minutes, after which it will be removed. However, if you already paid for the VIP role, you will get reinstated automatically.')
            member_embed = discord.Embed(title=f'تجربة مجانية لدور  MKL-Signal - VIP', description=f'لقد تم منحك دور **VIP** مؤقتًا. ستحتفظ بها لمدة 5 دقائق ، وبعد ذلك ستتم إزالتها. ومع ذلك ، إذا كنت قد دفعت بالفعل مقابل دور **VIP** ، فستتم إعادتك تلقائيًا.')
            await member.send(embed=member_embed)

            # loop through owners and admins and inform them
            admin_embed = discord.Embed(title=f'{guild_name} VIP role free trial for {member.mention}', description=f'{member.mention} has joined the server and has been given the VIP role temporarily. He will keep it for 5 minutes, after which it will be removed.')
            for owner in owner_members:
                await owner.send(embed=admin_embed)
            for admin in admin_members:
                await admin.send(embed=admin_embed)
            
            await asyncio.sleep(300)
            # check if user is still in the server and if he is, remove the vip role
            if member.id not in self.perm_vips and vip_role in member.roles:
                await member.remove_roles(vip_role)

                # embed = discord.Embed(title=f'{guild_name} VIP role free trial expired', description=f'Your VIP role free trial has expired. If you want to keep the VIP role, please contact one of the owners of the server.')
                member_embed = discord.Embed(title=f'انتهت الفترة التجريبية المجانية لدور  MKL-Signal - VIP ', description=f'انتهت صلاحية الإصدار التجريبي المجاني لدور VIP الخاص بك. إذا كنت ترغب في الاحتفاظ بدور **VIP**، يرجى الاتصال بأحد مالكي خادم **MKL-Signal**.')
                for owner in owner_members:
                    member_embed.add_field(name=f'{owner.mention}', inline=False)

                await member.send(embed=member_embed)

                admin_embed = discord.Embed(title=f'{guild_name} VIP role free trial expired for {member.mention}', description=f'{member.mention} has had his VIP role removed after the free trial expired. If he wants to keep the VIP role, he will have to contact one of the owners of the server.')
                for owner in owner_members:
                    admin_embed.add_field(name=f'{owner.mention}', inline=False)
                
                for owner in owner_members:
                    await owner.send(embed=admin_embed)
                for admin in admin_members:
                    await admin.send(embed=admin_embed)
                
            else:
                # Remove the member from the dictionary if they are in it
                del self.perm_vips[member.id]
                # embed = discord.Embed(title=f'{guild_name} VIP role free trial expired', description=f'Your VIP role free trial has expired, but you have paid for the VIP role, so you will keep it.')
                member_embed = discord.Embed(title=f'انتهت الفترة التجريبية المجانية لدور  MKL-Signal - VIP ', description=f'انتهت صلاحية الإصدار التجريبي المجاني لدور **VIP** الخاص بك ، لكنك دفعت مقابل دور **VIP** ، لذلك ستحتفظ به.')
                await member.send(embed=member_embed)

                admin_embed = discord.Embed(title=f'{guild_name} VIP role free trial expired for {member.mention}', description=f'{member.mention} has had his VIP role removed after the free trial expired, but he has paid for the VIP role, so he will keep it.')
                for owner in owner_members:
                    await owner.send(embed=admin_embed)
                for admin in admin_members:
                    await admin.send(embed=admin_embed)
            

    def check_and_add_user(self, discord_uid: int, username: str) -> None:
        # check if db_conn and db_cursor are open, and open them if not:
        isNewUser = False
        self.db_cursor.execute("SELECT * FROM users WHERE discord_uid = ?", (discord_uid,))
        self.db_conn.commit()
        if not self.db_cursor.fetchone():
            isNewUser = True
            self.db_cursor.execute("INSERT INTO users (discord_uid, username) VALUES (?, ?)", (discord_uid, username))
            self.db_conn.commit()
        return isNewUser

    def get_active_subscriptions(self, user_id: int) -> list[tuple]:
        query = """
        SELECT id, datetime(end_date)
        FROM subscriptions
        WHERE user_id = ?;
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
    
    def extend_subscription(self, subscription: tuple, duration_record: tuple, action_type: str) -> str:
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

        # Insert a new record into grants table or redeem table 
        # TODO: check if this is the right place to do this, and make some cleaning in the code (I am adding a redeem record elsewhere too)
        if action_type == 'grant':
            grant_record = (subscription['id'], action_type, datetime.datetime.now().strftime(DATETIME_FORMAT))
            self.db_cursor.execute("INSERT INTO grants (subscription_id, action_type, datetime) VALUES (?, ?, ?)", grant_record)
        elif action_type == 'redeem':
            redeem_record = (subscription['id'], action_type, datetime.datetime.now().strftime(DATETIME_FORMAT))
            self.db_cursor.execute("INSERT INTO redeems (subscription_id, action_type, datetime) VALUES (?, ?, ?)", redeem_record)
        self.db_conn.commit()
        

        return new_end_date_str

    def insert_new_subscription(self, user_id: int, duration_record: tuple, action_type: str) -> None:
        _, duration_value, duration_unit = duration_record
        if duration_unit == 'day':
            delta = datetime.timedelta(days=duration_value)
        elif duration_unit == 'month':
            delta = datetime.timedelta(days=duration_value * 30)

        start_date = datetime.datetime.now()
        end_date = start_date + delta

        # Insert the new subscription into the database
        new_subscription_record = (start_date.strftime(DATETIME_FORMAT), end_date.strftime(DATETIME_FORMAT), user_id)
        self.db_cursor.execute("INSERT INTO subscriptions (start_date, end_date, user_id) VALUES (?, ?, ?)", new_subscription_record)
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

