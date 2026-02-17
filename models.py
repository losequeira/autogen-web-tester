"""
Database models for multi-user AutoGen Web Tester.

Uses SQLAlchemy ORM with support for SQLite (5-20 users) and PostgreSQL (50+ users).
"""

from datetime import datetime
from enum import Enum as PyEnum
from flask_login import UserMixin
from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, scoped_session, sessionmaker
import bcrypt

Base = declarative_base()


class WorkspaceType(PyEnum):
    """Workspace type enumeration."""
    PRIVATE = 'private'
    SHARED = 'shared'


class WorkspaceRole(PyEnum):
    """Workspace member role enumeration."""
    OWNER = 'owner'
    EDITOR = 'editor'
    VIEWER = 'viewer'


class TestSource(PyEnum):
    """Test source type enumeration."""
    AI = 'ai'
    CODEGEN = 'codegen'
    MANUAL = 'manual'


class User(Base, UserMixin):
    """User account model."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    owned_workspaces = relationship('Workspace', back_populates='owner',
                                   foreign_keys='Workspace.owner_id')
    workspace_memberships = relationship('WorkspaceMember', back_populates='user',
                                        cascade='all, delete-orphan')
    created_tests = relationship('Test', back_populates='creator',
                                foreign_keys='Test.created_by')
    created_ai_steps = relationship('AiStep', back_populates='creator',
                                   foreign_keys='AiStep.created_by')
    preferences = relationship('UserPreference', back_populates='user',
                              cascade='all, delete-orphan')

    def set_password(self, password: str):
        """Hash and set user password using bcrypt."""
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt(rounds=12)
        ).decode('utf-8')

    def check_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )

    def to_dict(self):
        """Convert user to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active
        }


class Workspace(Base):
    """Workspace model for organizing tests."""
    __tablename__ = 'workspaces'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    type = Column(Enum(WorkspaceType), nullable=False, default=WorkspaceType.PRIVATE)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    owner = relationship('User', back_populates='owned_workspaces',
                        foreign_keys=[owner_id])
    members = relationship('WorkspaceMember', back_populates='workspace',
                          cascade='all, delete-orphan')
    tests = relationship('Test', back_populates='workspace',
                        cascade='all, delete-orphan')
    ai_steps = relationship('AiStep', back_populates='workspace',
                           cascade='all, delete-orphan')

    def to_dict(self, include_members=False):
        """Convert workspace to dictionary for JSON serialization."""
        result = {
            'id': self.id,
            'name': self.name,
            'type': self.type.value,
            'owner_id': self.owner_id,
            'owner_username': self.owner.username if self.owner else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'test_count': len(self.tests),
            'ai_step_count': len(self.ai_steps)
        }

        if include_members:
            result['members'] = [m.to_dict() for m in self.members]

        return result

    def get_user_role(self, user_id: int):
        """Get user's role in this workspace (or None if not a member)."""
        if self.owner_id == user_id:
            return WorkspaceRole.OWNER

        for member in self.members:
            if member.user_id == user_id:
                return member.role

        return None

    def has_access(self, user_id: int, permission: str = 'read') -> bool:
        """Check if user has specified permission in this workspace."""
        role = self.get_user_role(user_id)

        if role is None:
            return False

        if role == WorkspaceRole.OWNER:
            return True  # Owner has all permissions

        if permission == 'read':
            return True  # All members can read

        if permission == 'write':
            return role in (WorkspaceRole.OWNER, WorkspaceRole.EDITOR)

        return False


class WorkspaceMember(Base):
    """Workspace membership model."""
    __tablename__ = 'workspace_members'

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey('workspaces.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    role = Column(Enum(WorkspaceRole), nullable=False, default=WorkspaceRole.VIEWER)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    workspace = relationship('Workspace', back_populates='members')
    user = relationship('User', back_populates='workspace_memberships')

    # Unique constraint: user can only be in workspace once
    __table_args__ = (
        UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_user'),
    )

    def to_dict(self):
        """Convert membership to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'email': self.user.email if self.user else None,
            'role': self.role.value,
            'added_at': self.added_at.isoformat() if self.added_at else None
        }


class Test(Base):
    """Test model — stores Playwright test code and metadata."""
    __tablename__ = 'tests'

    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    code = Column(Text, nullable=True)
    workspace_id = Column(Integer, ForeignKey('workspaces.id'), nullable=False)
    source = Column(Enum(TestSource), nullable=False, default=TestSource.MANUAL)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                       nullable=False)
    last_run_status = Column(String(20))
    last_run_time = Column(DateTime)
    description = Column(Text)

    # Relationships
    workspace = relationship('Workspace', back_populates='tests')
    creator = relationship('User', back_populates='created_tests',
                          foreign_keys=[created_by])
    artifacts = relationship('TestArtifact', back_populates='test',
                            cascade='all, delete-orphan',
                            order_by='TestArtifact.created_at.desc()')

    # Unique constraint: filename must be unique within workspace
    __table_args__ = (
        UniqueConstraint('workspace_id', 'filename', name='uq_workspace_filename'),
    )

    def to_dict(self, include_code=False):
        """Convert test to dictionary for JSON serialization."""
        result = {
            'id': self.id,
            'filename': self.filename,
            'name': self.name,
            'workspace_id': self.workspace_id,
            'source': self.source.value,
            'created_by': self.created_by,
            'creator_username': self.creator.username if self.creator else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_run_status': self.last_run_status,
            'last_run_time': self.last_run_time.isoformat() if self.last_run_time else None,
            'description': self.description,
            'artifacts': [a.to_dict() for a in self.artifacts]
        }
        if include_code:
            result['code'] = self.code
        return result


class AiStep(Base):
    """AI step test model — stores natural language test steps."""
    __tablename__ = 'ai_steps'

    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    steps = Column(Text, nullable=False)
    workspace_id = Column(Integer, ForeignKey('workspaces.id'), nullable=False)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                       nullable=False)
    last_run_status = Column(String(20))
    last_run_time = Column(DateTime)

    # Relationships
    workspace = relationship('Workspace', back_populates='ai_steps')
    creator = relationship('User', back_populates='created_ai_steps',
                          foreign_keys=[created_by])

    __table_args__ = (
        UniqueConstraint('workspace_id', 'filename', name='uq_workspace_ai_step_filename'),
    )

    def to_dict(self):
        return {
            'filename': self.filename,
            'name': self.name,
            'steps': self.steps,
            'created': self.created_at.isoformat() if self.created_at else None,
            'updated': self.updated_at.isoformat() if self.updated_at else None,
            'last_run_status': self.last_run_status,
            'last_run_time': self.last_run_time.isoformat() if self.last_run_time else None,
        }


class TestArtifact(Base):
    """Test artifact metadata — references binary files on disk."""
    __tablename__ = 'test_artifacts'

    id = Column(Integer, primary_key=True)
    test_id = Column(Integer, ForeignKey('tests.id'), nullable=False)
    timestamp = Column(String(50), nullable=False)
    video_path = Column(String(500))
    video_size_mb = Column(Float, default=0)
    har_path = Column(String(500))
    status = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    test = relationship('Test', back_populates='artifacts')

    def to_dict(self):
        return {
            'timestamp': self.timestamp,
            'video_path': self.video_path,
            'video_size_mb': self.video_size_mb,
            'har_path': self.har_path,
            'status': self.status,
        }


class UserPreference(Base):
    """User preferences stored server-side for cross-device/session persistence."""
    __tablename__ = 'user_preferences'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    key = Column(String(100), nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                       nullable=False)

    # Relationships
    user = relationship('User', back_populates='preferences')

    # Unique constraint: one value per key per user
    __table_args__ = (
        UniqueConstraint('user_id', 'key', name='uq_user_preference_key'),
    )


# Database session management
_engine = None
_session_factory = None
db_session = None


def init_db(database_url: str):
    """Initialize database connection and create tables."""
    global _engine, _session_factory, db_session

    _engine = create_engine(
        database_url,
        # SQLite specific settings
        connect_args={'check_same_thread': False} if 'sqlite' in database_url else {},
        echo=False  # Set to True for SQL debugging
    )

    _session_factory = sessionmaker(bind=_engine)
    db_session = scoped_session(_session_factory)

    # Create all tables
    Base.metadata.create_all(_engine)

    return db_session


def get_db_session():
    """Get current database session."""
    return db_session


def close_db_session():
    """Close database session."""
    if db_session:
        db_session.remove()
