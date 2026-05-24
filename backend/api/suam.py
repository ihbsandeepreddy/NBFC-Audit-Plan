"""Complete SUAM API with auto-accumulation and opinion engine"""
import uuid
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import get_db
from models.suam import SUAM, MisstatementDirection
from models.engagement import Engagement

router = APIRouter()

class SUAMCreate(BaseModel):
    fs_area: str
    direction: str
    amount_crore: float
    is_corrected: bool = False
    is_qualitative: bool = False
    exception_id: Optional[str] = None
    notes: Optional[str] = None

class SUAMUpdate(BaseModel):
    is_corrected: Optional[bool] = None
    correction_amount: Optional[float] = None
    is_qualitative: Optional[bool] = None
    has_waiver: Optional[bool] = None
    waiver_letter: Optional[str] = None
    notes: Optional[str] = None

def _s(e):
    return {"id": str(e.id), "engagement_id": str(e.engagement_id), "suam_ref": e.suam_ref,
            "fs_area": e.fs_area, "direction": e.direction.value if e.direction else None,
            "amount_crore": float(e.amount_crore) if e.amount_crore else 0,
            "is_corrected": e.is_corrected, "is_qualitative": e.is_qualitative,
            "has_waiver": e.has_waiver, "exceeds_pm": e.exceeds_pm, "exceeds_om": e.exceeds_om,
            "notes": e.notes}

def _opinion_engine(entries, om: float, pm: float) -> dict:
    uncorrected = [e for e in entries if not e.is_corrected]
    total_uncorrected = sum(float(e.amount_crore) for e in uncorrected)
    individual_over_pm = [e for e in uncorrected if float(e.amount_crore) > pm]
    qualitative = [e for e in uncorrected if e.is_qualitative]
    
    if total_uncorrected > om or len(individual_over_pm) > 0:
        opinion = "modified_qualified"
        reason = "Uncorrected misstatement(s) exceed materiality — SA 705 Modified Opinion"
    elif total_uncorrected > pm:
        opinion = "modified_qualified"
        reason = f"Aggregate uncorrected (₹{total_uncorrected:.2f} Cr) exceeds PM (₹{pm:.2f} Cr)"
    elif qualitative:
        opinion = "modified_qualified"
        reason = "Qualitative material items identified — fraud / regulatory breach / RPT"
    else:
        opinion = "unmodified"
        reason = "No material uncorrected misstatements"
    
    return {"opinion": opinion, "reason": reason, "total_uncorrected": round(total_uncorrected, 2),
            "individual_over_pm_count": len(individual_over_pm),
            "aggregate_vs_pm_pct": round(total_uncorrected / pm * 100, 1) if pm > 0 else 0,
            "qualitative_items": len(qualitative)}

@router.get("/{engagement_id}")
async def get_suam(engagement_id: str, db: AsyncSession=Depends(get_db)):
    result = await db.execute(select(SUAM).where(SUAM.engagement_id==engagement_id))
    entries = result.scalars().all()
    # Get materiality from engagement
    eng_result = await db.execute(select(Engagement).where(Engagement.id==engagement_id))
    eng = eng_result.scalar_one_or_none()
    om = float(eng.overall_materiality) if eng and eng.overall_materiality else 0
    pm = float(eng.performance_materiality) if eng and eng.performance_materiality else 0
    return {"entries": [_s(e) for e in entries],
            "opinion_engine": _opinion_engine(entries, om, pm),
            "materiality": {"om": om, "pm": pm}}

@router.post("/{engagement_id}", status_code=201)
async def add_suam_entry(engagement_id: str, data: SUAMCreate, db: AsyncSession=Depends(get_db)):
    count_result = await db.execute(select(SUAM).where(SUAM.engagement_id==engagement_id))
    count = len(count_result.scalars().all())
    # Get materiality
    eng_result = await db.execute(select(Engagement).where(Engagement.id==engagement_id))
    eng = eng_result.scalar_one_or_none()
    om = float(eng.overall_materiality) if eng and eng.overall_materiality else 999999
    pm = float(eng.performance_materiality) if eng and eng.performance_materiality else 999999
    entry = SUAM(id=uuid.uuid4(), engagement_id=engagement_id,
        suam_ref=f"MS-{str(count+1).zfill(3)}", fs_area=data.fs_area,
        direction=MisstatementDirection(data.direction), amount_crore=data.amount_crore,
        is_corrected=data.is_corrected, is_qualitative=data.is_qualitative,
        exception_id=data.exception_id, notes=data.notes,
        exceeds_pm=data.amount_crore > pm, exceeds_om=data.amount_crore > om)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return _s(entry)

@router.patch("/{engagement_id}/{suam_id}")
async def update_suam_entry(engagement_id: str, suam_id: str, data: SUAMUpdate, db: AsyncSession=Depends(get_db)):
    result = await db.execute(select(SUAM).where(SUAM.engagement_id==engagement_id, SUAM.id==suam_id))
    entry = result.scalar_one_or_none()
    if not entry: raise HTTPException(404, "SUAM entry not found")
    d = data.dict(exclude_none=True)
    for f in ["is_corrected","correction_amount","is_qualitative","has_waiver","waiver_letter","notes"]:
        if f in d: setattr(entry, f, d[f])
    if "has_waiver" in d and d["has_waiver"]: entry.waiver_date = datetime.utcnow()
    entry.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(entry)
    return _s(entry)
