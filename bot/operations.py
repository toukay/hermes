from datetime import datetime, timedelta
from sqlalchemy import select, and_, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from contextlib import asynccontextmanager
import sqlite3
import shutil
import os
import gzip

from models import User, SubDuration, Subscription, UniqueCode, RedeemedCode, Grant, Revoke

async_engine = create_async_engine('sqlite+aiosqlite:///database.db')
async_session = sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)

@asynccontextmanager
async def get_session():
    session = async_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
        

# helper functions (synchronous, with local, "throw away" sessions)

# user helpers
async def get_users() -> list[User]:
    async with get_session() as session:
        result = await session.execute(select(User))
    return result.scalars().all()

async def get_user_by_discord_uid(discord_uid: int) -> User:
    async with get_session() as session:
        result = await session.execute(select(User).filter(User.discord_uid == discord_uid))
    return result.scalar_one_or_none()
    
async def get_user_by_subscription(subscription: Subscription) -> User:
    async with get_session() as session:
        result = await session.execute(select(User).filter(User.id == subscription.user_id))
    return result.scalar_one_or_none()

async def add_user(user: User) -> None:
    async with get_session() as session:
        session.add(user)
        await session.commit()


# sub duration helpers
async def get_sub_durations() -> list[SubDuration]:
    async with get_session() as session:
        result = await session.execute(select(SubDuration))
    return result.scalars().all()
    
async def get_sub_duration(duration: int, unit: str) -> SubDuration:
    async with get_session() as session:
        result = await session.execute(select(SubDuration).filter(SubDuration.duration == duration, SubDuration.unit == unit))
    return result.scalar_one_or_none()

async def get_sub_duration_by_code(code: UniqueCode) -> SubDuration:
    async with get_session() as session:
        result = await session.execute(select(SubDuration).filter(SubDuration.id == code.duration_id))
    return result.scalar_one_or_none()


# subscription helpers
async def get_active_subscriptions() -> list[Subscription]:
    async with get_session() as session:
        now = func.now()
        result = await session.execute(select(Subscription).filter(and_(Subscription.start_date <= now, Subscription.end_date >= now)))
    return result.scalars().all()

async def get_active_subscription(user: User) -> Subscription:
    async with get_session() as session:
        now = func.now()
        result = await session.execute(
            select(Subscription)
            .filter(and_(Subscription.user_id == user.id, Subscription.start_date <= now, Subscription.end_date >= now))
            .order_by(Subscription.start_date.desc())
        )
        subscription = result.scalars().first()
        
        if subscription:
            if subscription.is_expired():
                subscription.active = False
                session.add(subscription)
                await session.commit()
                return None
        return subscription

async def get_subscriptions(user: User) -> list[Subscription]:
    async with get_session() as session:
        result = await session.execute(select(Subscription).filter(Subscription.user_id == user.id))
    return result.scalars().all()

async def extend_subscription(subscription: Subscription, duration: SubDuration) -> tuple[Subscription, datetime]:
    async with get_session() as session:
        original_end_date = subscription.end_date
        unit = 1 if duration.unit == 'day' else 30 if duration.unit == 'month' else 0
        subscription.end_date += timedelta(days=duration.duration * unit)
        session.add(subscription)
        await session.commit()
    return subscription, original_end_date

async def add_subscription(subscription: Subscription) -> None:
    async with get_session() as session:
        session.add(subscription)
        await session.commit()

async def create_subscription(user: User, duration: SubDuration) -> Subscription:
    async with get_session() as session:
        unit = 1 if duration.unit == 'day' else 30 if duration.unit == 'month' else 0
        subscription = Subscription(datetime.now(), datetime.now() + timedelta(days=duration.duration * unit), user)
        session.add(subscription)
        await session.commit()
    return subscription

async def set_create_subscription(user: User, start_date: datetime, duration_days: int) -> Subscription:
    async with get_session() as session:
        subscription = Subscription(start_date, start_date + timedelta(days=duration_days), user)
        # check the start date is not in the past or in the future and change subscription.active accordingly
        if subscription.start_date < datetime.now() or subscription.start_date > datetime.now():
            subscription.active = False
        session.add(subscription)
        await session.commit()
    return subscription

async def reduce_subscription(subscription: Subscription, duration: SubDuration) -> tuple[Subscription, datetime]:
    async with get_session() as session:
        original_end_date = subscription.end_date
        unit = 1 if duration.unit == 'day' else 30 if duration.unit == 'month' else 0
        subscription.end_date = max(subscription.end_date - timedelta(days=duration.duration * unit), datetime.now())
        subscription.active = subscription.end_date > datetime.now()
        session.add(subscription)
        await session.commit()
    return subscription, original_end_date

async def revoke_subscription(subscription: Subscription) -> tuple[Subscription, datetime]:
    async with get_session() as session:
        original_end_date = subscription.end_date
        if subscription.end_date > datetime.now():
            subscription.end_date = datetime.now()
        if subscription.start_date > datetime.now():
            subscription.start_date = datetime.now()
        subscription.active = False
        session.add(subscription)
        await session.commit()
    return subscription, original_end_date

async def end_subscription(subscription: Subscription) -> None:
    async with get_session() as session:
        subscription.active = False
        session.add(subscription)
        await session.commit()


# unique code helpers
async def get_unique_code_by_code(code: str) -> UniqueCode:
    async with get_session() as session:
        result = await session.execute(select(UniqueCode).filter(UniqueCode.code == code))
    return result.scalar_one_or_none()
    
async def update_unique_code(unique_code: UniqueCode) -> None:
    async with get_session() as session:
        session.add(unique_code)
        await session.commit()

async def add_unique_code(unique_code: UniqueCode) -> None:
    async with get_session() as session:
        session.add(unique_code)
        await session.commit()

async def delete_expired_unique_codes() -> None:
    async with get_session() as session:
        expired_codes = await session.execute(
            select(UniqueCode).filter(UniqueCode.redeemed == False, UniqueCode.expiry_date < datetime.now())
        )
        for code in expired_codes.scalars():
            await session.delete(code)
        await session.commit()


# redeemed code helpers
async def add_redeemed_code(redeemed_code: RedeemedCode) -> None:
    async with get_session() as session:
        session.add(redeemed_code)
        await session.commit()


async def redeem_code(user: User, code: UniqueCode) -> None:
    async with get_session() as session:
        code.redeemed = True
        session.add(code)
        await session.commit()
        session.add(RedeemedCode(unique_code=code, )) # TODO: finish this
        await session.commit()


# grant helpers
async def add_grant(grant: Grant) -> None:
    async with get_session() as session:
        session.add(grant)
        await session.commit()


# revoke helpers
async def add_revoke(revoke: Revoke) -> None:
    async with get_session() as session:
        session.add(revoke)
        await session.commit()


# misc helpers
async def backup_database() -> tuple[str, str]:
    # Get the current date
    current_date = datetime.now().strftime("%Y%m%d")

    # Create the backup folder if it does not exist
    backup_folder = "./backup"
    os.makedirs(backup_folder, exist_ok=True)

    # Specify the source database and backup database file names
    source_database = "database.db"
    backup_database = f"{backup_folder}/backup_database_{current_date}.db"

    try:
        # Copy the source database file to the backup database file
        shutil.copyfile(source_database, backup_database)

        # Compress the backup database file
        with open(backup_database, 'rb') as f_in:
            with gzip.open(f"{backup_database}.gz", 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Remove the uncompressed backup file
        os.remove(backup_database)
    except Exception as e:
        return None, f"Error backing up database: {e}"

    return f"{backup_database}.gz", None