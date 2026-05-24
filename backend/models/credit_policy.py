"""
Credit Policy model - stores product-wise lending policy parameters
Used for validation of credit appraisals (DA-010) and compliance checking
"""

from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from datetime import datetime
import uuid

from core.database import Base


class CreditPolicy(Base):
    __tablename__ = "credit_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    engagement_id = Column(UUID(as_uuid=True), ForeignKey("engagements.id"), nullable=False, index=True)

    # Product
    product_code = Column(String(50), nullable=False)
    product_name = Column(String(255), nullable=False)

    # Age Limits
    min_age = Column(Integer, nullable=False)  # years
    max_age = Column(Integer, nullable=False)

    # Ticket Size
    max_ticket_size = Column(Numeric(15, 2), nullable=False)  # ₹ Cr
    min_ticket_size = Column(Numeric(15, 2), nullable=True)

    # Interest Rate Band
    rate_floor = Column(Numeric(6, 2), nullable=False)  # % per annum
    rate_ceiling = Column(Numeric(6, 2), nullable=False)

    # Bureau Score
    min_bureau_score = Column(Integer, nullable=False)

    # Leverage Ratios
    max_foir = Column(Numeric(6, 2), nullable=False)  # Fixed Obligation to Income Ratio
    max_ltv = Column(Numeric(6, 2), nullable=False)   # Loan to Value Ratio

    # Tenure
    max_tenure_months = Column(Integer, nullable=False)
    min_tenure_months = Column(Integer, nullable=True)

    # Collateral
    collateral_required = Column(String(50), nullable=True)  # Yes/No/Conditional

    # Documentation
    mandatory_documents = Column(JSON, nullable=True)  # List of required docs

    # Approval Authority
    # dict: "₹10L-₹25L": "Credit Manager", "₹25L-₹1Cr": "Credit Committee", etc.
    sanction_authority_levels = Column(JSON, nullable=True)

    # Metadata
    version = Column(String(20), default="1.0")
    effective_from = Column(DateTime, nullable=False, default=datetime.utcnow)
    effective_to = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CreditPolicy {self.product_code}>"
