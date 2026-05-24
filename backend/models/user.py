"""
User model with role-based access control
"""

from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from enum import Enum
import uuid

from core.database import Base
from core.security import hash_password


class UserRole(str, Enum):
    """User roles in the audit engagement"""
    PARTNER = "partner"              # Engagement Partner - read-only
    EQCR = "eqcr"                   # EQCR Partner - read-only + EQCR checklist
    MANAGER = "manager"             # Engagement Manager - full write
    SENIOR_AUDITOR = "senior_auditor"  # Senior Auditor - write assigned procedures
    IT_AUDITOR = "it_auditor"       # IT Auditor - write IT procedures + analytics
    ARTICLED_ASSISTANT = "articled_assistant"  # Articled Assistant - write own procedures
    SPECIALIST = "specialist"        # Specialist - write specialist sections


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.ARTICLED_ASSISTANT)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    def set_password(self, password: str):
        """Hash and set password"""
        self.hashed_password = hash_password(password)

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
