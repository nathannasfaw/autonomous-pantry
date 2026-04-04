"""
Inventory diff service.

Architecture note (Layer 5 - Optimization):
  Given what we have (InventorySnapshot) and what we need (recipe requirements),
  compute exactly what must be purchased, including any ingredient substitutions
  decided by the meta-reasoning layer.

  Substitutions are recorded on each MissingIngredient so the reasoning trace
  and proposal summary can explain *why* shrimp was chosen instead of salmon.
"""

from typing import Dict, List, Tuple

from app.models.inventory import (
    InventorySnapshot,
    RecipeRequirement,
    MissingIngredient,
)
from app.models.proposal import PurchaseProposal
from app.services import trace_logger
from app.models.common import TraceStep, TraceStatus


def compute_missing(
    snapshot: InventorySnapshot,
    requirements: List[RecipeRequirement],
    pricing: Dict[str, float],
    substitutions: Dict[str, Tuple[str, str]] | None = None,
    proposal: PurchaseProposal | None = None,
) -> List[MissingIngredient]:
    """
    Compare recipe requirements against current inventory.

    Args:
        snapshot:      current pantry state from CV layer
        requirements:  what the recipe needs
        pricing:       estimated price per unit for each ingredient name
        substitutions: optional map of {original: (substitute, reason)}
        proposal:      if provided, trace entries are appended

    Returns:
        List of MissingIngredient items that must be purchased.
    """
    substitutions = substitutions or {}
    missing: List[MissingIngredient] = []

    for req in requirements:
        item = snapshot.inventory.get(req.name)
        available = item.count if item else 0.0

        # Check for low-confidence inventory readings
        if item and item.is_low_confidence and proposal:
            trace_logger.log(
                proposal,
                TraceStep.UNCERTAINTY_DETECTED,
                f"{req.name} inventory confidence is {item.confidence:.0%} — treating as uncertain, adding buffer.",
                TraceStatus.WARNING,
            )
            # Apply a conservative buffer: treat available quantity as 70% of reported
            available = available * 0.7

        needed = max(0.0, req.required_quantity - available)

        if needed <= 0:
            continue

        # Apply substitution if one was decided by meta-reasoning
        ingredient_name = req.name
        substituted_from = None
        substitution_reason = None
        if req.name in substitutions:
            substitute, reason = substitutions[req.name]
            substituted_from = req.name
            ingredient_name = substitute
            substitution_reason = reason
            if proposal:
                trace_logger.log(
                    proposal,
                    TraceStep.CONFLICT_RESOLVED,
                    f"Substituted '{req.name}' → '{substitute}': {reason}",
                    TraceStatus.INFO,
                )

        price = pricing.get(ingredient_name, pricing.get(req.name, 0.0))

        missing.append(
            MissingIngredient(
                name=ingredient_name,
                required_quantity=req.required_quantity,
                available_quantity=available,
                missing_quantity=needed,
                unit=req.unit,
                estimated_price=round(price * needed, 2),
                substituted_from=substituted_from,
                substitution_reason=substitution_reason,
            )
        )

    if proposal:
        trace_logger.log(
            proposal,
            TraceStep.INVENTORY_ASSESSED,
            f"Inventory diff complete. {len(missing)} item(s) need to be purchased.",
            TraceStatus.INFO,
        )

    return missing
