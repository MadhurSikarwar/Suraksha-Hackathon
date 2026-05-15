from fastapi import APIRouter, HTTPException, Path
import logging
import re

logger = logging.getLogger(__name__)
router = APIRouter()

# Stable seed-based graph so the same entity always produces the same graph
# (prevents flickering on re-renders)
_KNOWN_ENTITIES = {
    "shell corp z": "high",
    "alpha holdings": "high",
    "ramesh kumar": "medium",
    "priya sharma": "low",
    "victim enterprises": "medium",
}

_VALID_ENTITY_TYPES = {"seller", "buyer", "notary", "property"}

_STATIC_NOTARY = {
    "id": "notary_ravi_sharma",
    "name": "Notary: Ravi Sharma",
    "group": 3,
    "val": 15,
    "type": "Notary",
    "risk": "high"
}

_STATIC_PROPERTIES = [
    {"survey": "SY-105", "risk": "high"},
    {"survey": "SY-203", "risk": "medium"},
    {"survey": "SY-407", "risk": "low"},
]

_SHELL_CORPS = [
    {"id": "shell_alpha_holdings", "name": "Alpha Holdings Ltd (Shell)", "risk": "high"},
    {"id": "shell_vertex_realty",  "name": "Vertex Realty Corp (Shell)", "risk": "high"},
]


def _sanitize_name(name: str) -> str:
    """Strip everything except alphanumeric, spaces, hyphens. Max 80 chars."""
    sanitized = re.sub(r"[^\w\s\-]", "", name).strip()
    return sanitized[:80]


def generate_stable_graph(entity_name: str, entity_type: str) -> dict:
    """
    Generates a deterministic fraud network graph.
    Same input always produces the same output (no random - prevents graph
    flickering on re-render and makes demo reproducible).
    """
    nodes = []
    links = []
    added_ids = set()

    name_lower = entity_name.lower()
    risk_level = _KNOWN_ENTITIES.get(name_lower, "medium" if "corp" in name_lower else "low")
    is_high_risk = risk_level == "high"

    # Core entity node
    core_id = f"{entity_type}_{entity_name.replace(' ', '_').lower()}"
    nodes.append({
        "id": core_id,
        "name": entity_name,
        "group": 1,
        "val": 24,
        "type": entity_type.capitalize(),
        "risk": risk_level
    })
    added_ids.add(core_id)

    # Add static properties (2 for low risk, 3 for high risk)
    props_to_add = _STATIC_PROPERTIES if is_high_risk else _STATIC_PROPERTIES[:2]
    for prop in props_to_add:
        prop_id = f"property_{prop['survey']}"
        if prop_id not in added_ids:
            nodes.append({
                "id": prop_id,
                "name": f"Survey {prop['survey']}",
                "group": 2,
                "val": 14,
                "type": "Property",
                "risk": prop["risk"]
            })
            added_ids.add(prop_id)
        links.append({
            "source": core_id,
            "target": prop_id,
            "label": "SOLD" if entity_type == "seller" else "BOUGHT"
        })

        # Notary connects all properties
        if _STATIC_NOTARY["id"] not in added_ids:
            nodes.append(_STATIC_NOTARY.copy())
            added_ids.add(_STATIC_NOTARY["id"])
        links.append({
            "source": prop_id,
            "target": _STATIC_NOTARY["id"],
            "label": "REGISTERED_BY"
        })

    # Shell corps only for high-risk entities
    if is_high_risk:
        for shell in _SHELL_CORPS:
            if shell["id"] not in added_ids:
                nodes.append({
                    "id": shell["id"],
                    "name": shell["name"],
                    "group": 4,
                    "val": 10,
                    "type": "Company",
                    "risk": shell["risk"]
                })
                added_ids.add(shell["id"])
            links.append({"source": shell["id"], "target": core_id, "label": "FUNDS_TO"})

    return {"nodes": nodes, "links": links}


@router.get("/network/{entity_type}/{entity_name}")
async def get_fraud_network(
    entity_type: str = Path(..., description="Type: seller, buyer, notary, or property"),
    entity_name: str = Path(..., description="Entity name to query")
):
    """
    Returns the fraud network graph for a given entity.
    Graph is deterministic — same name always returns same structure.
    """
    # Validate entity_type
    if entity_type.lower() not in _VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity_type '{entity_type}'. Must be one of: {', '.join(_VALID_ENTITY_TYPES)}"
        )

    # Sanitize entity_name to prevent injection / path traversal
    clean_name = _sanitize_name(entity_name)
    if not clean_name:
        raise HTTPException(status_code=400, detail="entity_name cannot be empty after sanitization.")

    try:
        graph = generate_stable_graph(clean_name, entity_type.lower())
        fraud_ring = any(n["risk"] == "high" for n in graph["nodes"])
        return {
            "network": graph,
            "fraud_ring_detected": fraud_ring,
            "entity_queried": clean_name
        }
    except Exception as e:
        logger.error(f"Graph generation failed for {entity_type}/{entity_name}: {e}")
        raise HTTPException(status_code=500, detail="Graph generation failed.")
