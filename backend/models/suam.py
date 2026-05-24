"""
SUAM (Schedule of Unadjusted Misstatements) model
Accumulates uncorrected misstatements for opinion determination
"""

from sqlalchemy import Column, String, Numeric, DateTime, Boolean, Text, Enum as SQLEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from datetime import datetime
from enum import Enum
import uuid

from core.database import Base


class MisstatementDirection(str, Enum):
    """Direction of misstatement"""
    OVERSTATEMENT = "overstatement"
    UNDERSTATEMENT = "understatement"


class SUAM(Base):
    __tablename__ = "suam"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    engagement_id = Column(UUID(as_uuid=True), ForeignKey("engagements.id"), nullable=False, index=True)

    # Misstatement Identity
    suam_ref = Column(String(50), nullable=False, unique=True)  # MS-001, MS-002, etc.
    exception_id = Column(UUID(as_uuid=True), nullable=True)  # Link to exception

    # Classification
    fs_area = Column(String(100), nullable=False)  # ECL Provision, Loan Portfolio, etc.
    direction = Column(SQLEnum(MisstatementDirection), nullable=False)
    amount_crore = Column(Numeric(15, 2), nullable=False)

    # Status
    is_corrected = Column(Boolean, default=False)
    correction_amount = Column(Numeric(15, 2), nullable=True)
    is_qualitative = Column(Boolean, default=False)  # Material by nature despite amount

    # Management Waiver
    has_waiver = Column(Boolean, default=False)
    waiver_letter = Column(Text, nullable=True)
    waiver_date = Column(DateTime, nullable=True)

    # Materiality Assessment
    exceeds_pm = Column(Boolean, default=False)  # Exceeds Performance Materiality
    exceeds_om = Column(Boolean, default=False)  # Exceeds Overall Materiality
    materiality_assessment = Column(JSON, nullable=True)  # { "om": value, "pm": value, "gap_pct": 0.45 }

    # Notes
    notes = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SUAM {self.suam_ref} {self.direction}>"
