"""
Analytics Job model - tracks data upload and DA processing jobs
"""

from sqlalchemy import Column, String, Integer, DateTime, Float, Text, Enum as SQLEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from datetime import datetime
from enum import Enum
import uuid

from core.database import Base


class JobStatus(str, Enum):
    """Status of analytics job"""
    UPLOADED = "uploaded"
    NORMALIZING = "normalizing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    """Type of analytics job"""
    LMS_DATA_INTEGRITY = "lms_data_integrity"
    FINANCIAL_UPLOAD = "financial_upload"
    DATA_ANALYTICS = "data_analytics"
    CREDIT_VALIDATION = "credit_validation"


class AnalyticsJob(Base):
    __tablename__ = "analytics_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    engagement_id = Column(UUID(as_uuid=True), ForeignKey("engagements.id"), nullable=False, index=True)

    # Job Identity
    job_type = Column(SQLEnum(JobType), nullable=False)
    da_ref = Column(String(20), nullable=True)  # DA-001, DA-013, etc.
    status = Column(SQLEnum(JobStatus), default=JobStatus.UPLOADED, index=True)

    # File Information
    original_filename = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    file_path = Column(String(255), nullable=True)
    file_format = Column(String(10), nullable=False)  # csv, xlsx

    # Schema Normalization
    column_mapping = Column(JSON, nullable=True)  # { "user_col_name": "STANDARD_COL_NAME", ... }
    normalization_status = Column(String(50), nullable=True)  # pending, in_progress, completed

    # Processing
    total_records = Column(Integer, nullable=True)
    records_processed = Column(Integer, nullable=True)
    exceptions_found = Column(Integer, default=0)
    progress_percent = Column(Float, default=0.0)

    # Results
    results_summary = Column(JSON, nullable=True)  # { "dup_lans": 5, "null_fields": 10, ... }
    output_file_path = Column(String(255), nullable=True)  # Path to output CSV
    anomalies_count = Column(Integer, default=0)
    materiality_breaches = Column(Integer, default=0)

    # Execution
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Error Handling
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)

    # Metadata
    created_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AnalyticsJob {self.da_ref} ({self.status})>"
