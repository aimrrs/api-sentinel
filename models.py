from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    owner = relationship("User", back_populates="projects")
    sentinel_key = relationship("SentinelKey", back_populates="project", cascade="all, delete-orphan", uselist=False)

class SentinelKey(Base):
    __tablename__ = "sentinel_keys"
    id = Column(Integer, primary_key=True, index=True)
    key_string = Column(String, unique=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    monthly_budget_rupees = Column(Integer, default=5000)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    project = relationship("Project", back_populates="sentinel_key")
    usage_logs = relationship("UsageLog", back_populates="sentinel_key", cascade="all, delete-orphan")

class UsageLog(Base):
    __tablename__ = "usage_logs"
    id = Column(Integer, primary_key=True, index=True)
    sentinel_key_id = Column(Integer, ForeignKey("sentinel_keys.id", ondelete="CASCADE"))
    cost_rupees = Column(Float, nullable=False)
    usage_metadata = Column(JSONB)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    sentinel_key = relationship("SentinelKey", back_populates="usage_logs")