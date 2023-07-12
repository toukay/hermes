from datetime import datetime
import string
import random
import discord
import logging

import operations as ops
import models as mdls


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'


# User helpers
async def get_or_add_member(member: discord.Member) -> tuple[mdls.User, bool]:
    discord_uid = member.id
    username = member.name + "#" + member.discriminator
    isNew = False
    user = await ops.get_user_by_discord_uid(discord_uid)
    if not user:
        isNew = True
        user = mdls.User(discord_uid, username)
        await ops.add_user(user)
    return user, isNew


# Sub duration helpers
def parse_duration(duration: str) -> tuple[int, str]:
    duration = duration.lower()
    if duration.endswith('s'):
        return int(duration[:-1]), 'second'
    elif duration.endswith('i'):
        return int(duration[:-1]), 'minute'
    elif duration.endswith('h'):
        return int(duration[:-1]), 'hour'
    elif duration.endswith('d'):
        return int(duration[:-1]), 'day'
    elif duration.endswith('m'):
        return int(duration[:-1]), 'month'
    elif duration.endswith('y'):
        return int(duration[:-1]), 'year'
    else:
        return None, None
    
async def validate_duration(duration: str) -> tuple[mdls.SubDuration, str]:
    duration_value, duration_unit = parse_duration(duration)
    if not duration_value or not duration_unit:
        return None, 'Invalid duration. Duration is not in the correct format.'
    sub_duration = await ops.get_sub_duration(duration_value, duration_unit)
    if not sub_duration:
        return None, 'Invalid duration. Duration is not part of the allowed durations.'
    return sub_duration, None

# Subscription helpers


# Unique code helpers
def gen_code(l: int) -> str:
    unique_digits = string.digits + string.ascii_uppercase
    random_code = ''.join(random.choice(unique_digits) for _ in range(l))
    return f'{random_code[:l//3]}-{random_code[l//3:2*l//3]}-{random_code[2*l//3:]}'

async def gen_unique_code(l: int) -> str:
    await ops.delete_expired_unique_codes()
    code = gen_code(l)
    while await ops.get_unique_code_by_code(code):
        code = gen_code(l)
    return code

async def validate_code(code: str) -> tuple[mdls.UniqueCode, str]:
    unique_code = await ops.get_unique_code_by_code(code)
    if not unique_code:
        return None, 'Invalid code. This code does not exist.'
    if unique_code.is_redeemed():
        return None, 'This code has been claimed.'
    if unique_code.is_expired():
        return None, 'This code has expired.'
    return unique_code, None

# Redeemed code helpers


# Grant helpers


# Revoke helpers


# Misc helpers
def get_error_message() -> str:
    hermes_error_messages = [
        "My apologies, mortal. It appears that even the swift Hermes can stumble. Let's attempt that command once more.",
        "By the wings of Hermes! An unexpected hindrance has occurred. Fear not, and try again after a short while.",
        "It appears Hermes is momentarily detained on Mount Olympus. Kindly retry your request later.",
    ]
    return random.choice(hermes_error_messages)


def error_embed(description: str) -> discord.Embed:
    embed = discord.Embed(title='Error', description=description, color=discord.Color.red())
    return embed

def success_embed(title: str, description: str = '') -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=discord.Color.green())
    return embed

def info_embed(title: str, description: str = '') -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=discord.Color.blue())
    return embed

def warning_embed(title: str, description: str = '') -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=discord.Color.orange())
    return embed

def special_embed(title: str, description: str = '') -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=discord.Color.gold())
    return embed

def advanced_embed(title: str, description: str = '') -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=discord.Color.purple())
    return embed

def owner_embed(title: str, description: str = '') -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=discord.Color.magenta())
    return embed


def datetime_to_string(dt: datetime) -> str:
    return dt.strftime(DATETIME_FORMAT)

def get_admins_and_owners(guild) -> list:
    owner_role = discord.utils.get(guild.roles, name="👑 Owner")
    admin_role = discord.utils.get(guild.roles, name="🛡️ Admin")
    return owner_role.members + admin_role.members