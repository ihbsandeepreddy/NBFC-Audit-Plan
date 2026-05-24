"""
CAP (Consolidated Audit Program) Procedure model
Stores dynamic execution data for audit procedures
"""

from sqlalchemy import Column, String, Integer, Numeric, DateTime, Boolean, Enum as SQLEnum, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from datetime import datetime
from enum import Enum
import uuid

from core.database import Base


class ProcedureStatus(str, Enum):
    """Status of audit procedure"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ReviewStatus(str, Enum):
    """Review sign-off status"""
    NOT_REVIEWED = "not_reviewed"
    IN_REVIEW = "in_review"
    APPROVED = "approved"


class RiskRating(str, Enum):
    """Risk rating"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Phase(str, Enum):
    """Audit phase"""
    PLANNING = "planning"
    RISK_ASSESSMENT = "risk_assessment"
    CONTROLS = "controls"
    SUBSTANTIVE = "substantive"
    COMPLETION = "completion"


class CAPProcedure(Base):
    __tablename__ = "cap_procedures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    engagement_id = Column(UUID(as_uuid=True), ForeignKey("engagements.id"), nullable=False, index=True)

    # Static fields (from Excel template)
    seq_number = Column(String(20), nullable=False)  # P.01, R.01, S.03, etc.
    phase = Column(SQLEnum(Phase), nullable=False, index=True)
    section = Column(String(100), nullable=False)
    procedure_name = Column(String(255), nullable=False)
    procedure_description = Column(Text, nullable=True)
    applicable_to = Column(String(50), nullable=False)  # All, Upper Layer, etc.
    risk_rating = Column(SQLEnum(RiskRating), nullable=False)
    assertion = Column(String(20), nullable=False)  # E/O, C, A/V, etc.
    regulatory_reference = Column(String(255), nullable=True)  # SA/Ind AS/RBI
    expected_control = Column(Text, nullable=True)
    data_analytics_step = Column(String(255), nullable=True)  # DA-001, DA-002, etc.
    documents_to_obtain = Column(Text, nullable=True)
    wp_reference = Column(String(100), nullable=True)

    # Dynamic fields (auditor fills during execution)
    status = Column(SQLEnum(ProcedureStatus), default=ProcedureStatus.PENDING, index=True)
    assigned_to = Column(String(100), nullable=True)  # Staff code
    budget_hours = Column(Integer, nullable=True)
    actual_hours = Column(Numeric(10, 2), nullable=True)
    start_date = Column(DateTime, nullable=True)
    completion_date = Column(DateTime, nullable=True)

    # Team Response (findings documentation)
    team_response = Column(Text, nullable=True)
    exceptions_found = Column(Boolean, default=False, index=True)
    observation = Column(Text, nullable=True)

    # Review & Sign-off
    reviewer_comments = Column(Text, nullable=True)
    review_status = Column(SQLEnum(ReviewStatus), default=ReviewStatus.NOT_REVIEWED)
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(UUID(as_uuid=True), nullable=True)

    def __repr__(self):
        return f"<CAPProcedure {self.seq_number} ({self.status})>"
