from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class APIKey(Base):
    __tablename__ = 'api_keys'
    
    id = Column(Integer, primary_key=True, index=True)
    key_id = Column(String(50), unique=True, index=True, default=lambda: str(uuid.uuid4())[:8])
    api_key = Column(String(100), unique=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)
    rate_limit = Column(Integer, default=1000)
    
    usage_logs = relationship('APIUsage', back_populates='api_key')

class APIUsage(Base):
    __tablename__ = 'api_usage'
    
    id = Column(Integer, primary_key=True, index=True)
    api_key_id = Column(Integer, ForeignKey('api_keys.id', ondelete='CASCADE'), index=True)
    endpoint = Column(String(200), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    ip_address = Column(String(45), nullable=True, index=True)
    user_agent = Column(Text, nullable=True)
    response_status = Column(Integer, nullable=True, index=True)
    response_time = Column(Float, nullable=True)
    captcha_type = Column(String(50), nullable=True, index=True)
    task_id = Column(String(100), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    api_key = relationship('APIKey', back_populates='usage_logs')
    
    __table_args__ = (
        Index('idx_api_key_timestamp', 'api_key_id', 'timestamp'),
        Index('idx_timestamp_status', 'timestamp', 'response_status'),
        Index('idx_ip_timestamp', 'ip_address', 'timestamp'),
    )

class AdminUser(Base):
    __tablename__ = 'admin_users'
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
