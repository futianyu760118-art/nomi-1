from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SchemaVersion(Base):
    __tablename__ = "schema_versions"
    version = Column(Integer, primary_key=True)
    applied_at = Column(String(40), default=timestamp, nullable=False)


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    mode = Column(String(20), nullable=False)
    start_date = Column(String(10), nullable=False)
    end_date = Column(String(10), nullable=False)
    last_sync = Column(String(40))


class ExternalProject(Base):
    __tablename__ = "external_projects"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    provider = Column(String(30), nullable=False)
    external_id = Column(String(200), nullable=False)
    data = Column(JSON, default=dict, nullable=False)
    __table_args__ = (UniqueConstraint("provider", "external_id"),)


class Requirement(Base):
    __tablename__ = "requirements"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    key = Column(String(40), nullable=False)
    external_id = Column(String(100))
    title = Column(String(500), nullable=False)
    module = Column(String(200), nullable=False)
    owner = Column(String(200), nullable=False)
    priority = Column(String(10), nullable=False)
    status = Column(String(30), nullable=False)
    week = Column(Integer, nullable=False)
    start = Column(String(10))
    due = Column(String(10))
    description = Column(Text, default="", nullable=False)
    criteria = Column(JSON, default=list, nullable=False)
    plane_url = Column(Text)
    blocked_progress = Column(Integer, default=0, nullable=False)
    active = Column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("project_id", "key"),)


class GitLink(Base):
    __tablename__ = "requirement_git_links"
    id = Column(Integer, primary_key=True)
    requirement_id = Column(Integer, ForeignKey("requirements.id"), nullable=False, unique=True)
    data = Column(JSON, default=dict, nullable=False)


class Inspection(Base):
    __tablename__ = "ai_inspections"
    id = Column(Integer, primary_key=True)
    requirement_id = Column(Integer, ForeignKey("requirements.id"), nullable=False, index=True)
    created_at = Column(String(40), default=timestamp, nullable=False)
    source = Column(String(20), nullable=False)
    commit_sha = Column(String(80))
    data = Column(JSON, nullable=False)


class Risk(Base):
    __tablename__ = "risks"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    requirement_id = Column(Integer, ForeignKey("requirements.id"), nullable=False)
    rule = Column(String(50), nullable=False)
    level = Column(String(10), nullable=False)
    title = Column(String(500), nullable=False)
    action = Column(Text, nullable=False)
    source = Column(String(30), nullable=False)
    status = Column(String(20), default="OPEN", nullable=False)
    created_at = Column(String(40), default=timestamp, nullable=False)
    __table_args__ = (UniqueConstraint("requirement_id", "rule"),)


class WeeklySnapshot(Base):
    __tablename__ = "weekly_snapshots"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    captured_at = Column(String(40), default=timestamp, nullable=False)
    data = Column(JSON, nullable=False)


class SyncLog(Base):
    __tablename__ = "sync_logs"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    source = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(String(40), default=timestamp, nullable=False)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    key = Column(String(100), primary_key=True)
    data = Column(JSON, nullable=False)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    role = Column(String(20), nullable=False)
