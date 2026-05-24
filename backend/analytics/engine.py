"""
Analytics Engine - Dispatcher for all DA (Data Analytics) functions
Handles execution of DA-001 to DA-050 with Polars + DuckDB
"""

import logging
import asyncio
import polars as pl
import duckdb
from typing import Optional, Callable, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """Main dispatcher for analytics functions"""

    def __init__(self):
        self.da_functions: Dict[str, Callable] = {}
        self._register_functions()

    def _register_functions(self):
        """Register all DA functions"""
        # DA-001: LMS-GL Reconciliation
        from . import da
        self.da_functions = {
            "DA-001": da.da_001_lms_gl_recon,
            "DA-002": da.da_002_los_lms_recon,
            "DA-003": da.da_003_duplicate_loans,
            "DA-004": da.da_004_rate_override,
            "DA-005": da.da_005_segment_variance,
            # ... Add all 50 DAs
        }

    async def run_analytics(
        self,
        da_ref: str,
        loan_tape: pl.LazyFrame,
        repayment_history: Optional[pl.LazyFrame] = None,
        credit_policy: Optional[dict] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a specific DA function

        Args:
            da_ref: DA reference (e.g., "DA-001")
            loan_tape: Polars LazyFrame with loan data
            repayment_history: Optional repayment history data
            credit_policy: Optional credit policy parameters
            **kwargs: Additional parameters for specific DAs

        Returns:
            Dictionary with results, exceptions, summary stats
        """
        if da_ref not in self.da_functions:
            raise ValueError(f"Unknown DA reference: {da_ref}")

        logger.info(f"Starting {da_ref} analytics...")
        start_time = datetime.utcnow()

        try:
            da_function = self.da_functions[da_ref]

            # Run DA function in thread pool to avoid blocking
            result = await asyncio.to_thread(
                da_function,
                loan_tape=loan_tape,
                repayment_history=repayment_history,
                credit_policy=credit_policy,
                **kwargs
            )

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"{da_ref} completed in {duration:.2f}s")

            return {
                "da_ref": da_ref,
                "status": "completed",
                "duration_seconds": duration,
                "results": result,
                "completed_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error in {da_ref}: {str(e)}")
            return {
                "da_ref": da_ref,
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.utcnow().isoformat()
            }

    def get_da_metadata(self, da_ref: str) -> Dict[str, Any]:
        """Get metadata for a DA function"""
        metadata = {
            "DA-001": {
                "name": "LMS-GL Reconciliation",
                "description": "Reconcile LMS outstanding by product to GL",
                "inputs": ["loan_tape", "gl_data"],
                "outputs": ["reconciliation_diff", "dup_loans", "null_fields"],
                "cap_seq": "R.01",
                "risk_theme": 1
            },
            "DA-002": {
                "name": "LOS-LMS Reconciliation",
                "description": "Reconcile LOS sanctions to LMS disbursements",
                "inputs": ["los_sanctions", "lms_disbursements"],
                "outputs": ["unmatched_los", "ghost_disbursements"],
                "cap_seq": "S.01",
                "risk_theme": 13
            },
            # ... metadata for all 50 DAs
        }
        return metadata.get(da_ref, {})


# Global analytics engine
engine = AnalyticsEngine()
