from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
import logging
from app.models.audit_log import get_all_cases, override_case

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_DECISIONS = {"SAFE", "REVIEW", "REJECT"}


class OverrideRequest(BaseModel):
    task_id: str
    new_decision: str
    reason: str

    @field_validator("new_decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in VALID_DECISIONS:
            raise ValueError(f"decision must be one of: {', '.join(VALID_DECISIONS)}")
        return upper

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 100:
            raise ValueError("task_id must be a non-empty string under 100 characters")
        return v

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("reason cannot be empty")
        return v[:500]  # Truncate to prevent oversized logs


@router.get("/history")
async def get_audit_history():
    """Returns the immutable case log (most recent 200 cases) for the underwriter dashboard."""
    try:
        cases = get_all_cases(limit=200)
        return {"cases": cases, "total": len(cases)}
    except Exception as e:
        logger.error(f"Audit history fetch failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve audit history.")


@router.post("/override")
async def submit_officer_override(req: OverrideRequest):
    """
    Allows a human officer to override the AI decision.
    The corrected label is stored for Active Learning / model retraining.
    """
    try:
        updated = override_case(req.task_id, req.new_decision, req.reason)
        if not updated:
            raise HTTPException(
                status_code=404,
                detail=f"Task ID '{req.task_id}' not found in audit log. Cannot override."
            )
        logger.info(f"Officer override: task={req.task_id} → {req.new_decision}")
        return {
            "status": "success",
            "message": f"Case {req.task_id[:8]}... overridden to {req.new_decision}. Queued for model retraining."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Override failed: {e}")
        raise HTTPException(status_code=500, detail="Override failed. Please try again.")
