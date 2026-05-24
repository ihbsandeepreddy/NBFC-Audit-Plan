"""Complete Exception Register API"""
import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import get_db
from models.exception import AuditException, ExceptionStatus, RiskRating

router = APIRouter()

class ExceptionCreate(BaseModel):
    cap_seq: str
    nature: str
    description: str
    account_or_lan: Optional[str] = None
    amount_crore: Optional[float] = None
    risk_rating: str = "high"
    suam_ref: Optional[str] = None
    wp_reference: str = ""

class ExceptionUpdate(BaseModel):
    nature: Optional[str] = None
    description: Optional[str] = None
    amount_crore: Optional[float] = None
    risk_rating: Optional[str] = None
    suam_ref: Optional[str] = None
    management_response: Optional[str] = None
    management_agrees: Optional[str] = None
    status: Optional[str] = None
    resolution_notes: Optional[str] = None

def _s(e):
    return {"id": str(e.id), "engagement_id": str(e.engagement_id), "exception_ref": e.exception_ref,
            "cap_seq": e.cap_seq, "nature": e.nature, "description": e.description,
            "account_or_lan": e.account_or_lan, "amount_crore": float(e.amount_crore) if e.amount_crore else None,
            "risk_rating": e.risk_rating.value if e.risk_rating else None, "suam_ref": e.suam_ref,
            "wp_reference": e.wp_reference, "management_response": e.management_response,
            "management_agrees": e.management_agrees, "status": e.status.value if e.status else "open",
            "resolution_notes": e.resolution_notes,
            "resolved_date": e.resolved_date.isoformat() if e.resolved_date else None,
            "created_at": e.created_at.isoformat() if e.created_at else None}

@router.get("/{engagement_id}")
async def list_exceptions(engagement_id: str, status: Optional[str]=None, db: AsyncSession=Depends(get_db)):
    stmt = select(AuditException).where(AuditException.engagement_id == engagement_id)
    if status:
        stmt = stmt.where(AuditException.status == status)
    result = await db.execute(stmt.order_by(AuditException.created_at.desc()))
    return [_s(e) for e in result.scalars().all()]

@router.post("/{engagement_id}", status_code=201)
async def create_exception(engagement_id: str, data: ExceptionCreate, db: AsyncSession=Depends(get_db)):
    count_result = await db.execute(select(func.count(AuditException.id)).where(AuditException.engagement_id==engagement_id))
    count = count_result.scalar() or 0
    exc = AuditException(id=uuid.uuid4(), engagement_id=engagement_id,
        exception_ref=f"EXC-{str(count+1).zfill(3)}", cap_seq=data.cap_seq, nature=data.nature,
        description=data.description, account_or_lan=data.account_or_lan, amount_crore=data.amount_crore,
        risk_rating=RiskRating(data.risk_rating), suam_ref=data.suam_ref, wp_reference=data.wp_reference,
        status=ExceptionStatus.OPEN)
    db.add(exc)
    await db.commit()
    await db.refresh(exc)
    return _s(exc)

@router.patch("/{engagement_id}/{exception_id}")
async def update_exception(engagement_id: str, exception_id: str, data: ExceptionUpdate, db: AsyncSession=Depends(get_db)):
    result = await db.execute(select(AuditException).where(AuditException.engagement_id==engagement_id, AuditException.id==exception_id))
    exc = result.scalar_one_or_none()
    if not exc:
        raise HTTPException(404, "Exception not found")
    d = data.dict(exclude_none=True)
    for f in ["nature","description","amount_crore","suam_ref","wp_reference","management_response","management_agrees","resolution_notes"]:
        if f in d: setattr(exc, f, d[f])
    if "risk_rating" in d: exc.risk_rating = RiskRating(d["risk_rating"])
    if "status" in d:
        exc.status = ExceptionStatus(d["status"])
        if d["status"] == "resolved": exc.resolved_date = datetime.utcnow()
    exc.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(exc)
    return _s(exc)

@router.get("/{engagement_id}/summary")
async def exceptions_summary(engagement_id: str, db: AsyncSession=Depends(get_db)):
    result = await db.execute(select(AuditException).where(AuditException.engagement_id==engagement_id))
    excs = result.scalars().all()
    return {"total": len(excs),
            "open": sum(1 for e in excs if e.status==ExceptionStatus.OPEN),
            "resolved": sum(1 for e in excs if e.status==ExceptionStatus.RESOLVED),
            "caro_adverse": sum(1 for e in excs if e.status==ExceptionStatus.CARO_ADVERSE),
            "high_risk": sum(1 for e in excs if e.risk_rating==RiskRating.HIGH),
            "total_amount_crore": round(sum(float(e.amount_crore) for e in excs if e.amount_crore), 2),
            "in_suam": sum(1 for e in excs if e.suam_ref)}
