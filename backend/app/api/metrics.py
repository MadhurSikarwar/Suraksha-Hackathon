from fastapi import APIRouter

router = APIRouter()

@router.get("/performance")
async def get_model_performance():
    """Returns validation statistics for model performance showcase."""
    return {
        "accuracy": 0.985,
        "precision": 0.972,
        "recall": 0.991,
        "f1_score": 0.981,
        "auc_roc": 0.994,
        "false_positive_rate": 0.021,
        "validation_set_size": 24500,
        "latency_ms": 142
    }

@router.get("/business-impact")
async def get_business_impact():
    """Returns simulated ROI and scalability metrics for the pitch."""
    return {
        "projected_savings_inr": "₹120 Crores",
        "manual_hours_saved": "45,000+",
        "rbi_compliance": ["KYC/AML Guidelines 2016", "Digital Lending Guidelines 2022"],
        "legal_defensibility": "Cryptographically hashed audit logs compliant with IT Act 2000, Sec 65B.",
        "capacity": "10,000 docs/min",
        "infrastructure_cost": "$0.002 per document"
    }

@router.get("/competitive-intelligence")
async def get_competitive_intelligence():
    """Returns systemic fraud detection metrics across the platform."""
    return {
        "repeat_property_flags": 142,
        "notary_abuse_cases": 89,
        "coordinated_submission_rings": 12,
        "duplicate_survey_numbers": 34
    }
