"""
Schema Normalizer - Maps user columns to standard LMS schema
Handles column name variations and data validation
"""

import logging
import polars as pl
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher
import re

logger = logging.getLogger(__name__)


class SchemaNormalizer:
    """Normalize user-provided data to standard LMS schema"""

    # Required 48-field LMS schema (from Data Schema sheet)
    REQUIRED_SCHEMA = {
        # Core loan identification
        "LOAN_ACCOUNT_NO": {"type": "string", "nullable": False, "aliases": ["loan_id", "LAN", "account_number"]},
        "PAN_NUMBER": {"type": "string", "nullable": False, "aliases": ["pan", "borrower_pan"]},
        "AADHAAR_LAST4": {"type": "string", "nullable": True, "aliases": ["aadhaar"]},
        "BORROWER_NAME": {"type": "string", "nullable": True, "aliases": ["customer_name", "name"]},
        "MOBILE_NUMBER": {"type": "string", "nullable": True, "aliases": ["phone", "contact"]},
        "EMAIL": {"type": "string", "nullable": True},
        "BANK_ACCOUNT_NO": {"type": "string", "nullable": True, "aliases": ["bank_account", "account"]},
        "IFSC_CODE": {"type": "string", "nullable": True, "aliases": ["ifsc"]},

        # Loan terms
        "PRODUCT_CODE": {"type": "string", "nullable": False, "aliases": ["product", "product_name"]},
        "DISBURSEMENT_DATE": {"type": "date", "nullable": False, "aliases": ["disbursal_date", "disbursed_date"]},
        "DISBURSEMENT_AMOUNT": {"type": "decimal", "nullable": False, "aliases": ["disbursal_amount", "amount_disbursed"]},
        "MATURITY_DATE": {"type": "date", "nullable": False, "aliases": ["due_date", "loan_maturity"]},
        "OUTSTANDING_PRINCIPAL": {"type": "decimal", "nullable": False, "aliases": ["principal_outstanding", "outstanding_amount"]},
        "INTEREST_RATE": {"type": "decimal", "nullable": False, "aliases": ["roi", "rate", "interest_rate_pa"]},
        "EMI_AMOUNT": {"type": "decimal", "nullable": True, "aliases": ["emi", "monthly_payment"]},
        "TENURE_MONTHS": {"type": "integer", "nullable": False, "aliases": ["tenure", "term_months"]},

        # Classification & Stage
        "DPD": {"type": "integer", "nullable": False, "aliases": ["days_past_due", "dpd_days"]},
        "IND_AS_STAGE": {"type": "integer", "nullable": False, "aliases": ["stage", "ecl_stage"]},
        "ASSET_CLASSIFICATION": {"type": "string", "nullable": True, "aliases": ["classification", "npa_status"]},

        # Security/Collateral
        "COLLATERAL_TYPE": {"type": "string", "nullable": True, "aliases": ["security_type", "collateral"]},
        "COLLATERAL_VALUE": {"type": "decimal", "nullable": True, "aliases": ["security_value", "ltv_value"]},
        "LTV_RATIO": {"type": "decimal", "nullable": True, "aliases": ["ltv"]},

        # Branch & DSA
        "BRANCH_CODE": {"type": "string", "nullable": False, "aliases": ["branch", "branch_id"]},
        "BRANCH_NAME": {"type": "string", "nullable": True},
        "DSA_CODE": {"type": "string", "nullable": True, "aliases": ["dsa", "distributor"]},

        # KYC Fields
        "VKYC_DATE": {"type": "date", "nullable": True, "aliases": ["vkyc", "kyc_date"]},
        "CKYC_ID": {"type": "string", "nullable": True},

        # Bureau & Scoring
        "BUREAU_SCORE": {"type": "integer", "nullable": True, "aliases": ["cibil_score", "credit_score"]},
        "BUREAU_INQUIRY_DATE": {"type": "date", "nullable": True},

        # ECL Provision
        "STAGE_1_ECL": {"type": "decimal", "nullable": True},
        "STAGE_2_ECL": {"type": "decimal", "nullable": True},
        "STAGE_3_ECL": {"type": "decimal", "nullable": True},
        "TOTAL_ECL_PROVISION": {"type": "decimal", "nullable": True},

        # Interest & Income
        "ACCRUED_INTEREST": {"type": "decimal", "nullable": True},
        "INTEREST_SUSPENSE": {"type": "decimal", "nullable": True},
        "LAST_PAYMENT_DATE": {"type": "date", "nullable": True},
        "LAST_PAYMENT_AMOUNT": {"type": "decimal", "nullable": True},

        # Restructuring
        "IS_RESTRUCTURED": {"type": "boolean", "nullable": True},
        "RESTRUCTURE_DATE": {"type": "date", "nullable": True},
        "RESTRUCTURE_AMOUNT": {"type": "decimal", "nullable": True},

        # Sanction
        "SANCTION_DATE": {"type": "date", "nullable": True},
        "SANCTION_AMOUNT": {"type": "decimal", "nullable": True},
        "SANCTION_AUTHORITY": {"type": "string", "nullable": True},

        # Related Party
        "IS_RELATED_PARTY": {"type": "boolean", "nullable": True},
        "RELATED_PARTY_TYPE": {"type": "string", "nullable": True},

        # Repayment Mode
        "REPAYMENT_MODE": {"type": "string", "nullable": True, "aliases": ["payment_mode", "emi_type"]},
    }

    @staticmethod
    def similarity_ratio(a: str, b: str) -> float:
        """Calculate string similarity ratio"""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    @classmethod
    def detect_column_mapping(cls, user_columns: List[str]) -> Dict[str, Optional[str]]:
        """
        Auto-detect mapping from user columns to required schema
        Uses fuzzy matching and alias lookup

        Args:
            user_columns: List of column names from user's file

        Returns:
            Dict mapping standard schema column -> user column name
        """
        mapping = {}
        unmatched = []

        for standard_col in cls.REQUIRED_SCHEMA.keys():
            schema_info = cls.REQUIRED_SCHEMA[standard_col]
            aliases = schema_info.get("aliases", [])
            aliases.append(standard_col)  # Add the standard name itself

            best_match = None
            best_score = 0.7  # Min 70% similarity

            # Try exact match first (case-insensitive)
            for user_col in user_columns:
                if user_col.lower() == standard_col.lower():
                    best_match = user_col
                    break

            # Try alias match
            if not best_match:
                for alias in aliases:
                    for user_col in user_columns:
                        if user_col.lower() == alias.lower():
                            best_match = user_col
                            break
                    if best_match:
                        break

            # Try fuzzy match
            if not best_match:
                for user_col in user_columns:
                    score = cls.similarity_ratio(standard_col, user_col)
                    if score > best_score:
                        best_match = user_col
                        best_score = score

            mapping[standard_col] = best_match
            if not best_match and not schema_info.get("nullable", True):
                unmatched.append(standard_col)

        return {
            "mapping": mapping,
            "unmatched_required": unmatched,
            "confidence": (len([m for m in mapping.values() if m]) / len(mapping)) * 100
        }

    @staticmethod
    def normalize_dataframe(
        df: pl.DataFrame,
        mapping: Dict[str, str],
        schema_info: Dict[str, Dict] = None
    ) -> Tuple[pl.DataFrame, List[str]]:
        """
        Normalize user dataframe to standard schema

        Args:
            df: Input dataframe with user column names
            mapping: Mapping of standard -> user column names
            schema_info: Schema validation info

        Returns:
            Tuple of (normalized_df, validation_errors)
        """
        errors = []

        # Rename columns
        rename_map = {}
        for standard_col, user_col in mapping.items():
            if user_col and user_col in df.columns:
                rename_map[user_col] = standard_col

        df_normalized = df.rename(rename_map)

        # Type conversions
        for standard_col in SchemaNormalizer.REQUIRED_SCHEMA.keys():
            if standard_col not in df_normalized.columns:
                continue

            col_type = SchemaNormalizer.REQUIRED_SCHEMA[standard_col]["type"]

            try:
                if col_type == "date":
                    df_normalized = df_normalized.with_columns(
                        pl.col(standard_col).str.strptime(pl.Date, "%Y-%m-%d", strict=False)
                    )
                elif col_type == "decimal":
                    df_normalized = df_normalized.with_columns(
                        pl.col(standard_col).cast(pl.Float64)
                    )
                elif col_type == "integer":
                    df_normalized = df_normalized.with_columns(
                        pl.col(standard_col).cast(pl.Int64)
                    )
                elif col_type == "boolean":
                    df_normalized = df_normalized.with_columns(
                        pl.col(standard_col).cast(pl.Boolean)
                    )
            except Exception as e:
                errors.append(f"Type conversion error in {standard_col}: {str(e)}")

        return df_normalized, errors

    @staticmethod
    def validate_schema(df: pl.DataFrame) -> Dict[str, List[str]]:
        """
        Validate normalized dataframe against schema rules

        Returns:
            Dict of validation errors by column
        """
        errors = {}

        # Check mandatory fields exist
        for standard_col, col_info in SchemaNormalizer.REQUIRED_SCHEMA.items():
            if col_info.get("nullable", True) is False:
                if standard_col not in df.columns:
                    if standard_col not in errors:
                        errors[standard_col] = []
                    errors[standard_col].append(f"Required field missing")

        # Check specific validations
        if "LOAN_ACCOUNT_NO" in df.columns:
            dup_count = df.group_by("LOAN_ACCOUNT_NO").count().filter(pl.col("count") > 1).height
            if dup_count > 0:
                errors["LOAN_ACCOUNT_NO"] = [f"{dup_count} duplicate LANs found"]

        if "INTEREST_RATE" in df.columns:
            outliers = df.filter(
                (pl.col("INTEREST_RATE") < 0) | (pl.col("INTEREST_RATE") > 60)
            ).height
            if outliers > 0:
                errors["INTEREST_RATE"] = [f"{outliers} rates outside 0-60% range"]

        return errors
