"""
Complete CAP API — Procedures listing, updates, bulk status, phase progress
"""

import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.database import get_db
from models.cap import CAPProcedure, ProcedureStatus, ReviewStatus

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ProcedureUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    budget_hours: Optional[int] = None
    actual_hours: Optional[float] = None
    start_date: Optional[str] = None
    completion_date: Optional[str] = None
    team_response: Optional[str] = None
    exceptions_found: Optional[bool] = None
    observation: Optional[str] = None
    reviewer_comments: Optional[str] = None
    review_status: Optional[str] = None
    reviewed_by: Optional[str] = None


def _serialize_proc(p: CAPProcedure) -> dict:
    return {
        "id": str(p.id),
        "engagement_id": str(p.engagement_id),
        "seq_number": p.seq_number,
        "phase": p.phase.value if p.phase else None,
        "section": p.section,
        "procedure_name": p.procedure_name,
        "procedure_description": p.procedure_description,
        "applicable_to": p.applicable_to,
        "risk_rating": p.risk_rating.value if p.risk_rating else None,
        "assertion": p.assertion,
        "regulatory_reference": p.regulatory_reference,
        "expected_control": p.expected_control,
        "data_analytics_step": p.data_analytics_step,
        "documents_to_obtain": p.documents_to_obtain,
        "wp_reference": p.wp_reference,
        "status": p.status.value if p.status else "pending",
        "assigned_to": p.assigned_to,
        "budget_hours": p.budget_hours,
        "actual_hours": float(p.actual_hours) if p.actual_hours else None,
        "start_date": p.start_date.isoformat() if p.start_date else None,
        "completion_date": p.completion_date.isoformat() if p.completion_date else None,
        "team_response": p.team_response or "",
        "exceptions_found": p.exceptions_found or False,
        "observation": p.observation or "",
        "reviewer_comments": p.reviewer_comments or "",
        "review_status": p.review_status.value if p.review_status else "not_reviewed",
        "reviewed_by": p.reviewed_by,
        "reviewed_at": p.reviewed_at.isoformat() if p.reviewed_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{engagement_id}/procedures")
async def list_procedures(
    engagement_id: str,
    phase: Optional[str] = None,
    status: Optional[str] = None,
    assigned_to: Optional[str] = None,
    exceptions_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """List all CAP procedures with optional filters"""
    stmt = select(CAPProcedure).where(CAPProcedure.engagement_id == engagement_id)

    if phase:
        stmt = stmt.where(CAPProcedure.phase == phase)
    if status:
        stmt = stmt.where(CAPProcedure.status == status)
    if assigned_to:
        stmt = stmt.where(CAPProcedure.assigned_to == assigned_to)
    if exceptions_only:
        stmt = stmt.where(CAPProcedure.exceptions_found == True)

    stmt = stmt.order_by(CAPProcedure.seq_number)
    result = await db.execute(stmt)
    procedures = result.scalars().all()
    return [_serialize_proc(p) for p in procedures]


@router.get("/{engagement_id}/procedures/{proc_id}")
async def get_procedure(engagement_id: str, proc_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single procedure"""
    result = await db.execute(
        select(CAPProcedure).where(
            CAPProcedure.engagement_id == engagement_id,
            CAPProcedure.id == proc_id,
        )
    )
    proc = result.scalar_one_or_none()
    if not proc:
        raise HTTPException(404, "Procedure not found")
    return _serialize_proc(proc)


@router.patch("/{engagement_id}/procedures/{proc_id}")
async def update_procedure(
    engagement_id: str,
    proc_id: str,
    data: ProcedureUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update dynamic fields of a CAP procedure"""
    result = await db.execute(
        select(CAPProcedure).where(
            CAPProcedure.engagement_id == engagement_id,
            CAPProcedure.id == proc_id,
        )
    )
    proc = result.scalar_one_or_none()
    if not proc:
        raise HTTPException(404, "Procedure not found")

    update_data = data.dict(exclude_none=True)

    if "status" in update_data:
        proc.status = ProcedureStatus(update_data["status"])
        if update_data["status"] == "completed" and not proc.completion_date:
            proc.completion_date = datetime.utcnow()
        if update_data["status"] == "in_progress" and not proc.start_date:
            proc.start_date = datetime.utcnow()

    if "review_status" in update_data:
        proc.review_status = ReviewStatus(update_data["review_status"])
        if update_data["review_status"] == "approved":
            proc.reviewed_at = datetime.utcnow()

    for field in ["assigned_to", "budget_hours", "actual_hours", "team_response",
                  "exceptions_found", "observation", "reviewer_comments", "reviewed_by"]:
        if field in update_data:
            setattr(proc, field, update_data[field])

    if "start_date" in update_data and update_data["start_date"]:
        proc.start_date = datetime.fromisoformat(update_data["start_date"])
    if "completion_date" in update_data and update_data["completion_date"]:
        proc.completion_date = datetime.fromisoformat(update_data["completion_date"])

    proc.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(proc)
    return _serialize_proc(proc)


@router.post("/{engagement_id}/procedures/bulk-status")
async def bulk_update_status(
    engagement_id: str,
    proc_ids: List[str],
    new_status: str,
    db: AsyncSession = Depends(get_db),
):
    """Bulk update status for multiple procedures"""
    result = await db.execute(
        select(CAPProcedure).where(
            CAPProcedure.engagement_id == engagement_id,
            CAPProcedure.id.in_(proc_ids),
        )
    )
    procedures = result.scalars().all()

    for proc in procedures:
        proc.status = ProcedureStatus(new_status)
        proc.updated_at = datetime.utcnow()

    await db.commit()
    return {"updated": len(procedures), "status": new_status}


@router.get("/{engagement_id}/procedures/exceptions/summary")
async def get_exceptions_summary(engagement_id: str, db: AsyncSession = Depends(get_db)):
    """Get summary of procedures with exceptions by phase"""
    result = await db.execute(
        select(CAPProcedure).where(
            CAPProcedure.engagement_id == engagement_id,
            CAPProcedure.exceptions_found == True,
        )
    )
    procs = result.scalars().all()
    return {
        "total_exceptions": len(procs),
        "by_phase": {
            ph: len([p for p in procs if p.phase and p.phase.value == ph])
            for ph in ["planning", "risk_assessment", "controls", "substantive", "completion"]
        },
        "procedures": [{"seq": p.seq_number, "name": p.procedure_name, "phase": p.phase.value if p.phase else None}
                       for p in procs],
    }
