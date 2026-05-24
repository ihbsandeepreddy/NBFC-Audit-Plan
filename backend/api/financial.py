"""Complete Financial Analytics API"""
import os, uuid, asyncio, logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response, FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import get_db
from core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)
UPLOAD_DIR = settings.UPLOAD_DIR
os.makedirs(UPLOAD_DIR, exist_ok=True)


class FinancialDataInput(BaseModel):
    period_label: str
    data: dict  # attribute_code -> value


@router.get("/{engagement_id}/template")
async def download_template(engagement_id: str):
    """Download Excel template with all required financial attributes"""
    from analytics.financial_ratios import generate_excel_template
    content = generate_excel_template()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=NBFC_Financial_Template.xlsx"}
    )


@router.post("/{engagement_id}/upload")
async def upload_financial_data(
    engagement_id: str, period_label: str = "Current",
    file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    """Upload financial data file and compute ratios"""
    content = await file.read()
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "csv"
    
    file_path = os.path.join(UPLOAD_DIR, f"fin_{uuid.uuid4()}.{ext}")
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        import polars as pl
        if ext == "csv":
            df = pl.read_csv(file_path)
        else:
            df = pl.read_excel(file_path)

        from analytics.financial_ratios import FINANCIAL_ATTRIBUTES, compute_ratios
        
        # Build data dict from uploaded file
        # Expected: column "Attribute Code" and columns for periods
        financial_data = {}
        if "Attribute Code" in df.columns or "attribute_code" in df.columns:
            code_col = "Attribute Code" if "Attribute Code" in df.columns else "attribute_code"
            val_col = df.columns[2] if len(df.columns) > 2 else df.columns[1]
            for row in df.to_dicts():
                code = row.get(code_col, "")
                val = row.get(val_col)
                if code and val is not None:
                    try:
                        financial_data[code] = float(val)
                    except (ValueError, TypeError):
                        pass
        else:
            # Try to read as simple key-value
            for col in df.columns:
                if col.lower() in FINANCIAL_ATTRIBUTES:
                    financial_data[col.lower()] = float(df[col][0]) if len(df) > 0 else 0

        ratios = compute_ratios(financial_data, period_label)
        os.remove(file_path)
        return {"period": period_label, "ratios": ratios, "data_used": financial_data}

    except Exception as e:
        logger.error(f"Financial upload error: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(400, f"Error processing file: {str(e)}")


@router.post("/{engagement_id}/compute")
async def compute_financial_ratios(engagement_id: str, data: FinancialDataInput):
    """Compute ratios from JSON input (no file upload)"""
    from analytics.financial_ratios import compute_ratios
    return compute_ratios(data.data, data.period_label)


@router.post("/{engagement_id}/variance")
async def compute_variance(engagement_id: str, current: FinancialDataInput, prior: FinancialDataInput):
    """Compute period-over-period variance"""
    from analytics.financial_ratios import compute_ratios, compute_variance
    current_ratios = compute_ratios(current.data, current.period_label)
    prior_ratios = compute_ratios(prior.data, prior.period_label)
    variance = compute_variance(current_ratios, prior_ratios)
    return {"current": current_ratios, "prior": prior_ratios, "variance": variance}
