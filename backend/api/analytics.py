"""
Complete Analytics API - Upload, Schema Normalize, Run DA, Results, Credit Validation
Handles 10M+ rows via Polars + DuckDB background processing
"""

import os
import uuid
import asyncio
import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import get_db
from core.config import settings
from models.analytics_job import AnalyticsJob, JobStatus, JobType
from analytics.normalizer import SchemaNormalizer

router = APIRouter()
logger = logging.getLogger(__name__)

UPLOAD_DIR = settings.UPLOAD_DIR
os.makedirs(UPLOAD_DIR, exist_ok=True)


class NormalizeRequest(BaseModel):
    job_id: str
    mapping: dict  # { "standard_col": "user_col" }


class RunDARequest(BaseModel):
    job_id: str
    da_ref: str
    additional_inputs: Optional[dict] = None  # e.g., {"gl_data_job_id": "xxx"}


def _s(job: AnalyticsJob) -> dict:
    return {"id": str(job.id), "engagement_id": str(job.engagement_id), "job_type": job.job_type.value if job.job_type else None,
            "da_ref": job.da_ref, "status": job.status.value if job.status else "uploaded",
            "original_filename": job.original_filename, "file_size_bytes": job.file_size_bytes,
            "total_records": job.total_records, "records_processed": job.records_processed,
            "exceptions_found": job.exceptions_found, "progress_percent": job.progress_percent,
            "results_summary": job.results_summary, "output_file_path": job.output_file_path,
            "error_message": job.error_message, "column_mapping": job.column_mapping,
            "normalization_status": job.normalization_status,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "created_at": job.created_at.isoformat() if job.created_at else None}


@router.post("/{engagement_id}/upload")
async def upload_file(engagement_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Upload CSV or XLSX file for analytics processing"""
    if not file.filename:
        raise HTTPException(400, "No file provided")
    
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("csv", "xlsx", "xls"):
        raise HTTPException(400, "Only CSV and XLSX files accepted")

    content = await file.read()
    file_size = len(content)
    
    if file_size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit")

    job_id = uuid.uuid4()
    file_path = os.path.join(UPLOAD_DIR, f"{job_id}.{ext}")
    with open(file_path, "wb") as f:
        f.write(content)

    # Count records
    total_records = await asyncio.to_thread(_count_records, file_path, ext)

    job = AnalyticsJob(id=job_id, engagement_id=engagement_id, job_type=JobType.LMS_DATA_INTEGRITY,
        status=JobStatus.UPLOADED, original_filename=file.filename, file_size_bytes=file_size,
        file_path=file_path, file_format=ext, total_records=total_records, progress_percent=0)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Get column preview for normalization
    columns_preview = await asyncio.to_thread(_get_columns_preview, file_path, ext)
    auto_mapping = SchemaNormalizer.detect_column_mapping(columns_preview["columns"])
    
    return {**_s(job), "columns_preview": columns_preview, "auto_mapping": auto_mapping}


@router.post("/{engagement_id}/normalize")
async def normalize_schema(engagement_id: str, req: NormalizeRequest, db: AsyncSession = Depends(get_db)):
    """Save column mapping and normalize the uploaded file"""
    result = await db.execute(select(AnalyticsJob).where(AnalyticsJob.id == req.job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    job.column_mapping = req.mapping
    job.normalization_status = "completed"
    job.status = JobStatus.NORMALIZING
    await db.commit()
    await db.refresh(job)
    return _s(job)


@router.post("/{engagement_id}/run")
async def run_analytics(
    engagement_id: str, req: RunDARequest,
    background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)
):
    """Run a specific DA on normalized data (background task)"""
    result = await db.execute(select(AnalyticsJob).where(AnalyticsJob.id == req.job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    if not job.column_mapping:
        raise HTTPException(400, "Schema not normalized. Call /normalize first")

    job.da_ref = req.da_ref
    job.status = JobStatus.RUNNING
    job.started_at = datetime.utcnow()
    job.progress_percent = 0
    await db.commit()

    background_tasks.add_task(_run_da_background, str(job.id), engagement_id, req.da_ref, req.additional_inputs or {})
    return {"message": f"{req.da_ref} started", "job_id": str(job.id)}


@router.post("/{engagement_id}/validate-credit-policy")
async def run_credit_validation(
    engagement_id: str, req: RunDARequest,
    background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)
):
    """Validate loan data against stored credit policy"""
    result = await db.execute(select(AnalyticsJob).where(AnalyticsJob.id == req.job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    job.job_type = JobType.CREDIT_VALIDATION
    job.da_ref = "CREDIT-POLICY"
    job.status = JobStatus.RUNNING
    job.started_at = datetime.utcnow()
    await db.commit()

    background_tasks.add_task(_run_credit_validation_background, str(job.id), engagement_id)
    return {"message": "Credit policy validation started", "job_id": str(job.id)}


@router.get("/{engagement_id}/job/{job_id}")
async def get_job_status(engagement_id: str, job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AnalyticsJob).where(AnalyticsJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    return _s(job)


@router.get("/{engagement_id}/jobs")
async def list_jobs(engagement_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AnalyticsJob).where(AnalyticsJob.engagement_id == engagement_id).order_by(AnalyticsJob.created_at.desc())
    )
    return [_s(j) for j in result.scalars().all()]


@router.get("/{engagement_id}/results/{job_id}/download")
async def download_results(engagement_id: str, job_id: str, db: AsyncSession = Depends(get_db)):
    """Stream CSV output for completed job"""
    result = await db.execute(select(AnalyticsJob).where(AnalyticsJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job or job.status != JobStatus.COMPLETED:
        raise HTTPException(404, "Job not completed or not found")
    if not job.output_file_path or not os.path.exists(job.output_file_path):
        raise HTTPException(404, "Output file not found")

    filename = f"{job.da_ref}_{job_id[:8]}_results.csv"
    return FileResponse(job.output_file_path, media_type="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={filename}"})


# ── Background Processing ─────────────────────────────────────────────────────

def _count_records(file_path: str, ext: str) -> int:
    """Count records in file"""
    try:
        import polars as pl
        if ext == "csv":
            df = pl.read_csv(file_path, n_rows=0, infer_schema_length=0)
            # For actual count, use DuckDB
            import duckdb
            con = duckdb.connect()
            return con.execute(f"SELECT COUNT(*) FROM read_csv_auto('{file_path}')").fetchone()[0]
        else:
            df = pl.read_excel(file_path)
            return len(df)
    except Exception:
        return 0


def _get_columns_preview(file_path: str, ext: str) -> dict:
    """Get column names and sample rows"""
    try:
        import polars as pl
        if ext == "csv":
            df = pl.read_csv(file_path, n_rows=5)
        else:
            df = pl.read_excel(file_path).head(5)
        return {"columns": df.columns, "sample_rows": df.to_dicts(), "dtypes": {col: str(dt) for col, dt in zip(df.columns, df.dtypes)}}
    except Exception as e:
        return {"columns": [], "sample_rows": [], "error": str(e)}


async def _run_da_background(job_id: str, engagement_id: str, da_ref: str, additional_inputs: dict):
    """Background task: load normalized data, run DA, save CSV output"""
    from core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(AnalyticsJob).where(AnalyticsJob.id == job_id))
            job = result.scalar_one_or_none()
            if not job: return

            import polars as pl
            from analytics.engine import engine

            # Load the file
            if job.file_format == "csv":
                df = pl.scan_csv(job.file_path)
            else:
                df = pl.read_excel(job.file_path).lazy()

            # Apply column mapping
            if job.column_mapping:
                reverse_map = {v: k for k, v in job.column_mapping.items() if v}
                df = df.rename(reverse_map)

            # Run DA
            da_result = await engine.run_analytics(da_ref=da_ref, loan_tape=df, **additional_inputs)

            # Save output as CSV
            output_path = os.path.join(UPLOAD_DIR, f"{job_id}_{da_ref}_output.csv")
            if "results" in da_result and "exceptions_df" in da_result["results"]:
                exc_df = da_result["results"]["exceptions_df"]
                if exc_df is not None and len(exc_df) > 0:
                    exc_df.write_csv(output_path)

            # Update job
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.progress_percent = 100
            job.exceptions_found = da_result.get("results", {}).get("exceptions_count", 0)
            job.results_summary = da_result.get("results", {}).get("summary", {})
            job.output_file_path = output_path if os.path.exists(output_path) else None
            if job.started_at:
                job.duration_seconds = int((job.completed_at - job.started_at).total_seconds())
            await db.commit()

        except Exception as e:
            logger.error(f"DA job {job_id} failed: {e}")
            result = await db.execute(select(AnalyticsJob).where(AnalyticsJob.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                await db.commit()


async def _run_credit_validation_background(job_id: str, engagement_id: str):
    """Background task: run credit policy validation"""
    from core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(AnalyticsJob).where(AnalyticsJob.id == job_id))
            job = result.scalar_one_or_none()
            if not job: return

            from models.credit_policy import CreditPolicy
            policy_result = await db.execute(select(CreditPolicy).where(CreditPolicy.engagement_id == engagement_id))
            policies = [{"product_code": p.product_code, "min_age": p.min_age, "max_age": p.max_age,
                         "max_ticket_size": float(p.max_ticket_size), "rate_floor": float(p.rate_floor),
                         "rate_ceiling": float(p.rate_ceiling), "min_bureau_score": p.min_bureau_score,
                         "max_foir": float(p.max_foir), "max_ltv": float(p.max_ltv),
                         "max_tenure_months": p.max_tenure_months}
                        for p in policy_result.scalars().all()]

            import polars as pl
            from analytics.credit_policy_validator import validate_portfolio

            if job.file_format == "csv":
                df = pl.scan_csv(job.file_path)
            else:
                df = pl.read_excel(job.file_path).lazy()

            if job.column_mapping:
                reverse_map = {v: k for k, v in job.column_mapping.items() if v}
                df = df.rename(reverse_map)

            validation_result = await asyncio.to_thread(validate_portfolio, df, policies)

            output_path = os.path.join(UPLOAD_DIR, f"{job_id}_credit_violations.csv")
            violations_df = validation_result.get("violations_df")
            if violations_df is not None and len(violations_df) > 0:
                violations_df.write_csv(output_path)

            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.progress_percent = 100
            job.exceptions_found = validation_result.get("violations_count", 0)
            job.results_summary = {k: v for k, v in validation_result.items() if k != "violations_df"}
            job.output_file_path = output_path if os.path.exists(output_path) else None
            await db.commit()

        except Exception as e:
            logger.error(f"Credit validation {job_id} failed: {e}")
            result = await db.execute(select(AnalyticsJob).where(AnalyticsJob.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                await db.commit()
