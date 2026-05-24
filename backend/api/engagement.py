"""
Complete Engagement API — CRUD + Progress + Materiality
"""

import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.database import get_db
from models.engagement import Engagement
from models.cap import CAPProcedure, ProcedureStatus

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class TeamMemberIn(BaseModel):
    staff_code: str
    name: str
    role: str
    max_hours: int = 180
    rate_per_hour: float = 4500.0
    sections_assigned: str = ""
    notes: Optional[str] = None


class EngagementCreate(BaseModel):
    client_name: str
    audit_firm_name: str
    engagement_partner_name: str
    eqcr_partner_name: str
    file_reference: str
    period_from: str
    period_to: str
    target_report_date: str
    nbfc_layer: str = "upper_layer"
    deposit_category: str = "non_deposit_taking"
    engagement_type: str = "statutory_audit"
    sebi_status: str = "not_listed"
    risk_level: str = "high"
    gross_loan_portfolio: Optional[float] = None
    tier_i_capital: Optional[float] = None
    overall_materiality: Optional[float] = None
    performance_materiality: Optional[float] = None
    trivial_threshold: Optional[float] = None
    team_roster: Optional[List[TeamMemberIn]] = None
    qualitative_flags: Optional[List[dict]] = None


class MaterialityUpdate(BaseModel):
    overall_materiality: float
    performance_materiality: float
    trivial_threshold: float
    gross_loan_portfolio: Optional[float] = None
    tier_i_capital: Optional[float] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_404(engagement_id: str, db: AsyncSession) -> Engagement:
    result = await db.execute(select(Engagement).where(Engagement.id == engagement_id))
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(404, "Engagement not found")
    return e


def _serialize(e: Engagement) -> dict:
    return {
        "id": str(e.id),
        "client_name": e.client_name,
        "audit_firm_name": e.audit_firm_name,
        "engagement_partner_name": e.engagement_partner_name,
        "eqcr_partner_name": e.eqcr_partner_name,
        "file_reference": e.file_reference,
        "period_from": e.period_from.isoformat() if e.period_from else None,
        "period_to": e.period_to.isoformat() if e.period_to else None,
        "target_report_date": e.target_report_date.isoformat() if e.target_report_date else None,
        "nbfc_layer": e.nbfc_layer,
        "deposit_category": e.deposit_category,
        "engagement_type": e.engagement_type,
        "sebi_status": e.sebi_status,
        "risk_level": e.risk_level,
        "overall_materiality": float(e.overall_materiality) if e.overall_materiality else None,
        "performance_materiality": float(e.performance_materiality) if e.performance_materiality else None,
        "trivial_threshold": float(e.trivial_threshold) if e.trivial_threshold else None,
        "gross_loan_portfolio": float(e.gross_loan_portfolio) if e.gross_loan_portfolio else None,
        "tier_i_capital": float(e.tier_i_capital) if e.tier_i_capital else None,
        "team_roster": e.team_roster or [],
        "qualitative_flags": e.qualitative_flags or [],
        "is_active": e.is_active,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


async def _seed_cap_procedures(engagement_id, db: AsyncSession):
    """Seed all CAP procedures from static data for a new engagement"""
    try:
        from data.cap_procedures import CAP_PROCEDURES
    except ImportError:
        return  # Static data not yet created, skip seeding

    for proc_data in CAP_PROCEDURES:
        proc = CAPProcedure(
            id=uuid.uuid4(),
            engagement_id=engagement_id,
            seq_number=proc_data["seq_number"],
            phase=proc_data["phase"],
            section=proc_data["section"],
            procedure_name=proc_data["procedure_name"],
            procedure_description=proc_data.get("procedure_description", ""),
            applicable_to=proc_data.get("applicable_to", "ALL"),
            risk_rating=proc_data.get("risk_rating", "high"),
            assertion=proc_data.get("assertion", ""),
            regulatory_reference=proc_data.get("regulatory_reference", ""),
            expected_control=proc_data.get("expected_control", ""),
            data_analytics_step=proc_data.get("data_analytics_step", ""),
            documents_to_obtain=proc_data.get("documents_to_obtain", ""),
            wp_reference=proc_data.get("wp_reference", ""),
            status=ProcedureStatus.PENDING,
            team_response=proc_data.get("template_team_response", ""),
            budget_hours=proc_data.get("budget_hours"),
        )
        db.add(proc)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
async def list_engagements(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Engagement).where(Engagement.is_active == True).order_by(Engagement.created_at.desc())
    )
    return [_serialize(e) for e in result.scalars().all()]


@router.post("/", status_code=201)
async def create_engagement(data: EngagementCreate, db: AsyncSession = Depends(get_db)):
    # Unique file reference check
    existing = await db.execute(select(Engagement).where(Engagement.file_reference == data.file_reference))
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"File reference '{data.file_reference}' already exists")

    engagement = Engagement(
        id=uuid.uuid4(),
        client_name=data.client_name,
        audit_firm_name=data.audit_firm_name,
        engagement_partner_name=data.engagement_partner_name,
        eqcr_partner_name=data.eqcr_partner_name,
        file_reference=data.file_reference,
        period_from=datetime.fromisoformat(data.period_from),
        period_to=datetime.fromisoformat(data.period_to),
        target_report_date=datetime.fromisoformat(data.target_report_date),
        nbfc_layer=data.nbfc_layer,
        deposit_category=data.deposit_category,
        engagement_type=data.engagement_type,
        sebi_status=data.sebi_status,
        risk_level=data.risk_level,
        gross_loan_portfolio=data.gross_loan_portfolio,
        tier_i_capital=data.tier_i_capital,
        overall_materiality=data.overall_materiality,
        performance_materiality=data.performance_materiality,
        trivial_threshold=data.trivial_threshold,
        team_roster=[m.dict() for m in data.team_roster] if data.team_roster else [],
        qualitative_flags=data.qualitative_flags or [],
        created_by=uuid.uuid4(),
    )
    db.add(engagement)
    await db.flush()
    await _seed_cap_procedures(engagement.id, db)
    await db.commit()
    await db.refresh(engagement)
    return _serialize(engagement)


@router.get("/{engagement_id}")
async def get_engagement(engagement_id: str, db: AsyncSession = Depends(get_db)):
    return _serialize(await _get_or_404(engagement_id, db))


@router.put("/{engagement_id}")
async def update_engagement(engagement_id: str, data: EngagementCreate, db: AsyncSession = Depends(get_db)):
    e = await _get_or_404(engagement_id, db)
    for field in ["client_name", "audit_firm_name", "engagement_partner_name", "eqcr_partner_name",
                  "nbfc_layer", "deposit_category", "engagement_type", "sebi_status", "risk_level",
                  "gross_loan_portfolio", "tier_i_capital"]:
        setattr(e, field, getattr(data, field))
    e.team_roster = [m.dict() for m in data.team_roster] if data.team_roster else []
    e.qualitative_flags = data.qualitative_flags or []
    e.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(e)
    return _serialize(e)


@router.patch("/{engagement_id}/materiality")
async def update_materiality(engagement_id: str, data: MaterialityUpdate, db: AsyncSession = Depends(get_db)):
    e = await _get_or_404(engagement_id, db)
    e.overall_materiality = data.overall_materiality
    e.performance_materiality = data.performance_materiality
    e.trivial_threshold = data.trivial_threshold
    if data.gross_loan_portfolio:
        e.gross_loan_portfolio = data.gross_loan_portfolio
    if data.tier_i_capital:
        e.tier_i_capital = data.tier_i_capital
    e.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(e)
    return _serialize(e)


@router.get("/{engagement_id}/progress")
async def get_progress(engagement_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CAPProcedure).where(CAPProcedure.engagement_id == engagement_id)
    )
    procedures = result.scalars().all()

    phases: dict = {}
    for proc in procedures:
        ph = proc.phase.value if proc.phase else "unknown"
        if ph not in phases:
            phases[ph] = {"total": 0, "completed": 0, "in_progress": 0, "pending": 0, "exceptions": 0}
        phases[ph]["total"] += 1
        if proc.status == ProcedureStatus.COMPLETED:
            phases[ph]["completed"] += 1
        elif proc.status == ProcedureStatus.IN_PROGRESS:
            phases[ph]["in_progress"] += 1
        else:
            phases[ph]["pending"] += 1
        if proc.exceptions_found:
            phases[ph]["exceptions"] += 1

    total = len(procedures)
    completed = sum(1 for p in procedures if p.status == ProcedureStatus.COMPLETED)
    return {
        "total": total,
        "completed": completed,
        "in_progress": sum(1 for p in procedures if p.status == ProcedureStatus.IN_PROGRESS),
        "pending": sum(1 for p in procedures if p.status == ProcedureStatus.PENDING),
        "exceptions": sum(1 for p in procedures if p.exceptions_found),
        "completion_pct": round(completed / total * 100, 1) if total > 0 else 0,
        "phases": phases,
    }
