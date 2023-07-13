import logging
from datetime import datetime, timedelta
import time
import traceback
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import asyncio
import os
from tabulate import tabulate
import csv
import io

import operations as ops
import models as mdls
import utils as utls

load_dotenv()

ADMIN_USER_ID = os.environ['ADMIN_USER_ID']

class NewMemberButtonsView(discord.ui.View):
    @discord.ui.button(label='Grant', row=0, style=discord.ButtonStyle.primary)
    async def grant(self, button: discord.ui.Button, interaction: discord.Interaction):
        button.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Kick', row=1, style=discord.ButtonStyle.danger)
    async def kick(self, button: discord.ui.Button, interaction: discord.Interaction):
        button.disabled = True
        await interaction.response.edit_message(view=self)


class VIPCommand(commands.Cog):
    def __init__(self, bot):
        ops.init_db()
        self.bot = bot
        self.bot.remove_command('help')
        self.perm_vips = {}
        self.task_check_subscriptions.start()
        self.sub_check_in_progress = False
        self.backup_in_progress = False
        self.silent = True
        self.sub_check_mode = False
        self.role_change_mode = False
        
    
    def cog_unload(self):
        self.task_check_subscriptions.cancel()

    @tasks.loop(hours=12)
    async def task_check_subscriptions(self):
        if self.sub_check_mode:
            await self.check_subscriptions()

    @tasks.loop(hours=24)
    async def backup_db(self):
        self.backup_in_progress = True
        logging.info('Backing up database...')
        backup_file, err_msg = await ops.backup_database()
        self.backup_in_progress = False
        if err_msg:
            logging.error(err_msg)
            await self.send_private_error_notification(error_message=err_msg)
            return
        logging.info(f'Database backed up to {backup_file}')

    # @tasks.loop(hours=1)
    # async def check_codes(self):
    #     pass

    @task_check_subscriptions.before_loop
    async def before_task_check_subscriptions(self):
        await self.bot.wait_until_ready()  # wait until the bot logs in


    # @discord.slash_command(name='help', description='Returns the list of User commands.')
    @discord.slash_command(name='help', description='Returns the list of User commands.')
    async def help(self, ctx):
        embed = utls.info_embed(title='Member commands', description='List of member commands')
        embed.add_field(name='/help', value='Returns the list of commands.', inline=False)
        embed.add_field(name='/ping', value='Returns the latency of the bot.', inline=False)
        embed.add_field(name='/redeem <code>', value='Redeems a code for a VIP subscription.', inline=False)
        embed.add_field(name='/status', value='Checks the status of a VIP subscription.', inline=False)
        embed.add_field(name='/code <code>', value='Checks the status of a unique code.', inline=False)
        await ctx.respond(embed=embed)


    # @commands.has_guild_permissions(administrator=True)
    @discord.slash_command(name='help1', description='Returns the list of Admin commands.')
    async def help1(self, ctx):
        embed = utls.owner_embed(title='Admin commands', description='List of admin level commands. Only server admins can use these commands.')
        embed.add_field(name='/help', value='Returns the list of User commands.', inline=False)
        embed.add_field(name='/help1', value='Returns the list of Admin commands.', inline=False)
        embed.add_field(name='/help2', value='Returns the list of Advanced Admin commands.', inline=False)
        embed.add_field(name='/ping', value='Returns the latency of the bot.', inline=False)
        embed.add_field(name='/generate', value='Generates a unique code for a VIP subscription.', inline=False)
        embed.add_field(name='/grant <@User> <duration>', value='Grants a VIP subscription to a user. Duration is optional.', inline=False)
        embed.add_field(name='/revoke <@User> <duration>', value='Revokes a VIP subscription from a user. Duration is optional.', inline=False)
        embed.add_field(name='/ustatus <@User>', value='Checks the status of a user.', inline=False)
        embed.add_field(name='/code <code>', value='Checks the status of a unique code.', inline=False)
        embed.add_field(name='/quiet', value='Sets the bot to silent mode. No messages will be sent to members who get granted or revoked VIP subscriptions.', inline=False)
        embed.add_field(name='/unquiet', value='Resets the bot to normal mode. Messages will be sent to members who get granted or revoked VIP subscriptions.', inline=False)
        await ctx.respond(embed=embed)


    # @commands.has_guild_permissions(administrator=True)
    @discord.slash_command(name='help2', description='Returns the list of Advanced Admin commands.')
    async def help2(self, ctx):
        embed = utls.advanced_embed(title='Advanced Admin commands', description='List of Advanced Admin level commands. Only server admins can use these commands. These commands are dangerous and should be used with caution.')
        embed.add_field(name='/listas', value='Lists all active VIP subscriptions.', inline=False)
        embed.add_field(name='/listu', value='Lists all users.', inline=False)
        embed.add_field(name='/listus <@User>', value='Lists all VIP subscriptions of a user.', inline=False)
        embed.add_field(name='/rega', value='Register and add all members of the server to the database.', inline=False)
        embed.add_field(name='/regav', value='Register and add all members with a VIP role to the database and grant them a VIP subscription.', inline=False)
        embed.add_field(name='/massrv', value='Mass remove all vip roles.', inline=False)
        embed.add_field(name='/fcheck', value='Force Checks all VIP subscriptions.', inline=False)
        embed.add_field(name='/fbackup', value='Force Backups the database.', inline=False)
        embed.add_field(name='/setsub <@User> <start date> <duration in days>', value='Sets a VIP subscription for a user. Duration is optional.', inline=False)
        
        await ctx.respond(embed=embed)


    # @commands.has_guild_permissions(administrator=True)
    @discord.slash_command(name='fcheck', aliases=['fc'], description='Forces the bot to check all subscriptions.')
    async def force_check(self, ctx):
        # check if the user has the role of admin or owner
        if not ctx.author.guild_permissions.administrator:
            await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
            return
        # record time spent checking subscriptions
        if not self.sub_check_in_progress:
            start_time = time.time()
            await ctx.respond(embed=utls.info_embed('Force checking subscriptions...'))
            records_checked, records_updated = await self.check_subscriptions()
            end_time = time.time()
            embed=utls.success_embed(f'Force checked all subscriptions successfully.')
            embed.add_field(name='Time spent:', value=f'{round(end_time - start_time, 2)} seconds', inline=False)
            embed.add_field(name='Users checked', value=f'{records_checked} users', inline=False)
            embed.add_field(name='Subscriptions updated', value=f'{records_updated} subscriptions', inline=False)
            await ctx.respond(embed=embed)
        else:
            await ctx.respond(embed=utls.warning_embed('The bot is already checking subscriptions at the moment. Please wait until it finishes.'))


    # @commands.has_guild_permissions(administrator=True)
    @discord.slash_command(name='fbackup', aliases=['fb'], description='Forces the bot to backup the database.')
    async def force_backup(self, ctx):
        # check if the user has the role of admin or owner
        if not ctx.author.guild_permissions.administrator:
            await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
            return
        # record time spent backing up database
        if not self.backup_in_progress:
            start_time = time.time()
            await ctx.respond(embed=utls.info_embed('Force backing up database...'))
            logging.info('Forcing backup...')
            await ops.backup_database()
            logging.info('Backup complete.')
            end_time = time.time()
            embed=utls.success_embed(f'Force backed up database successfully.')
            embed.add_field(name='Time spent:', value=f'{round(end_time - start_time, 2)} seconds', inline=False)
            await ctx.respond(embed=embed)
        else:
            await ctx.respond(embed=utls.warning_embed('The bot is already backing up the database at the moment. Please wait until it finishes.'))


    @discord.slash_command(name='ping', description='Returns the latency of the bot.')
    async def ping(self, ctx):
        await ctx.respond(embed=utls.info_embed(f'Pong! {round(self.bot.latency * 1000)}ms'))


    # @discord.slash_command(name='generate', aliases=['gen', 'forge'], description='Generates a unique code for a VIP subscription.')
    @discord.slash_command(name='generate', description='Generates a unique code for a VIP subscription.')
    async def generate_code(self, ctx, duration: str = '1m'):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return

            # check if the user has the administrator permission
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if user exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)
            
            # check if the duration is valid
            duration, err_msg = await utls.validate_duration(duration)
            if err_msg:
                await ctx.respond(embed=utls.warning_embed(err_msg))
                return

            # generate a unique code
            code = await utls.gen_unique_code(12)

            # generate an expiry date
            expiry_date = (datetime.now() + timedelta(days=7))
            
            # create a new unique code record
            unique_code = mdls.UniqueCode(code, expiry_date, duration, admin)

            # insert the new unique code record into the database
            await ops.add_unique_code(unique_code)

            embed = utls.success_embed(title=code, description='This code can be redeemed for a VIP subscription.')
            embed.add_field(name='Duration:', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
            embed.add_field(name='Expiry date:', value=utls.datetime_to_string(expiry_date), inline=False)
            await ctx.respond(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))


    @discord.slash_command(name='redeem', aliases=['claim'], description='Redeems a unique code for a VIP subscription.')
    async def redeem_code(self, ctx, code: str):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner (amins can not claim codes)
            if ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if user exists in the database and add them if not
            user, isNew = await utls.get_or_add_member(ctx.author)

            # check if the code exists in the database and whether it has been claimed or not
            unique_code, err_msg = await utls.validate_code(code)
            if err_msg:
                await ctx.respond(embed=utls.warning_embed(err_msg))
                return

            # get the duration of the code
            duration = await ops.get_sub_duration_by_code(unique_code)

            # mark the code as redeemed
            await ops.redeem_code(unique_code, user) # TODO: FIX THIS

            # check if the user already has a subscription and if so, if end_date is not expired yet and still active, then update the end_date, otherwise insert a new subscription
            subscription = await ops.get_active_subscription(user)
            extension = False
            if subscription and subscription.is_now_active():
                extension = True
                subscription, original_end_date = await ops.extend_subscription(subscription, duration)
            else:
                subscription = await ops.create_subscription(user, duration)
            
            # Change user role to VIP if not already
            if subscription.is_now_active():
                # Keep the member's VIP role from the free trila
                if ctx.author.id in self.perm_vips:
                    self.perm_vips[ctx.author.id] = True
                    
                await ctx.author.add_roles(discord.utils.get(ctx.guild.roles, name='🌟 VIP'))

            if extension:
                embed = utls.success_embed(title='Extension', description=f'Your subscription has been extended:')
                embed.add_field(name='By (duration):', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
                embed.add_field(name='From (old end-date):', value=utls.datetime_to_string(original_end_date), inline=False)
                embed.add_field(name='To (new end-date):', value=utls.datetime_to_string(subscription.end_date), inline=False)
            else:
                embed = utls.success_embed(title='Activation', description=f'Your subscription has been actiaved:')
                embed.add_field(name='For (duration):', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
                embed.add_field(name='Until (end-date):', value=utls.datetime_to_string(subscription.end_date), inline=False)

            await ctx.respond(embed=embed)
                
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))


    @discord.slash_command(name='grant', aliases=['setsub', 'extend', 'bless'], description='[admin only] Grants a VIP subscription to a user.')
    async def grant(self, ctx, member: discord.Member, start_date: str = datetime.today().strftime("%Y-%m-%d"), duration: str = '1m'):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return

            # check if the user has the administrator permission
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            # check if user exists in the database and add them if not
            user, isNew = await utls.get_or_add_member(member)
            
            # TODO 1: make granting and extending subscription work by date (e.g 1 month from start date 2023-05-10 => end date: 2023-06-10, regardless of month duration)

            # convert subscription start date to datetime
            start_date = start_date.split()[0].strip()
            start_date = datetime.strptime(start_date, "%Y-%m-%d") # e.g. start_date = 2023-05-10

            # check if the duration is valid
            duration, err_msg = await utls.validate_duration(duration)
            if err_msg:
                await ctx.respond(embed=utls.warning_embed(err_msg))
                return

            # check if the user already has a subscription and if so, if end_date is not expired yet and still active, then update the end_date, otherwise insert a new subscription
            original_end_date = None
            subscription = await ops.get_active_subscription(user)
            extension = False
            if subscription and subscription.is_now_active() and subscription.end_date >= start_date:
                extension = True
                subscription, original_end_date = await ops.extend_subscription(subscription, start_date, duration)
            else:
                subscription = await ops.set_create_subscription(user, start_date, duration)

            # Change user role to VIP if not already
            vipStatus = 0
            if subscription.is_now_active():
                # Keep the member's VIP role from the free trila
                if member.id in self.perm_vips:
                    self.perm_vips[member.id] = True

                if not discord.utils.get(member.roles, name='🌟 VIP'):
                    vipStatus = 1
                    await member.add_roles(discord.utils.get(ctx.guild.roles, name='🌟 VIP'))
                else:
                    vipStatus = 2
            else:
                if discord.utils.get(member.roles, name='🌟 VIP'):
                    vipStatus = -1
                    await member.remove_roles(discord.utils.get(ctx.guild.roles, name='🌟 VIP'))


            if original_end_date is None:
                original_end_date = subscription.end_date

            # add the grant to the database
            grant_date = datetime.now()
            action_type = 'extend' if extension else 'grant'
            grant = mdls.Grant(grant_date, original_end_date, subscription.end_date, duration, subscription, admin, user, action_type=action_type)
            await ops.add_grant(grant)

            unexpected_error = False

            # send success message to admin and user
            quiet_mode = 'Enabled, member will not be notified' if self.silent else 'Disabled, member will be notified'
            if extension:
                duration_str = f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}"
                if utls.datetime_to_string(original_end_date) == utls.datetime_to_string(subscription.end_date):
                    duration_str = "0 days"

                embed_admin = utls.success_embed(title='Extension', description=f'Member **{member.mention}**\'s subscription has been extended:')
                embed_admin.add_field(name='By (duration):', value=duration_str, inline=False)
                embed_admin.add_field(name='From (old end-date):', value=utls.datetime_to_string(original_end_date), inline=False)
                embed_admin.add_field(name='To (new end-date):', value=utls.datetime_to_string(subscription.end_date), inline=False)

                embed_user = utls.success_embed(title='Extension', description=f'Your subscription has been extended:')
                embed_user.add_field(name='By (duration):', value=duration_str, inline=False)
                embed_user.add_field(name='From (old end-date):', value=utls.datetime_to_string(original_end_date), inline=False)
                embed_user.add_field(name='To (new end-date):', value=utls.datetime_to_string(subscription.end_date), inline=False)
            elif subscription.is_now_active():
                embed_admin = utls.success_embed(title='Activation', description=f'Member **{member.mention}**\'s subscription has been actiaved:')
                embed_admin.add_field(name='For (duration):', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
                embed_admin.add_field(name='From (start-sate):', value=utls.datetime_to_string(start_date), inline=False)
                embed_admin.add_field(name='Until (end-date):', value=utls.datetime_to_string(subscription.end_date), inline=False)

                embed_user = utls.success_embed(title='Activation', description=f'Your subscription has been actiaved:')
                embed_user.add_field(name='For (duration):', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
                embed_user.add_field(name='From (start-sate):', value=utls.datetime_to_string(start_date), inline=False)
                embed_user.add_field(name='Until (end-date):', value=utls.datetime_to_string(subscription.end_date), inline=False)
            elif subscription.is_future(): # return datetime.now() <= self.start_date <= self.end_date
                embed_admin = utls.success_embed(title='Future Subscription', description=f'Member **{member.mention}**\'s future subscription has been set:')
                embed_admin.add_field(name='For (duration):', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
                embed_admin.add_field(name='From (start-sate):', value=utls.datetime_to_string(start_date), inline=False)
                embed_admin.add_field(name='Until (end-date):', value=utls.datetime_to_string(subscription.end_date), inline=False)

                embed_user = utls.success_embed(title='Future Subscription', description=f'Your future subscription has been set:')
                embed_user.add_field(name='For (duration):', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
                embed_user.add_field(name='From (start-sate):', value=utls.datetime_to_string(start_date), inline=False)
                embed_user.add_field(name='Until (end-date):', value=utls.datetime_to_string(subscription.end_date), inline=False)
            else: # something wrong happened
                embed_admin = utls.error_embed(title='Somthing wrong happened', description=f'Member **{member.mention}**\'s subscription could not be set properly')
                unexpected_error = True
                
            if not unexpected_error:
                embed_admin.add_field(name='Quiet mode:', value=quiet_mode, inline=False)
                embed_admin.add_field(name='Current Status:', value='Active' if subscription.is_now_active() else 'Inactive', inline=False)
                embed_admin.add_field(name='VIP Role:', value='Added!' if vipStatus == 1 else 'Removed!' if vipStatus == -1 else 'Not changed (Not-VIP)' if vipStatus == 0 else 'Not changed (Already VIP)', inline=False)

            await ctx.respond(embed=embed_admin)

            if not self.silent and not unexpected_error:
                try:
                    await member.send(embed=embed_user)
                except discord.Forbidden:
                    logging.error(f"Unable to send message to {member}")

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))


    # @discord.slash_command(name='grantAll', description='Grants a VIP subscription to all members.')
    # async def grantAll(self, ctx, duration: str = ''):
    #     try:
    #         # make sure the command is not private
    #         if ctx.guild is None:
    #             await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
    #             return

    #         # check if the user has the administrator permission
    #         if not ctx.author.guild_permissions.administrator:
    #             await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
    #             return
            
    #         # check if admin exists in the database and add them if not
    #         admin, isNew = await utls.get_or_add_member(ctx.author)

    #         # check if the duration is valid
    #         duration, err_msg = await utls.validate_duration(duration)
    #         if err_msg:
    #             await ctx.respond(embed=utls.warning_embed(err_msg))
    #             return

    #         # get all members
    #         members = ctx.guild.members

    #         # grant VIP subscription to all members
    #         for member in members:
    #             # check if the user already has a subscription and if so, if end_date is not expired yet and still active, then update the end_date, otherwise insert a new subscription
    #             original_end_date = None
    #             subscription = await ops.get_active_subscription(member)
    #             extension = False
    #             if subscription and subscription.is_now_active():
    #                 extension = True
    #                 subscription, original_end_date = await ops.extend_subscription(subscription, duration)
    #             else:
    #                 subscription = await ops.create_subscription(member, duration)

    #             # Change user role to VIP if not already
    #             if subscription.is_now_active():
    #                 # Keep the member's VIP role from the free trila
    #                 if member.id in self.perm_vips:
    #                     self.perm_vips[member.id] = True

    #                 await member.add_roles(discord.utils.get(ctx.guild.roles, name='🌟 VIP'))

    #             if original_end_date is None:
    #                 original_end_date = subscription.end_date

    #             # add the grant to the database
    #             grant_date = datetime.now()
    #             action_type = 'extend' if extension else 'grant'
    #             grant = mdls.Grant(grant_date, original_end_date, subscription.end_date, duration, subscription, admin, member, action_type=action_type)
    #             await ops.add_grant(grant)

    #     except Exception as e:
    #         logging.error(f"An error occurred: {str(e)}")
    #         await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
    #         await ctx.respond(embed=utls.error_embed(utls.get_error_message()))

    
    @discord.slash_command(name='revoke', aliases=['reduce', 'curse']) 
    async def revoke(self, ctx, member: discord.Member, duration: str = ''):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner (amins can not claim codes)
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            # check if user exists in the database and add them if not
            user, isNew = await utls.get_or_add_member(member)

            # check if the user already has a subscription
            subscription = await ops.get_active_subscription(user)

            if not subscription:
                await ctx.respond(embed=utls.warning_embed(f'Member **{member.name}** does not have an active subscription.'))
                return

            if duration:
                # check if the duration is valid
                duration, err_msg = await utls.validate_duration(duration)
                if err_msg:
                    await ctx.respond(embed=utls.warning_embed(err_msg))
                    return
                
                # reduce the user's active subscription by reducing the end_date by the duration
                subscription, original_end_date = await ops.reduce_subscription(subscription, duration)
            else:
                # remove the user's active subscription by updating the end_date to now
                subscription, original_end_date = await ops.revoke_subscription(subscription)
                duration = None
            

            # add the revoke to the database
            revoke_date = datetime.now()
            action_type = 'reduce' if duration else 'revoke'
            revoke = mdls.Revoke(revoke_date, original_end_date, subscription.end_date, subscription, admin, user, duration=duration, action_type=action_type)
            await ops.add_revoke(revoke)
                

            quiet_mode = 'Enabled, member will not be notified' if self.silent else 'Disabled, member will be notified'
            if duration and not subscription.is_expired():
                embed_admin = utls.success_embed(title='Duration Reduce', description=f'Member **{member.mention}**\'s subscription duration has been reduced:')
                embed_admin.add_field(name='By (duration):', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
                embed_admin.add_field(name='From (old end-date):', value=utls.datetime_to_string(original_end_date), inline=False)
                embed_admin.add_field(name='To (new end-date):', value=utls.datetime_to_string(subscription.end_date), inline=False)
                embed_admin.add_field(name='Quiet Mode:', value=quiet_mode, inline=False)

                embed_user = utls.warning_embed(title='Duration Reduce', description=f'Your subscription duration has been reduced:')
                embed_user.add_field(name='By (duration):', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
                embed_user.add_field(name='From (old end-date):', value=utls.datetime_to_string(original_end_date), inline=False)
                embed_user.add_field(name='To (new end-date):', value=utls.datetime_to_string(subscription.end_date), inline=False)
            else:
                await member.remove_roles(discord.utils.get(ctx.guild.roles, name='🌟 VIP'))
                embed_admin = utls.success_embed(title='Revoke', description=f'Member **{member.mention}**\'s subscription has been revoked.')
                embed_admin.add_field(name='Quiet Mode:', value=quiet_mode, inline=False)
                embed_user = utls.warning_embed(title='Revoke', description=f'Your subscription has been revoked.')
            

            await ctx.respond(embed=embed_admin)

            if not self.silent:
                try:
                    await member.send(embed=embed_user)
                except discord.Forbidden:
                    logging.error(f"Unable to send message to {member}")

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))


    @discord.slash_command(name='status', aliases=['check', '🌟 VIP'])
    async def status(self, ctx):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner (amins can not check status)
            if ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command as an admin.'))
                return
            
            # check if admin exists in the database and add them if not
            user, isNew = await utls.get_or_add_member(ctx.author)

            vip_role = discord.utils.get(ctx.guild.roles, name='🌟 VIP')

            # check if the user already has a subscription and if so, get the remaining days
            subscription = await ops.get_active_subscription(user)
            if subscription and not subscription.is_expired():
                # check if the user has the VIP role and if not, add it
                if not discord.utils.get(ctx.author.roles, name='🌟 VIP') and self.role_change_mode:
                    await ctx.author.add_roles(vip_role)
                remaining_days = (subscription.end_date - datetime.now()).days
                embed = utls.info_embed(title='Status', description=f'Your VIP subscription is active:')
                embed.add_field(name='Until (end-date):', value=utls.datetime_to_string(subscription.end_date), inline=False)
                embed.add_field(name='Remaining days:', value=remaining_days, inline=False)
            else:
                # check if the user has the VIP role and if so, remove it
                if discord.utils.get(ctx.author.roles, name='🌟 VIP') and self.role_change_mode:
                    await ctx.author.remove_roles(vip_role)
                embed = utls.info_embed(title='Status', description=f'You do not have an active VIP subscription.')

            await ctx.respond(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))

    
    @discord.slash_command(name='ustatus', description='[admin only] check the status of a user')
    async def ustatus(self, ctx, member: discord.Member):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the administrator permission
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command as an admin.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            user, isNew = await utls.get_or_add_member(member)

            vip_role = discord.utils.get(ctx.guild.roles, name='🌟 VIP')

            # check if the user already has a subscription and if so, get the remaining days
            subscription = await ops.get_active_subscription(user)
            if subscription and subscription.is_now_active():
                # check if the user has the VIP role and if not, add it
                if not discord.utils.get(member.roles, name='🌟 VIP') and self.role_change_mode:
                    await member.add_roles(vip_role)
                remaining_days = (subscription.end_date - datetime.now()).days
                embed = utls.info_embed(title='Status', description=f'{member.mention}\'s VIP subscription is active:')
                embed.add_field(name='Until (end-date):', value=utls.datetime_to_string(subscription.end_date), inline=False)
                embed.add_field(name='Remaining days:', value=remaining_days, inline=False)
            else:
                # check if the user has the VIP role and if so, remove it
                if discord.utils.get(member.roles, name='🌟 VIP') and self.role_change_mode:
                    await member.remove_roles(vip_role)
                embed = utls.info_embed(title='Status', description=f'{member.mention} does not have an active VIP subscription.')

            await ctx.respond(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))


    @discord.slash_command(name='code', aliases=['validity', 'val'], description='[all] check the validity of a code')
    async def code_status(self, ctx, code: str): # send code duration and status
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if admin exists in the database and add them if not
            user, isNew = await utls.get_or_add_member(ctx.author)

            # check if the code exists in the database and whether it has been claimed or not
            unique_code, err_msg = await utls.validate_code(code)
            if err_msg:
                await ctx.respond(embed=utls.warning_embed(title='Code Status', description=err_msg))
                return
            
            # get the duration of the code
            duration = await ops.get_sub_duration_by_code(unique_code)

            # send code status
            embed = utls.info_embed(title='Code Status', description=code)
            embed.add_field(name='Status:', value='Unclaimed', inline=False)
            embed.add_field(name='Duration:', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
            embed.add_field(name='Expiry date:', value=utls.datetime_to_string(unique_code.expiry_date), inline=False)

            await ctx.respond(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))

    @discord.slash_command(name="keep")
    async def keep(self, ctx, member: discord.Member):
        # Keep the member's VIP role
        self.perm_vips[member.id] = True

        # Inform the user that the member will keep the '🌟 VIP' role
        await ctx.respond(f"{member.mention} will keep the VIP role. **Use Grant or setsub commands if you didn't!**")

    @discord.slash_command(name="quiet", description="[admin only] enable quiet mode")
    async def quiet(self, ctx):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner (amins can not claim codes)
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            self.silent = True
            
            description = f'Quiet mode has been enabled by {ctx.author.mention}. Granting, Extending, Revoking, and Reducing VIP roles will not send warning messages to the user.'
            embed = utls.success_embed(title='Quiet mode', description=description)

            await ctx.respond(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))


    @discord.slash_command(name="unquiet", description="[admin only] disable quiet mode")
    async def unquiet(self, ctx):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner (amins can not claim codes)
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            self.silent = False

            description = f'Quiet mode has been disabled by {ctx.author.mention}. Granting, Extending, Revoking, and Reducing VIP roles will not send warning messages to the user.'
            embed = utls.success_embed(title='Quiet mode', description=description)

            await ctx.respond(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))

    @discord.slash_command(name="autocheck", description="[admin only] toggle automatic subscription check task")
    async def toggle_sub_check_task(self, ctx):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner (amins can not claim codes)
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            self.sub_check_mode = not self.sub_check_mode
            
            description = f'Automatic Subscription check task has been {"enabled" if self.sub_check_mode else "disabled"} by {ctx.author.mention}. The task will run every 3 hours.'
            embed = utls.success_embed(title='Automatic Subscription Checking', description=description)

            await ctx.respond(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))

    @discord.slash_command(name="rolechange", description="[admin only] toggle automatic role change mode")
    async def toggle_role_change_mode(self, ctx):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner (amins can not claim codes)
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            self.role_change_mode = not self.role_change_mode
            
            description = f'Automatic Role change has been {"enabled" if self.role_change_mode else "disabled"} by {ctx.author.mention}.'
            embed = utls.success_embed(title='Automatic role changing', description=description)

            await ctx.respond(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))


    @discord.slash_command(name="info", description="[admin only] get info about the bot")
    async def info(self, ctx):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner (amins can not claim codes)
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)
            
            # get the bot info (attributes) and display their status (on or off)

            embed = utls.info_embed(title='Bot Info', description='Bot attributes and their status:')
            embed.add_field(name='Automatic Subscription Checking:', value='Enabled' if self.sub_check_mode else 'Disabled', inline=False)
            embed.add_field(name='Automatic Role Changing:', value='Enabled' if self.role_change_mode else 'Disabled', inline=False)
            embed.add_field(name='Quiet Mode:', value='Enabled' if self.silent else 'Disabled', inline=False)

            await ctx.respond(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))


    @discord.slash_command(name="listu", aliases=['uinfo'], description="[admin only] list all users")
    async def list_users(self, ctx):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the administrator permission
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            users = await ops.get_users()
            
            csv_data = []
            for user in users:
                subscription = await ops.get_active_subscription(user)
                status = '🌟 VIP' if subscription and subscription.is_now_active() else 'Free'
                row = [user.id, user.username, status, user.discord_uid]
                csv_data.append(row)

            if len(csv_data) == 0:
                await ctx.respond(embed=utls.info_embed(title='Users', description='No users found.'))
                return

            headers = ["ID", "Username", "Status", "Discord ID"]
            csv_data.insert(0, headers)

            # Write the data to a StringIO buffer
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerows(csv_data)
            buffer.seek(0)

            # Create a discord.File object to send
            file = discord.File(fp=buffer, filename="users.csv")

            embed = utls.info_embed(title='All Users info are in the file')

            message = await ctx.respond(embed=embed, file=file)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))


    @discord.slash_command(name="listas", aliases=['asinfo'], description="[admin only] list all active subscriptions")
    async def active_subs_info(self, ctx):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the administrator permission
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            # get all the members in the database
            subscriptions = await ops.get_active_subscriptions()

            csv_data = []
            for subscription in subscriptions:
                status = 'Active' if subscription.is_now_active() else 'pending' if subscription.is_future() else 'Expired' if subscription.is_expired() else 'Unknown'
                user = await ops.get_user_by_subscription(subscription)
                # days only
                start_date = subscription.start_date.strftime("%Y-%m-%d")
                end_date = subscription.end_date.strftime("%Y-%m-%d")
                row = [user.discord_uid, start_date, end_date, status]
                csv_data.append(row)

            if len(csv_data) == 0:
                await ctx.respond(embed=utls.warning_embed('There are no active subscriptions.'))
                return

            headers = ["User's discord ID", "Start Date", "End Date", "Status"]
            csv_data.insert(0, headers)

            # Write the data to a StringIO buffer
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerows(csv_data)
            buffer.seek(0)

            # Create a discord.File object to send
            file = discord.File(fp=buffer, filename="active_subscriptions.csv")

            embed = utls.info_embed(title='All Active Subscriptions info are in the file')

            message = await ctx.respond(embed=embed, file=file)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))


    @discord.slash_command(name="listfu", description="[admin only] list free users")
    async def free_users_info(self, ctx, isvip: bool = False, hassubs: bool = False):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can only be used in private messages.'))
                return
            
            # check if the user has the administrator permission
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            guild = self.bot.guilds[0]

            csv_data = []
            for member in guild.members:
                if member.bot:
                    continue

                user, isNew = await utls.get_or_add_member(member)
            
                active_subscription = await ops.get_active_subscription(user)

                subscriptions = await ops.get_subscriptions(user)

                if active_subscription:
                    continue
                if isvip and not discord.utils.get(member.roles, name='🌟 VIP'):
                    continue
                if not isvip and discord.utils.get(member.roles, name='🌟 VIP'):
                    continue
                if hassubs and not subscriptions:
                    continue
                if not hassubs and subscriptions:
                    continue

                row = [member.id, member.name, member.discriminator]
                csv_data.append(row)

            if len(csv_data) == 0:
                await ctx.respond(embed=utls.warning_embed('No Free users found with the specified criteria.'))
                return
            
            headers = ["ID", "Username", "Discriminator"]
            csv_data.insert(0, headers)

            # Write the data to a StringIO buffer
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerows(csv_data)
            buffer.seek(0)

            # Create a discord.File object to send
            file = discord.File(fp=buffer, filename="free_users.csv")

            embed = utls.info_embed(title='All Free Users info are in the file')
            embed.add_field(name='Is VIP:', value=isvip, inline=False)
            embed.add_field(name='Has Subscriptions:', value=hassubs, inline=False)

            message = await ctx.respond(embed=embed, file=file)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))


    @discord.slash_command(name="listus", aliases=['usinfo'], description="[admin only] Lists all VIP subscriptions of a user")
    async def user_sub_info(self, ctx, member: discord.Member):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the administrator permission
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            # check if admin exists in the database and add them if not
            user, isNew = await utls.get_or_add_member(member)

            subscriptions = await ops.get_subscriptions(user)
            
            csv_data = []
            for subscription in subscriptions:
                status = 'Active' if subscription.is_now_active() else 'pending' if subscription.is_future() else 'Expired' if subscription.is_expired() else 'Unknown'
                start_date = subscription.start_date.strftime("%Y-%m-%d")
                end_date = subscription.end_date.strftime("%Y-%m-%d")
                row = [subscription.id, start_date, end_date, status]
                csv_data.append(row)

            if len(csv_data) == 0:
                await ctx.respond(embed=utls.warning_embed('This user has no subscriptions.'))
                return
            
            headers = ["ID", "Start Date", "End Date", "Status"]
            csv_data.insert(0, headers)

            # Write the data to a StringIO buffer
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerows(csv_data)
            buffer.seek(0)

            # Create a discord.File object to send
            file = discord.File(fp=buffer, filename=f"{member.name}_subscriptions.csv")

            embed = utls.info_embed(title=f"All {user.username} Subscriptions are in the file")

            await ctx.respond(embed=embed, file=file)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))


    @discord.slash_command(name="rega", aliases=['ra'], description="[admin only] register all users")
    async def register_all(self, ctx): # Add all members of the server to the database for the specified duration
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the administrator permission
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            # get all the members of the server
            members = ctx.guild.members

            # add all the members to the database
            for member in members:
                user, isNew = await utls.get_or_add_member(member)

            embed = utls.success_embed(title='All members have been added to the database successfully.')

            await ctx.respond(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))


    @discord.slash_command(name="regav", aliases=['rav'], description="[admin only] register all users with a vip role")
    async def register_all_vips(self, ctx, duration: str): # Add and subscribe all members of the server with a vip role to the database for the specified duration
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the administrator permission
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            # check if the duration is valid
            duration, err_msg = await utls.validate_duration(duration)
            if err_msg:
                await ctx.respond(embed=utls.error_embed(err_msg))
                return

            # get the vip role
            vip_role = discord.utils.get(ctx.guild.roles, name='🌟 VIP')

            # get all the members with the vip role
            members = vip_role.members

            # add all the members to the database
            end_date = None
            for member in members:
                user, isNew = await utls.get_or_add_member(member)
                subscription = await ops.get_active_subscription(user)
                if subscription is None:
                    subscription = await ops.create_subscription(user, duration)
                    if end_date is None:
                        end_date = subscription.end_date

            if end_date:
                embed = utls.success_embed('All members with the VIP role and without a subscription have been added to the database and subscribed to the VIP role.')
                embed.add_field(name='For (duration):', value=f"{duration.duration} {duration.unit}{'s' if duration.duration > 1 else ''}", inline=False)
                embed.add_field(name='Until (end-date):', value=utls.datetime_to_string(end_date), inline=False)
            else:
                embed = utls.success_embed('All members with the VIP role already have a subscription.')

            await ctx.respond(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))


    @discord.slash_command(name="massrv", aliases=['msrv'], description="[admin only] mass remove all vip roles")
    async def mass_remove_vip_roles(self, ctx): # Remove the vip role from all members of the server
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the administrator permission
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            # get the vip role
            vip_role = discord.utils.get(ctx.guild.roles, name='🌟 VIP')

            # get all the members with the vip role
            members = vip_role.members

            # remove the vip role from all the members
            for member in members:
                if self.role_change_mode:
                    await member.remove_roles(vip_role)

            embed = utls.success_embed('All members with the VIP role have been removed from the role.')

            await ctx.respond(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))


    @discord.slash_command(name="massrs", aliases=['msrv'], description="[admin only] mass remove all vip subscriptions")
    async def mass_remove_vip_subscriptions(self, ctx): # Remove the vip role from all members of the server
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the administrator permission
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            # get the vip role
            vip_role = discord.utils.get(ctx.guild.roles, name='🌟 VIP')

            # get all the members with the vip role
            members = vip_role.members

            # remove the vip role from all the members and their active subscriptions
            for member in members:
                if self.role_change_mode:
                    await member.remove_roles(vip_role)
                user, isNew = await utls.get_or_add_member(member)
                subscription = await ops.get_active_subscription(user)
                if subscription is not None:
                    await ops.revoke_subscription(subscription)

            embed = utls.success_embed('All members with the VIP role have been removed from the role and their active subscriptions have been ended.')

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))

    
    @discord.slash_command(name='reset-free-trial') 
    async def reset_free_trial(self, ctx, member: discord.Member, toggle: bool = False):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner (amins can not claim codes)
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            # check if user exists in the database and add them if not
            user, isNew = await utls.get_or_add_member(member)

            member_name = member.name + "#" + member.discriminator

            old_free_trial_used = user.free_trial_used

            if toggle:
                await ops.toggle_free_trial_user(user)
                embed = utls.success_embed(title=f'Free trial for {member_name} has been toggled to {"used" if user.free_trial_used else "not used"} by {ctx.author.mention}.')
            elif user.free_trial_used:
                await ops.reset_free_trial_user(user)
                embed = utls.success_embed(title=f'Free trial for {member_name} has been reset by {ctx.author.mention}.')
            else:
                embed = utls.warning_embed(title=f'Free trial for {member_name} has not been used yet.')
            
            await ctx.respond(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))


    @discord.slash_command(name='reset-free-trial-all') 
    async def reset_free_trial_all(self, ctx):
        try:
            # make sure the command is not private
            if ctx.guild is None:
                await ctx.respond(embed=utls.warning_embed('This command can not be used in private messages.'))
                return
            
            # check if the user has the role of admin or owner (amins can not claim codes)
            if not ctx.author.guild_permissions.administrator:
                await ctx.respond(embed=utls.warning_embed('You are not allowed to use this command.'))
                return
            
            # check if admin exists in the database and add them if not
            admin, isNew = await utls.get_or_add_member(ctx.author)

            await ctx.defer()
            embed = utls.info_embed(title='Resetting free trials for all server members...')
            await ctx.send(embed=embed)

            records_updated = 0
            for member in ctx.guild.members:
                # check if user exists in the database and add them if not
                user, isNew = await utls.get_or_add_member(member)
                if user.free_trial_used:
                    await ops.reset_free_trial_user(user)
                    records_updated += 1
            
            embed = utls.success_embed(title=f'Free trial for {records_updated} users has been reset by {ctx.author.mention}.')
            await ctx.respond(embed=embed)

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            await self.send_private_error_notification(ctx.author.name, ctx.command.name, str(e))
            await ctx.respond(embed=utls.error_embed(utls.get_error_message()))


    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # get the vip role
        vip_role = discord.utils.get(member.guild.roles, name='🌟 VIP')

        logging.info(f"{member} joined the server!")

        # check if admin exists in the database and add them if not
        user, isNew = await utls.get_or_add_member(member)

        # check if member is in the database, if he is don't give hime vip role
        if not isNew and user.free_trial_used:
            return
        
        if not user.free_trial_used:
            await ops.toggle_free_trial_user(user)
        
        await member.add_roles(vip_role)
        # send him a private message informing him that he has been given the vip role temporarily as a free-trial, and if he paid he will get reinstaited (in an embed)
        owner_role = discord.utils.get(member.guild.roles, name='👑 Owner')
        owner_members = owner_role.members
        admin_role = discord.utils.get(member.guild.roles, name='🛡️ Admin')
        admin_members = admin_role.members

        guild_name = member.guild.name
        # embed = utls.info_embed(title=f'{guild_name} VIP role free trial', description=f'You have been given the VIP role temporarily. You will keep it for 20 minutes, after which it will be removed. However, if you already paid for the VIP role, you will get reinstated automatically.')
        member_embed = utls.info_embed(title=f'تجربة مجانية لدور  MKL-Signals - VIP', description=f'لقد تم منحك دور **VIP** مؤقتًا. ستحتفظ بها لمدة 20 دقائق ، وبعد ذلك ستتم إزالتها. ومع ذلك ، إذا كنت قد دفعت بالفعل مقابل دور **VIP** ، فستتم إعادتك تلقائيًا.')
        try:
            await member.send(embed=member_embed)
        except discord.Forbidden:
            logging.error(f"Unable to send message to {member}")

        # loop through owners and admins and inform them
        member_name = member.name + "#" + member.discriminator
        admin_embed = utls.info_embed(title=f'{guild_name} VIP role free trial for {member_name}', description=f'{member.mention} has joined the server and has been given the VIP role temporarily. He will keep it for 20 minutes, after which it will be removed.')
        admin_embed.add_field(name='Note', value='Buttons are just for testing, they do nothing now', inline=False)
        for owner in owner_members:
            await owner.send(embed=admin_embed, view=NewMemberButtonsView())
        for admin in admin_members:
            await admin.send(embed=admin_embed, view=NewMemberButtonsView())
        
        # Add the member's user ID to the perm_vips dictionary
        self.perm_vips[member.id] = False

        await asyncio.sleep(1200)
        # check if user is still in the server and if he is, remove the vip role
        if self.perm_vips[member.id] == False:
            await member.remove_roles(vip_role)

            # embed = utls.info_embed(title=f'{guild_name} VIP role free trial expired', description=f'Your VIP role free trial has expired. If you want to keep the VIP role, please contact one of the owners of the server.')
            member_embed = utls.info_embed(title=f'انتهت الفترة التجريبية المجانية لدور  MKL-Signals - VIP ', description=f'انتهت صلاحية الإصدار التجريبي المجاني لدور VIP الخاص بك. إذا كنت ترغب في الاحتفاظ بدور **VIP**، يرجى الاتصال بأحد مالكي خادم **MKL-Signals**.')
            for owner in owner_members:
                owner_name = owner.name + "#" + owner.discriminator
                member_embed.add_field(name=f'{owner_name}', value=f'{owner.mention}', inline=False)
            
            try:
                await member.send(embed=member_embed)
            except discord.Forbidden:
                logging.error(f"Unable to send message to {member}")

            admin_embed = utls.info_embed(title=f'{guild_name} VIP role free trial expired for {member_name}', description=f'{member.mention} has had his VIP role removed after the free trial expired. If he wants to keep the VIP role, he will have to contact one of the owners of the server.')
            for owner in owner_members:
                owner_name = owner.name + "#" + owner.discriminator
                admin_embed.add_field(name=f'{owner_name}', value=f'{owner.mention}', inline=False)
            
            for owner in owner_members:
                await owner.send(embed=admin_embed)
            for admin in admin_members:
                await admin.send(embed=admin_embed)
        else:
            # embed = utls.info_embed(title=f'{guild_name} VIP role free trial expired', description=f'Your VIP role free trial has expired, but you have paid for the VIP role, so you will keep it.')
            member_embed = utls.info_embed(title=f'انتهت الفترة التجريبية المجانية لدور  MKL-Signals - VIP ', description=f'انتهت صلاحية الإصدار التجريبي المجاني لدور **VIP** الخاص بك ، لكنك دفعت مقابل دور **VIP** ، لذلك ستحتفظ به.')
            try:
                await member.send(embed=member_embed)
            except discord.Forbidden:
                logging.error(f"Unable to send message to {member}")

            admin_embed = utls.info_embed(title=f'{guild_name} VIP role free trial expired for {member_name}', description=f'{member.mention} VIP role free trial expired, but he was given a new active subscription or `keep` was used on him, so he will keep the VIP role.')
            for owner in owner_members:
                await owner.send(embed=admin_embed)
            for admin in admin_members:
                await admin.send(embed=admin_embed)

        # Remove the member from the dictionary if they are in it
        del self.perm_vips[member.id]


    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, discord.slash_commandNotFound):
            await ctx.respond(embed=utls.error_embed("Command not found. Please use `!help` to see a list of available commands."))
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.respond(embed=utls.error_embed("Missing a required argument. Please try again."))
        elif isinstance(error, commands.MissingPermissions):
            await ctx.respond(embed=utls.error_embed("You do not have permission to perform this action."))
        elif isinstance(error, commands.BadArgument):
            await ctx.respond(embed=utls.error_embed("Bad argument. Please try again."))
        elif isinstance(error, discord.slash_commandOnCooldown):
            await ctx.respond(embed=utls.error_embed(f"This command is on cooldown. Please try again in {error.retry_after:.2f} seconds."))
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.respond(embed=utls.error_embed("This command cannot be used in private messages."))
        elif isinstance(error, discord.slash_commandInvokeError):
            await ctx.respond(embed=utls.error_embed("An error occurred. Please try again."))
            original = error.original
            if isinstance(original, discord.Forbidden):
                await ctx.respond(embed=utls.error_embed("I do not have permission to perform this action."))
            else:
                raise error
        else:
            raise error
        
        await self.send_private_error_notification(ctx.author.name, 'on_command_error', traceback.format_exc())

    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        await self.send_private_error_notification("on_error", event, traceback.format_exc())
        
    async def send_private_error_notification(self, username: str = '', command: str = '', error_message: str = ''):
        owner_id = ADMIN_USER_ID
        owner = await self.bot.fetch_user(owner_id)
        await owner.send(embed=utls.error_embed(f"An error occurred (u: {username}, c: {command}): {error_message}"))


    async def check_subscriptions(self) -> tuple[int, int]:
        self.sub_check_in_progress = True
        logging.info('Checking subscriptions...')
        guild = self.bot.guilds[0]
        vip_role = discord.utils.get(guild.roles, name='🌟 VIP')
        admin_members = utls.get_admins_and_owners(guild)
        records_updated = 0
        for member in guild.members:
            user, isNew = await utls.get_or_add_member(member)
            subscription = await ops.get_active_subscription(user)
            member_name = member.name + "#" + member.discriminator
            if vip_role in member.roles: 
                if subscription: 
                    if subscription.is_expiring_soon(days=1):
                        embed_admin = utls.warning_embed(f'{member.mention}\'s ({member_name}) VIP subscription is about to end in less than 1 day.')
                        embed_user = utls.warning_embed(f'Your VIP subscription is about to end in less than 1 day.')
                    else:
                        continue
                else:
                    embed_admin = utls.warning_embed(f'{member.mention}\'s ({member_name}) VIP subscription has ended.')
                    embed_user = utls.warning_embed(f'Your VIP subscription has ended.')
                    await member.remove_roles(vip_role)
                    records_updated += 1
            elif subscription and subscription.is_now_active():
                embed_admin = utls.success_embed(f'{member.mention}\'s ({member_name}) VIP role has been reinstated as his subscription is still active.')
                embed_user = utls.success_embed(f'Your VIP role has been reinstated as your subscription is still active.')
                await member.add_roles(vip_role)
                records_updated += 1
            else:
                continue

            await self.send_embed_messages(embed_admin, embed_user, member, admin_members)
                
        logging.info('Finished checking subscriptions.')
        self.sub_check_in_progress = False
        return len(guild.members), records_updated
    

    async def send_embed_messages(self, embed_admin, embed_user, member, admin_members):
        if not self.silent:
            try:
                await member.send(embed=embed_user)
            except discord.Forbidden:
                print(f"Was not able to send message to {member.name}")

        for admin in admin_members:
            try:
                await admin.send(embed=embed_admin)
            except discord.Forbidden:
                print(f"Was not able to send message to {admin.name}")


def setup(bot): # this is called by Pycord to setup the cog
    bot.add_cog(VIPCommand(bot)) # add the cog to the bot