from datetime import datetime, timedelta
from sqlalchemy import Table, Column, ForeignKey, CheckConstraint, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import event

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    discord_uid = Column(Integer, unique=True, nullable=False)
    username = Column(String, nullable=False)

    subscriptions = relationship('Subscription',  foreign_keys='Subscription.user_id', back_populates='user')
    unique_codes = relationship('UniqueCode',  foreign_keys='UniqueCode.admin_id', back_populates='admin')
    admin_grants = relationship('Grant',  foreign_keys='Grant.admin_id', back_populates='admin')
    user_grants = relationship('Grant',  foreign_keys='Grant.user_id', back_populates='user')
    admin_revokes = relationship('Revoke',  foreign_keys='Revoke.admin_id', back_populates='admin')
    user_revokes = relationship('Revoke', foreign_keys='Revoke.user_id', back_populates='user')

    def __init__(self, discord_uid, username):
        self.discord_uid = discord_uid
        self.username = username

    def __repr__(self):
        return f'<User(id={self.id}, discord_uid={self.discord_uid}, username={self.username})>'
    
    def __str__(self):
        return self.username
    
    def __eq__(self, other):
        return self.id == other.id
    

class SubDuration(Base):
    __tablename__ = 'sub_durations'

    id = Column(Integer, primary_key=True)
    duration = Column(Integer, CheckConstraint('duration > 0'), nullable=False)
    unit = Column(String, CheckConstraint("unit IN ('day', 'month')"), nullable=False)

    unique_codes = relationship('UniqueCode',  foreign_keys='UniqueCode.duration_id', back_populates='duration')
    grants = relationship('Grant',  foreign_keys='Grant.duration_id', back_populates='duration')
    revokes = relationship('Revoke',  foreign_keys='Revoke.duration_id', back_populates='duration')

    def __init__(self, duration, unit):
        self.duration = duration
        self.unit = unit

    def __repr__(self):
        return f'<SubDuration(id={self.id}, duration={self.duration}, unit={self.unit})>'
    
    def __str__(self):
        return f'SubDuration(id={self.id}, duration={self.duration}, unit={self.unit})'
    
    def __eq__(self, other):
        return self.id == other.id
    

class Subscription(Base):
    __tablename__ = 'subscriptions'

    id = Column(Integer, primary_key=True)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    active = Column(Boolean, CheckConstraint("active IN (0, 1)"), nullable=False, default=True)

    user = relationship('User', foreign_keys=[user_id], back_populates='subscriptions')
    redeemed_codes = relationship('RedeemedCode', foreign_keys='RedeemedCode.subscription_id', back_populates='subscription')
    grants = relationship('Grant', foreign_keys='Grant.subscription_id', back_populates='subscription')
    revokes = relationship('Revoke', foreign_keys='Revoke.subscription_id', back_populates='subscription')

    def __init__(self, start_date, end_date, user):
        self.start_date = start_date
        self.end_date = end_date
        self.user = user

    def __repr__(self):
        return f'<Subscription(id={self.id}, start_date={self.start_date}, end_date={self.end_date}, user_id={self.user_id})>'
    
    def __str__(self):
        return f'Subscription(id={self.id}, start_date={self.start_date}, end_date={self.end_date}, user_id={self.user_id})'
    
    def __eq__(self, other):
        return self.id == other.id
    
    def is_expired(self):
        return self.end_date < datetime.now()
    
    def is_expiring_soon(self, days=1):
        return self.end_date < datetime.now() + timedelta(days=days)
    

class UniqueCode(Base):
    __tablename__ = 'unique_codes'

    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)
    redeemed = Column(Boolean, CheckConstraint("redeemed IN (0, 1)"),nullable=False, default=False)
    expiry_date = Column(DateTime, nullable=False)
    duration_id = Column(Integer, ForeignKey('sub_durations.id'), nullable=False)
    admin_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    duration = relationship('SubDuration', foreign_keys=[duration_id], back_populates='unique_codes')
    admin = relationship('User', foreign_keys=[admin_id], back_populates='unique_codes')
    redeemed_code = relationship('RedeemedCode', foreign_keys='RedeemedCode.unique_code_id', back_populates='unique_code')

    def __init__(self, code, redeemed, expiry_date, duration, admin):
        self.code = code
        self.redeemed = redeemed
        self.expiry_date = expiry_date
        self.duration = duration
        self.admin = admin

    def __repr__(self):
        return f'<UniqueCode(id={self.id}, code={self.code}, redeemed={self.redeemed}, expiry_date={self.expiry_date}, duration_id={self.duration_id}, admin_id={self.admin_id})>'
    
    def __str__(self):
        return f'UniqueCode(id={self.id}, code={self.code}, redeemed={self.redeemed}, expiry_date={self.expiry_date}, duration_id={self.duration_id}, admin_id={self.admin_id})'
    
    def __eq__(self, other):
        return self.id == other.id
    
    def is_expired(self):
        return self.expiry_date < datetime.now()
    
    def is_redeemed(self):
        return self.redeemed and self.redeemed_code is not None
    

class RedeemedCode(Base):
    __tablename__ = 'redeemed_codes'

    id = Column(Integer, primary_key=True)
    redemption_date = Column(DateTime, nullable=False)
    unique_code_id = Column(Integer, ForeignKey('unique_codes.id'), unique=True, nullable=False)
    subscription_id = Column(Integer, ForeignKey('subscriptions.id'), nullable=False)

    unique_code = relationship('UniqueCode', foreign_keys=[unique_code_id], back_populates='redeemed_code')
    subscription = relationship('Subscription', foreign_keys=[subscription_id], back_populates='redeemed_codes')

    def __init__(self, redemption_date, unique_code, subscription):
        self.redemption_date = redemption_date
        self.unique_code = unique_code
        self.subscription = subscription

    def __repr__(self):
        return f'<RedeemedCode(id={self.id}, redemption_date={self.redemption_date}, unique_code_id={self.unique_code_id}, subscription_id={self.subscription_id})>'
    
    def __str__(self):
        return f'RedeemedCode(id={self.id}, redemption_date={self.redemption_date}, unique_code_id={self.unique_code_id}, subscription_id={self.subscription_id})'
    
    def __eq__(self, other):
        return self.id == other.id
    

class Grant(Base):
    __tablename__ = 'grants'

    id = Column(Integer, primary_key=True)
    grant_date = Column(DateTime, nullable=False)
    action_type = Column(String, CheckConstraint("action_type IN ('grant', 'extend')"), nullable=False)
    original_end_date = Column(DateTime, nullable=False)
    new_end_date = Column(DateTime, nullable=False)
    duration_id = Column(Integer, ForeignKey('sub_durations.id'), nullable=False)
    subscription_id = Column(Integer, ForeignKey('subscriptions.id'), nullable=False)
    admin_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    duration = relationship('SubDuration', foreign_keys=[duration_id], back_populates='grants')
    subscription = relationship('Subscription', foreign_keys=[subscription_id], back_populates='grants')
    admin = relationship('User', foreign_keys=[admin_id], back_populates='admin_grants')
    user = relationship('User', foreign_keys=[user_id], back_populates='user_grants')

    def __init__(self, grant_date, action_type, original_end_date, new_end_date, duration, subscription, admin, user):
        self.grant_date = grant_date
        self.action_type = action_type
        self.original_end_date = original_end_date
        self.new_end_date = new_end_date
        self.duration = duration
        self.subscription = subscription
        self.admin = admin
        self.user = user

    def __repr__(self):
        return f'<Grant(id={self.id}, grant_date={self.grant_date}, action_type={self.action_type}, original_end_date={self.original_end_date}, new_end_date={self.new_end_date}, duration_id={self.duration_id}, subscription_id={self.subscription_id}, admin_id={self.admin_id}, user_id={self.user_id})>'
    
    def __str__(self):
        return f'Grant(id={self.id}, grant_date={self.grant_date}, action_type={self.action_type}, original_end_date={self.original_end_date}, new_end_date={self.new_end_date}, duration_id={self.duration_id}, subscription_id={self.subscription_id}, admin_id={self.admin_id}, user_id={self.user_id})'
    
    def __eq__(self, other):
        return self.id == other.id
    

class Revoke(Base):
    __tablename__ = 'revokes'

    id = Column(Integer, primary_key=True)
    revoke_date = Column(DateTime, nullable=False)
    action_type = Column(String, CheckConstraint("action_type IN ('revoke', 'reduce')"), nullable=False)
    original_end_date = Column(DateTime, nullable=False)
    new_end_date = Column(DateTime, nullable=False)
    duration_id = Column(Integer, ForeignKey('sub_durations.id'), nullable=False)
    subscription_id = Column(Integer, ForeignKey('subscriptions.id'), nullable=False)
    admin_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    duration = relationship('SubDuration', foreign_keys=[duration_id], back_populates='revokes')
    subscription = relationship('Subscription', foreign_keys=[subscription_id], back_populates='revokes')
    admin = relationship('User', foreign_keys=[admin_id], back_populates='admin_revokes')
    user = relationship('User', foreign_keys=[user_id], back_populates='user_revokes')

    def __init__(self, revoke_date, action_type, original_end_date, new_end_date, duration, subscription, admin, user):
        self.revoke_date = revoke_date
        self.action_type = action_type
        self.original_end_date = original_end_date
        self.new_end_date = new_end_date
        self.duration = duration
        self.subscription = subscription
        self.admin = admin
        self.user = user

    def __repr__(self):
        return f'<Revokes(id={self.id}, revoke_date={self.revoke_date}, action_type={self.action_type}, original_end_date={self.original_end_date}, new_end_date={self.new_end_date}, duration_id={self.duration_id}, subscription_id={self.subscription_id}, admin_id={self.admin_id}, user_id={self.user_id})>'
    
    def __str__(self):
        return f'Revokes(id={self.id}, revoke_date={self.revoke_date}, action_type={self.action_type}, original_end_date={self.original_end_date}, new_end_date={self.new_end_date}, duration_id={self.duration_id}, subscription_id={self.subscription_id}, admin_id={self.admin_id}, user_id={self.user_id})'
    
    def __eq__(self, other):
        return self.id == other.id
