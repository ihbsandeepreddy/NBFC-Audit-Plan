"""Complete Credit Policy API"""
import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import get_db
from models.credit_policy import CreditPolicy

router = APIRouter()

class PolicyCreate(BaseModel):
    product_code: str
    product_name: str
    min_age: int = 18
    max_age: int = 70
    max_ticket_size: float
    min_ticket_size: Optional[float] = None
    rate_floor: float
    rate_ceiling: float
    min_bureau_score: int = 650
    max_foir: float = 50.0
    max_ltv: float = 80.0
    max_tenure_months: int = 360
    min_tenure_months: Optional[int] = None
    collateral_required: Optional[str] = None
    mandatory_documents: Optional[List[str]] = None
    sanction_authority_levels: Optional[dict] = None

def _s(p: CreditPolicy) -> dict:
    return {"id": str(p.id), "engagement_id": str(p.engagement_id), "product_code": p.product_code,
            "product_name": p.product_name, "min_age": p.min_age, "max_age": p.max_age,
            "max_ticket_size": float(p.max_ticket_size), "min_ticket_size": float(p.min_ticket_size) if p.min_ticket_size else None,
            "rate_floor": float(p.rate_floor), "rate_ceiling": float(p.rate_ceiling),
            "min_bureau_score": p.min_bureau_score, "max_foir": float(p.max_foir), "max_ltv": float(p.max_ltv),
            "max_tenure_months": p.max_tenure_months, "min_tenure_months": p.min_tenure_months,
            "collateral_required": p.collateral_required, "mandatory_documents": p.mandatory_documents,
            "sanction_authority_levels": p.sanction_authority_levels}

@router.get("/{engagement_id}")
async def list_policies(engagement_id: str, db: AsyncSession=Depends(get_db)):
    result = await db.execute(select(CreditPolicy).where(CreditPolicy.engagement_id==engagement_id))
    return [_s(p) for p in result.scalars().all()]

@router.post("/{engagement_id}", status_code=201)
async def create_policy(engagement_id: str, data: PolicyCreate, db: AsyncSession=Depends(get_db)):
    # Check for existing policy for this product
    result = await db.execute(select(CreditPolicy).where(
        CreditPolicy.engagement_id==engagement_id, CreditPolicy.product_code==data.product_code))
    if result.scalar_one_or_none():
        raise HTTPException(400, f"Policy for {data.product_code} already exists. Use PUT to update.")
    policy = CreditPolicy(id=uuid.uuid4(), engagement_id=engagement_id, **data.dict())
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return _s(policy)

@router.put("/{engagement_id}/{product_code}")
async def update_policy(engagement_id: str, product_code: str, data: PolicyCreate, db: AsyncSession=Depends(get_db)):
    result = await db.execute(select(CreditPolicy).where(
        CreditPolicy.engagement_id==engagement_id, CreditPolicy.product_code==product_code))
    policy = result.scalar_one_or_none()
    if not policy: raise HTTPException(404, "Policy not found")
    for f, v in data.dict().items():
        if v is not None: setattr(policy, f, v)
    policy.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(policy)
    return _s(policy)

@router.delete("/{engagement_id}/{product_code}", status_code=204)
async def delete_policy(engagement_id: str, product_code: str, db: AsyncSession=Depends(get_db)):
    result = await db.execute(select(CreditPolicy).where(
        CreditPolicy.engagement_id==engagement_id, CreditPolicy.product_code==product_code))
    policy = result.scalar_one_or_none()
    if not policy: raise HTTPException(404, "Policy not found")
    await db.delete(policy)
    await db.commit()
