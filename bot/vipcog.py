import logging
import datetime
from datetime import timedelta
import traceback
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import asyncio
import os
from tabulate import tabulate

import operations as ops
import models as mdls
import utils as utls


load_dotenv()

ADMIN_USER_ID = os.environ['ADMIN_USER_ID']


class VIPCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.remove_command('help')
        self.perm_vips = {}
        self.silent = False
    
    def cog_unload(self):
        self.check_subs.cancel()

    @tasks.loop(hours=1)
    async def check_subscriptions(self):
        logging.info('Checking subscriptions...')
        guild = self.bot.guilds[0]
        vip_role = discord.utils.get(guild.roles, name="VIP")
        owner_role = discord.utils.get(member.guild.roles, name="Owner")
        owner_members = [member for member in member.guild.members if owner_role in member.roles]
        admin_role = discord.utils.get(member.guild.roles, name="Admin")
        admin_members = [member for member in member.guild.members if admin_role in member.roles]
        for member in guild.members:
            user, isNew = await utls.get_or_add_member(member)
            
            subscription = await ops.get_active_subscription(user)
            
            is_subscription_expired = False
            if subscription:
                if subscription.is_expired():
                    await ops.end_subscription(subscription)
                    is_subscription_expired = True
                        
                    embed_admin = utls.warning_embed(f'{member.mention}\'s VIP subscription has ended.')
                    embed_user = utls.warning_embed(f'Your VIP subscription has ended.')

                    await member.send(embed=embed_user)

                    for owner in owner_members:
                        await owner.send(embed=embed_admin)

                    for admin in admin_members:
                        await admin.send(embed=embed_admin)
                    
                elif subscription.is_expiring_soon(days=1):
                    if not discord.utils.get(member.roles, name='VIP'):
                        await member.add_roles(vip_role)

                    embed_admin = utls.warning_embed(f'{member.mention}\'s VIP subscription is about to end in less than 1 day.')
                    embed_user = utls.warning_embed(f'Your VIP subscription is about to end in less than 1 day.')

                    await member.send(embed=embed_user)

                    for owner in owner_members:
                        await owner.send(embed=embed_admin)

                    for admin in admin_members:
                        await admin.send(embed=embed_admin)

            if is_subscription_expired:
                if discord.utils.get(member.roles, name='VIP'):
                    await member.remove_roles(vip_role)
            else:
                if not discord.utils.get(member.roles, name='VIP'):
                    await member.add_roles(vip_role)
                

    # @tasks.loop(hours=1)
    # async def check_codes(self):
    #     pass

    @check_subscriptions.before_loop
    async def before_check_subs(self):
        await self.bot.wait_until_ready()  # wait until the bot logs in


    @commands.command(name='help', help='Returns the list of commands.')
    async def help(self, ctx):
        embed = utls.info_embed(title='VIP Bot', description='List of commands')
        embed.add_field(name='!help', value='Returns the list of commands.', inline=False)
        embed.add_field(name='!ping', value='Returns the latency of the bot.', inline=False)
        embed.add_field(name='!generate', value='Generates a unique code for a VIP subscription.', inline=False)
        embed.add_field(name='!redeem', value='Redeems a code for a VIP subscription.', inline=False)
        embed.add_field(name='!grant', value='Grants a VIP subscription to a user.', inline=False)
        embed.add_field(name='!revoke', value='Revokes a VIP subscription from a user.', inline=False)
        embed.add_field(name='!status', value='Checks the status of a VIP subscription.', inline=False)
        embed.add_field(name='!code', value='Checks the status of a unique code.', inline=False)
        embed.add_field(name='!listas', value='Lists all active VIP subscriptions.', inline=False)
        embed.add_field(name='!listus', value='Lists all VIP subscriptions of a user.', inline=False)
        embed.add_field(name='!quiet', value='Sets the bot to silent mode. No messages will be sent to members who get granted or revoked VIP subscriptions.', inline=False)
        embed.add_field(name='!unquiet', value='Resets the bot to normal mode. Messages will be sent to members who get granted or revoked VIP subscriptions.', inline=False)
        embed.add_field(name='!fcheck', value='Force Checks all VIP subscriptions.', inline=False)
        embed.add_field(name='!rega', value='Register and add all members of the server to the database.', inline=False)
        embed.add_field(name='!regav', value='Register and add all members of the server to the database and grant them a VIP subscription.', inline=False)
        
        await ctx.send(embed=embed)


    @commands.command(name='ping', help='Returns the latency of the bot.')
    async def ping(self, ctx):
        await ctx.send(embed=utls.info_embed(f'Pong! {round(self.bot.latency * 1000)}ms'))

    @commands.command(name='fcheck', aliases=['fc'], help='Forces the bot to check all subscriptions.')
    @commands.has_role('Admin')
    async def force_check(self, ctx):
        # check if the bot is currently checking subscriptions if not force it to check
        if not self.check_subs.is_running():
            await ctx.send(embed=utls.info_embed('Force checking subscriptions...'))
            await self.check_subscriptions()
            await ctx.send(embed=utls.success_embed('Force checked all subscriptions successfully.'))
        else:
            await ctx.send(embed=utls.warning_embed('The bot is already checking subscriptions at the moment. Please wait until it finishes.'))


    @commands.command(name='generate', aliases=['gen', 'forge'], help='Generates a unique code for a VIP subscription.')
    async def generate_code(self, ctx, duration: str = '1m'):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.send(embed=utls.error_embed('This command can not be used in private messages.'))
                return

            # check if the user has the role of admin or owner
            if not ctx.author.guild_permissions.administrator:
                await ctx.send(embed=utls.error_embed('You are not allowed to use this command.'))
                return
            
            # check if user exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)
            
            # check if the duration is valid
            sub_duration, err_msg = await utls.validate_duration(duration)
            if err_msg:
                await ctx.send(embed=utls.error_embed(err_msg))
                return

            # generate a unique code
            code = await utls.gen_unique_code(12)

            # generate an expiry date
            expiry_date = (datetime.datetime.now() + datetime.timedelta(days=7))
            
            # create a new unique code record
            unique_code = mdls.UniqueCode(code, expiry_date, sub_duration, admin)

            # insert the new unique code record into the database
            await ops.add_unique_code(unique_code)

            
            embed = utls.success_embed(title=code, description='This code can be redeemed for a VIP subscription.')
            embed.add_field(name='Duration', value=f"{sub_duration.duration} {sub_duration.unit}{'s' if sub_duration.duration > 1 else ''}", inline=False)
            embed.add_field(name='Expiry date', value=utls.datetime_to_string(expiry_date), inline=False)
            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(embed=utls.error_embed(self.get_error_message()))


    @commands.command(name='redeem', aliases=['claim'], help='Redeems a unique code for a VIP subscription.')
    async def redeem_code(self, ctx, code: str):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.send(embed=utls.error_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner (amins can not claim codes)
            if ctx.author.guild_permissions.administrator:
                await ctx.send(embed=utls.error_embed('You are not allowed to use this command.'))
                return
            
            # check if user exists in the database and add them if not
            user, isNew = await utls.get_or_add_member(ctx.author)

            # check if the code exists in the database and whether it has been claimed or not
            unique_code, err_msg = await utls.validate_code(code)
            if err_msg:
                await ctx.send(embed=utls.error_embed(err_msg))
                return

            # get the duration of the code
            duration = unique_code.duration

            # mark the code as redeemed
            await ops.redeem_code(unique_code, user) # TODO: FIX THIS

            # check if the user already has a subscription and if so, if end_date is not expired yet and still active, then update the end_date, otherwise insert a new subscription
            subscription = await ops.get_active_subscription(user)
            extension = False
            if subscription:
                extension = True
                subscription, original_end_date = await ops.extend_subscription(subscription, duration)
            else:
                subscription = await ops.create_subscription(user, duration)
            
            # Change user role to VIP if not already
            if not discord.utils.get(ctx.author.roles, name='VIP'):
                await ctx.author.add_roles(discord.utils.get(ctx.guild.roles, name='VIP'))

            if extension:
                embed = utls.success_embed(title='Extension', description=f'Your subscription has been extended:')
                embed.add_field(name='By (duration):', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
                embed.add_field(name='From (old end-date)', value=utls.datetime_to_string(original_end_date), inline=False)
                embed.add_field(name='To (new end-date)', value=utls.datetime_to_string(subscription.end_date), inline=False)
            else:
                embed = utls.success_embed(title='Activation', description=f'Your subscription has been actiaved:')
                embed.add_field(name='For (duration):', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
                embed.add_field(name='Until (end-date)', value=utls.datetime_to_string(subscription.end_date), inline=False)

            await ctx.send(embed=embed)
                
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(embed=utls.error_embed(self.get_error_message()))

    @commands.command(name='grant', aliases=['bless'], help='Grants a VIP subscription to a user.')
    async def grant(self, ctx, member: discord.Member, duration: str = '1m'):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.send(embed=utls.error_embed('This command can not be used in private messages.'))
                return

            # check if the user has the role of admin or owner (amins can not claim codes)
            if not ctx.author.guild_permissions.administrator:
                await ctx.send(embed=utls.error_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            # check if user exists in the database and add them if not
            user, isNew = await utls.get_or_add_member(member)

            # check if the duration is valid
            sub_duration, err_msg = await utls.validate_duration(duration)
            if err_msg:
                await ctx.send(embed=utls.error_embed(err_msg))
                return

            # check if the user already has a subscription and if so, if end_date is not expired yet and still active, then update the end_date, otherwise insert a new subscription
            subscription = await ops.get_active_subscription(user)
            extension = False
            if subscription:
                extension = True
                subscription, original_end_date = await ops.extend_subscription(subscription, duration)
            else:
                subscription = await ops.create_subscription(user, duration)

            # Change user role to VIP if not already
            if not discord.utils.get(member.roles, name='VIP'):
                await member.add_roles(discord.utils.get(ctx.guild.roles, name='VIP'))

            # add the grant to the database
            grant_date = datetime.datetime.now()
            action_type = 'extend' if extension else 'grant' if extension else None
            grant = mdls.Grant(grant_date, action_type, original_end_date, subscription.end_date, sub_duration, subscription, admin, user)
            await ops.add_grant(grant)

            # send success message to admin and user
            quiet_mode = 'Enabled, member will not be notified' if self.silent else 'Disabled, member will be notified'
            if extension:
                embed_admin = utls.success_embed(title='Extension', description=f'Member **{member.name}**\'s subscription has been extended:')
                embed_admin.add_field(name='By (duration):', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
                embed_admin.add_field(name='From (old end-date)', value=utls.datetime_to_string(original_end_date), inline=False)
                embed_admin.add_field(name='To (new end-date)', value=utls.datetime_to_string(subscription.end_date), inline=False)
                embed_admin.add_field(name='Quiet mode:', value=quiet_mode, inline=False)

                embed_user = utls.success_embed(title='Extension', description=f'Your subscription has been extended:')
                embed_user.add_field(name='By (duration):', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
                embed_user.add_field(name='From (old end-date)', value=utls.datetime_to_string(original_end_date), inline=False)
                embed_user.add_field(name='To (new end-date)', value=utls.datetime_to_string(subscription.end_date), inline=False)
            else:
                embed_admin = utls.success_embed(title='Activation', description=f'Member **{member.name}**\'s subscription has been actiaved:')
                embed_admin.add_field(name='For (duration):', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
                embed_admin.add_field(name='Until (end-date)', value=utls.datetime_to_string(subscription.end_date), inline=False)
                embed_admin.add_field(name='Quiet mode:', value=quiet_mode, inline=False)

                embed_user = utls.success_embed(title='Activation', description=f'Your subscription has been actiaved:')
                embed_user.add_field(name='For (duration):', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
                embed_user.add_field(name='Until (end-date)', value=utls.datetime_to_string(subscription.end_date), inline=False)

            await ctx.send(embed=embed_admin)

            if not self.silent:
                await member.send(embed=embed_user)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(embed=utls.error_embed(self.get_error_message()))

    @commands.command(name='revoke', aliases=['reduce', 'curse']) 
    async def revoke(self, ctx, member: discord.Member, duration: str = ''):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.send(embed=utls.error_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner (amins can not claim codes)
            if not ctx.author.guild_permissions.administrator:
                await ctx.send(embed=utls.error_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            # check if user exists in the database and add them if not
            user, isNew = await utls.get_or_add_member(member)

            # check if the user already has a subscription
            subscription = await ops.get_active_subscription(user)

            if not subscription:
                await ctx.send(embed=utls.error_embed(f'Member **{member.name}** does not have an active subscription.'))
                return

            if duration:
                # check if the duration is valid
                sub_duration, err_msg = await utls.validate_duration(duration)
                if err_msg:
                    await ctx.send(embed=utls.error_embed(err_msg))
                    return
                
                # reduce the user's active subscription by reducing the end_date by the duration
                subscription, original_end_date = await ops.reduce_subscription(subscription, duration)
            else:
                # remove the user's active subscription by updating the end_date to now
                subscription, original_end_date = await ops.revoke_subscription(subscription)

            # add the revoke to the database
            revoke_date = datetime.datetime.now()
            action_type = 'reduce' if duration else 'revoke'
            revoke = mdls.Revoke(revoke_date, action_type, original_end_date, subscription.end_date, sub_duration, subscription, admin, user)
            await ops.add_revoke(revoke)
                

            quiet_mode = 'Enabled, member will not be notified' if self.silent else 'Disabled, member will be notified'
            if duration and not subscription.is_expired():
                embed_admin = utls.success_embed(title='Duration Reduce', description=f'Member **{member.name}**\'s subscription duration has been reduced:')
                embed_admin.add_field(name='By (duration):', value=f"{sub_duration.duration} {sub_duration.unit}{'s' if sub_duration.duration > 1 else ''}", inline=False)
                embed_admin.add_field(name='From (old end-date)', value=utls.datetime_to_string(original_end_date), inline=False)
                embed_admin.add_field(name='To (new end-date)', value=utls.datetime_to_string(subscription.end_date), inline=False)
                embed_admin.add_field(name='Quiet Mode', value=quiet_mode, inline=False)

                embed_user = utls.warning_embed(title='Duration Reduce', description=f'Your subscription duration has been reduced:')
                embed_user.add_field(name='By (duration):', value=f"{sub_duration.duration} {sub_duration.unit}{'s' if sub_duration.duration > 1 else ''}", inline=False)
                embed_user.add_field(name='From (old end-date)', value=utls.datetime_to_string(original_end_date), inline=False)
                embed_user.add_field(name='To (new end-date)', value=utls.datetime_to_string(subscription.end_date), inline=False)
            else:
                await member.remove_roles(discord.utils.get(ctx.guild.roles, name='VIP'))
                embed_admin = utls.success_embed(title='Revoke', description=f'Member **{member.name}**\'s subscription has been revoked.')
                embed_admin.add_field(name='Quiet Mode', value=quiet_mode, inline=False)
                embed_user = utls.warning_embed(title='Revoke', description=f'Your subscription has been revoked.')
            

            await ctx.send(embed=embed_admin)

            if not self.silent:
                await member.send(embed=embed_user)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(embed=utls.error_embed(self.get_error_message()))


    @commands.command(name='status', aliases=['check', 'vip'])
    async def status(self, ctx):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.send(embed=utls.error_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner (amins can not check status)
            if ctx.author.guild_permissions.administrator:
                await ctx.send(embed=utls.error_embed('You are not allowed to use this command as an admin.'))
                return
            
            # check if admin exists in the database and add them if not
            user, isNew = await utls.get_or_add_member(ctx.author)

            vip_role = discord.utils.get(ctx.guild.roles, name='VIP')

            # check if the user already has a subscription and if so, get the remaining days
            subscription = await ops.get_active_subscription(user)
            if subscription:
                # check if the user has the VIP role and if not, add it
                if not discord.utils.get(ctx.author.roles, name='VIP'):
                    await ctx.author.add_roles(vip_role)
                remaining_days = (subscription.end_date - datetime.datetime.now()).days
                embed = utls.info_embed(title='Status', description=f'Your VIP subscription is active:')
                embed.add_field(name='Until (end-date)', value=utls.datetime_to_string(subscription.end_date), inline=False)
                embed.add_field(name='Remaining days', value=remaining_days, inline=False)
            else:
                # check if the user has the VIP role and if so, remove it
                if discord.utils.get(ctx.author.roles, name='VIP'):
                    await ctx.author.remove_roles(vip_role)
                embed = utls.info_embed(title='Status', description=f'You do not have an active VIP subscription.')

            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(embed=utls.error_embed(self.get_error_message()))

    @commands.command(name='code', aliases=['validity', 'val'])
    async def code_status(self, ctx, code: str): # send code duration and status
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.send(embed=utls.error_embed('This command can not be used in private messages.'))
                return
            
            # check if admin exists in the database and add them if not
            user, isNew = await utls.get_or_add_member(ctx.author)

            # check if the code exists in the database and whether it has been claimed or not
            unique_code, err_msg = await utls.validate_code(code)
            if err_msg:
                await ctx.send(embed=utls.warning_embed(title='Code Status', description=err_msg))
                return
            
            # get the duration of the code
            duration = unique_code.duration

            # send code status
            embed = utls.info_embed(title='Code Status', description=code)
            embed.add_field(name='Status', value='Unclaimed', inline=False)
            embed.add_field(name='Duration', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
            embed.add_field(name='Expiry date', value=utls.datetime_to_string(unique_code.expiry_date), inline=False)

            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(embed=utls.error_embed(self.get_error_message()))

    @commands.command(name="keep")
    async def keep(self, ctx, member: discord.Member):
        # Add the member's user ID to the perm_vips dictionary
        self.perm_vips[member.id] = True

        # Inform the user that the member will keep the "VIP" role
        await ctx.send(f"{member.mention} will keep the VIP role. **(Permanently! Database and other features not fully working yet)**")

    @commands.command(name="quiet")
    async def quiet(self, ctx, member: discord.Member):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.send(embed=utls.error_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner (amins can not claim codes)
            if not ctx.author.guild_permissions.administrator:
                await ctx.send(embed=utls.error_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            self.silent = True
            
            description = f'Quiet mode has been enabled by {ctx.author.mention}. Granting, Extending, Revoking, and Reducing VIP roles will not send warning messages to the user.'
            embed = utls.success_embed(title='Quiet mode', description=description)

            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(embed=utls.error_embed(self.get_error_message()))


    @commands.command(name="unquiet")
    async def unquiet(self, ctx, member: discord.Member):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.send(embed=utls.error_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner (amins can not claim codes)
            if not ctx.author.guild_permissions.administrator:
                await ctx.send(embed=utls.error_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            self.silent = False

            description = f'Quiet mode has been disabled by {ctx.author.mention}. Granting, Extending, Revoking, and Reducing VIP roles will not send warning messages to the user.'
            embed = utls.success_embed(title='Quiet mode', description=description)

            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(embed=utls.error_embed(self.get_error_message()))


    @commands.command(name="listas", aliases=['asinfo'])
    async def active_subs_info(self, ctx):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.send(embed=utls.error_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner
            if ctx.author.guild_permissions.administrator:
                await ctx.send(embed=utls.error_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            # get all the members in the database
            subscriptions = await ops.get_active_subscriptions()

            table_data = []
            for subscription in subscriptions:
                status = 'Active' if subscription.active else 'Expired'
                user = subscription.user
                row = [user.username, subscription.start_date, subscription.end_date, status]
                table_data.append(row)

            table = tabulate(table_data, headers=["Username", "Start Date", "End Date", "Status"], tablefmt="pretty")

            embed = utls.success_embed(title='Active Subscriptions', description=table)

            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(embed=utls.error_embed(self.get_error_message()))


    @commands.command(name="listus", aliases=['usinfo'])
    async def user_sub_info(self, ctx, member: discord.Member):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.send(embed=utls.error_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner
            if ctx.author.guild_permissions.administrator:
                await ctx.send(embed=utls.error_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            # check if admin exists in the database and add them if not
            user, isNew = await utls.get_or_add_member(member)

            subscriptions = user.subscriptions
            
            table_data = []
            for subscription in subscriptions:
                status = 'Active' if subscription.active else 'Expired'
                row = [subscription.id, subscription.start_date, subscription.end_date, status]
                table_data.append(row)

            table = tabulate(table_data, headers=["Subscription ID", "Start Date", "End Date", "Status"], tablefmt="pretty")
            embed = utls.info_embed(title="User's Subscriptions Information", description=table)

            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(embed=utls.error_embed(self.get_error_message()))


    @commands.command(name="rega")
    async def register_all(self, ctx): # Add all members of the server to the database for the specified duration
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.send(embed=utls.error_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner
            if ctx.author.guild_permissions.administrator:
                await ctx.send(embed=utls.error_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            # get all the members of the server
            members = ctx.guild.members

            # add all the members to the database
            for member in members:
                user, isNew = await utls.get_or_add_member(member)

            embed = utls.success_embed(title='All members have been added to the database successfully.')

            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(embed=utls.error_embed(self.get_error_message()))


    @commands.command(name="regav")
    async def register_all_vips(self, ctx, duration): # Add and subscribe all members of the server with a vip role to the database for the specified duration
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.send(embed=utls.error_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner
            if ctx.author.guild_permissions.administrator:
                await ctx.send(embed=utls.error_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            # check if the duration is valid
            duration, err_msg = await utls.validate_duration(duration)
            if err_msg:
                await ctx.send(embed=utls.error_embed(err_msg))
                return

            # get the vip role
            vip_role = discord.utils.get(ctx.guild.roles, name="VIP")

            # get all the members with the vip role
            members = vip_role.members

            # add all the members to the database
            for member in members:
                user, isNew = await utls.get_or_add_member(member)
                subscription = await ops.get_active_subscription(user)
                if subscription is None:
                    await ops.create_subscription(user, duration)

            embed = utls.success_embed('All members with the VIP role and without a subscription have been added to the database and subscribed to the VIP role.')
            embed.add_field(name='For (duration):', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
            embed.add_field(name='Until (end-date)', value=utls.datetime_to_string(subscription.end_date), inline=False)

            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.send(embed=utls.error_embed(self.get_error_message()))


    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # get the vip role
        vip_role = discord.utils.get(member.guild.roles, name="VIP")

        logging.info(f"{member} joined the server!")

        # check if admin exists in the database and add them if not
        user, isNew = await utls.get_or_add_member(member)

        # check if member is in the database, if he is don't give hime vip role
        if not isNew:
            return
        
        await member.add_roles(vip_role)
        # send him a private message informing him that he has been given the vip role temporarily as a free-trial, and if he paid he will get reinstaited (in an embed)
        owner_role = discord.utils.get(member.guild.roles, name="Owner")
        owner_members = [member for member in member.guild.members if owner_role in member.roles]
        admin_role = discord.utils.get(member.guild.roles, name="Admin")
        admin_members = [member for member in member.guild.members if admin_role in member.roles]

        guild_name = member.guild.name
        # embed = utls.info_embed(title=f'{guild_name} VIP role free trial', description=f'You have been given the VIP role temporarily. You will keep it for 5 minutes, after which it will be removed. However, if you already paid for the VIP role, you will get reinstated automatically.')
        member_embed = utls.info_embed(title=f'تجربة مجانية لدور  MKL-Signals - VIP', description=f'لقد تم منحك دور **VIP** مؤقتًا. ستحتفظ بها لمدة 5 دقائق ، وبعد ذلك ستتم إزالتها. ومع ذلك ، إذا كنت قد دفعت بالفعل مقابل دور **VIP** ، فستتم إعادتك تلقائيًا.')
        await member.send(embed=member_embed)

        # loop through owners and admins and inform them
        member_name = member.name + "#" + member.discriminator
        admin_embed = utls.info_embed(title=f'{guild_name} VIP role free trial for {member_name}', description=f'{member.mention} has joined the server and has been given the VIP role temporarily. He will keep it for 5 minutes, after which it will be removed.')
        for owner in owner_members:
            await owner.send(embed=admin_embed)
        for admin in admin_members:
            await admin.send(embed=admin_embed)
        
        await asyncio.sleep(300)
        # check if user is still in the server and if he is, remove the vip role
        if member.id not in self.perm_vips and vip_role in member.roles:
            await member.remove_roles(vip_role)

            # embed = utls.info_embed(title=f'{guild_name} VIP role free trial expired', description=f'Your VIP role free trial has expired. If you want to keep the VIP role, please contact one of the owners of the server.')
            member_embed = utls.info_embed(title=f'انتهت الفترة التجريبية المجانية لدور  MKL-Signals - VIP ', description=f'انتهت صلاحية الإصدار التجريبي المجاني لدور VIP الخاص بك. إذا كنت ترغب في الاحتفاظ بدور **VIP**، يرجى الاتصال بأحد مالكي خادم **MKL-Signals**.')
            for owner in owner_members:
                owner_name = owner.name + "#" + owner.discriminator
                member_embed.add_field(name=f'{owner_name}', value=f'{owner.mention}', inline=False)
            await member.send(embed=member_embed)

            admin_embed = utls.info_embed(title=f'{guild_name} VIP role free trial expired for {member_name}', description=f'{member.mention} has had his VIP role removed after the free trial expired. If he wants to keep the VIP role, he will have to contact one of the owners of the server.')
            for owner in owner_members:
                owner_name = owner.name + "#" + owner.discriminator
                admin_embed.add_field(name=f'{owner_name}', value=f'{owner.mention}', inline=False)
            
            for owner in owner_members:
                await owner.send(embed=admin_embed)
            for admin in admin_members:
                await admin.send(embed=admin_embed)
            
        else:
            # Remove the member from the dictionary if they are in it
            del self.perm_vips[member.id]
            # embed = utls.info_embed(title=f'{guild_name} VIP role free trial expired', description=f'Your VIP role free trial has expired, but you have paid for the VIP role, so you will keep it.')
            member_embed = utls.info_embed(title=f'انتهت الفترة التجريبية المجانية لدور  MKL-Signals - VIP ', description=f'انتهت صلاحية الإصدار التجريبي المجاني لدور **VIP** الخاص بك ، لكنك دفعت مقابل دور **VIP** ، لذلك ستحتفظ به.')
            await member.send(embed=member_embed)

            admin_embed = utls.info_embed(title=f'{guild_name} VIP role free trial expired for {member_name}', description=f'{member.mention} has had his VIP role removed after the free trial expired, but he has paid for the VIP role, so he will keep it.')
            for owner in owner_members:
                await owner.send(embed=admin_embed)
            for admin in admin_members:
                await admin.send(embed=admin_embed)


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
        
        await self.send_private_error_notification(ctx.author.name, ctx.command.name, traceback.format_exc())

    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        await self.send_private_error_notification("on_error", event, traceback.format_exc())
        
    async def send_private_error_notification(self, username: str, command: str, error_message: str):
        owner_id = ADMIN_USER_ID
        owner = await self.bot.fetch_user(owner_id)
        await owner.send(embed=utls.error_embed(f"An error occurred (u: {username}, c: {command}): {error_message}"))
