"""
Exception Register model - tracks audit exceptions and findings
"""

from sqlalchemy import Column, String, Numeric, DateTime, Text, Enum as SQLEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from enum import Enum
import uuid

from core.database import Base


class ExceptionStatus(str, Enum):
    """Exception status in SUAM workflow"""
    OPEN = "open"
    PARTIALLY_OPEN = "partially_open"
    RESOLVED = "resolved"
    CARO_ADVERSE = "caro_adverse"


class RiskRating(str, Enum):
    """Risk rating of exception"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AuditException(Base):
    __tablename__ = "exceptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    engagement_id = Column(UUID(as_uuid=True), ForeignKey("engagements.id"), nullable=False, index=True)

    # Exception Identity
    exception_ref = Column(String(50), nullable=False, unique=True)  # EXC-001, EXC-002, etc.
    cap_seq = Column(String(20), nullable=False, index=True)  # Link to CAP procedure (S.03, C.01, etc.)

    # Description
    nature = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    account_or_lan = Column(String(255), nullable=True)
    amount_crore = Column(Numeric(15, 2), nullable=True)

    # Risk & Impact
    risk_rating = Column(SQLEnum(RiskRating), nullable=False)
    suam_ref = Column(String(50), nullable=True)  # Link to SUAM entry (MS-001, etc.)
    wp_reference = Column(String(100), nullable=True)

    # Management Response
    management_response = Column(Text, nullable=True)
    response_received_date = Column(DateTime, nullable=True)
    management_agrees = Column(String(50), nullable=True)  # Fully/Partially/Disagrees

    # Status Tracking
    status = Column(SQLEnum(ExceptionStatus), default=ExceptionStatus.OPEN, index=True)
    resolution_notes = Column(Text, nullable=True)
    resolved_date = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), nullable=True)

    def __repr__(self):
        return f"<Exception {self.exception_ref}>"
