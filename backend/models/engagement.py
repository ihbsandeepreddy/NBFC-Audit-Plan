"""
Engagement model - represents an NBFC audit engagement
"""

from sqlalchemy import Column, String, Numeric, DateTime, Boolean, Enum as SQLEnum, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from datetime import datetime
from enum import Enum
import uuid

from core.database import Base


class NBFCLayer(str, Enum):
    """RBI regulatory layer"""
    UPPER_LAYER = "upper_layer"
    MIDDLE_LAYER = "middle_layer"
    BASE_LAYER = "base_layer"


class DepositCategory(str, Enum):
    """Deposit taking status"""
    DEPOSIT_TAKING = "deposit_taking"
    NON_DEPOSIT_TAKING = "non_deposit_taking"


class EngagementType(str, Enum):
    """Type of audit engagement"""
    STATUTORY_AUDIT = "statutory_audit"
    INTERNAL_AUDIT = "internal_audit"
    LIMITED_REVIEW = "limited_review"


class SEBIStatus(str, Enum):
    """SEBI listing status"""
    NOT_LISTED = "not_listed"
    LISTED_EQUITY = "listed_equity"
    LISTED_NCD = "listed_ncd"
    LISTED_BOTH = "listed_both"


class RiskLevel(str, Enum):
    """Engagement risk level"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Engagement(Base):
    __tablename__ = "engagements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Client Details
    client_name = Column(String(255), nullable=False)
    client_registration_number = Column(String(50), nullable=True)
    audit_firm_name = Column(String(255), nullable=False)
    engagement_partner_name = Column(String(255), nullable=False)
    eqcr_partner_name = Column(String(255), nullable=False)
    file_reference = Column(String(50), nullable=False, unique=True)

    # Audit Period
    period_from = Column(DateTime, nullable=False)
    period_to = Column(DateTime, nullable=False)
    target_report_date = Column(DateTime, nullable=False)

    # Configuration
    nbfc_layer = Column(SQLEnum(NBFCLayer), nullable=False)
    deposit_category = Column(SQLEnum(DepositCategory), nullable=False)
    engagement_type = Column(SQLEnum(EngagementType), nullable=False)
    sebi_status = Column(SQLEnum(SEBIStatus), nullable=False)
    risk_level = Column(SQLEnum(RiskLevel), nullable=False, default=RiskLevel.HIGH)

    # Materiality
    overall_materiality = Column(Numeric(15, 2), nullable=True)
    performance_materiality = Column(Numeric(15, 2), nullable=True)
    trivial_threshold = Column(Numeric(15, 2), nullable=True)

    # Portfolio Metrics
    gross_loan_portfolio = Column(Numeric(15, 2), nullable=True)
    tier_i_capital = Column(Numeric(15, 2), nullable=True)
    reporting_currency = Column(String(3), default="INR")

    # Team Configuration
    team_roster = Column(JSON, nullable=True)  # Staff code, name, role, hours, rate

    # Qualitative Flags
    qualitative_flags = Column(JSON, nullable=True)  # Fraud, RBI penalty, RPT, going concern

    # Status
    is_active = Column(Boolean, default=True)
    created_by = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Engagement {self.file_reference}>"
