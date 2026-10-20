#!/usr/bin/env python3
"""Create the auditable Week 8 CFB rebuild decision registry.

This file summarizes evidence only. It may identify the lead rebuild/foundation
candidate, but it can never authorize canonical promotion by itself.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_incremental(path: Path) -> tuple[dict[str, Any], bool]:
    """Load optional incremental evidence without making workflow ordering fatal.

    The foundation-feature workflow and decision workflow can be triggered by
    separate commits. If the incremental evidence has not landed yet, record a
    pending research state. A later commit of that evidence re-triggers this
    registry and replaces the pending state with the full evaluation.
    """
    if path.exists():
        return load(path), True
    return {
        "validation": {
            "foldCount": 0,
            "minimumRequiredFolds": 3,
            "games": 0,
            "evidenceStatus": "PENDING_INCREMENTAL_EVIDENCE",
            "challengerEligibleFamilies": [],
            "families": {},
        }
    }, False


def build(
    foundation_shadow_path: Path,
    foundation_validation_path: Path,
    rich_path: Path,
    multi_path: Path,
    incremental_path: Path,
    ref_path: Path,
) -> dict[str, Any]:
    foundation_shadow = load(foundation_shadow_path)
    foundation_validation = load(foundation_validation_path)
    rich = load(rich_path)
    multi = load(multi_path)
    incremental, incremental_available = load_incremental(incremental_path)
    ref = load(ref_path)

    locked = foundation_validation["lockedDevelopmentCandidate"]
    multi_wf = multi["walkForward2026"]
    inc = incremental["validation"]
    ref_model = ref["overall"]["model"]

    foundation_ready = (
        locked.get("status") == "FOUNDATION_CANDIDATE_READY"
        and foundation_shadow.get("role") == "VALIDATED_FOUNDATION_PROSPECTIVE_SHADOW"
        and foundation_shadow.get("canonicalInfluence") is False
        and foundation_shadow.get("canonicalPromotionAuthorized") is False
        and foundation_shadow.get("lockedParameters") == locked.get("params")
        and all(g.get("status") == "FOUNDATION_SHADOW_READY" for g in foundation_shadow.get("games", []))
    )
    rich_rejected = (
        rich["validation"].get("comparisonGatePass") is False
        and multi_wf.get("evidenceStatus") == "RICH_REJECTED"
        and multi_wf.get("prospectiveShadowGatePass") is False
    )
    incremental_not_promoted = (
        inc.get("challengerEligibleFamilies") == []
        and inc.get("evidenceStatus") in {
            "INSUFFICIENT_FOLDS",
            "NO_INCREMENTAL_FAMILY_ELIGIBLE",
            "PENDING_INCREMENTAL_EVIDENCE",
        }
    )

    lead = foundation_shadow["modelId"] if foundation_ready and rich_rejected else "NONE"
    status = "VALIDATED_FOUNDATION_CANDIDATE_IDENTIFIED" if lead != "NONE" else "REVIEW_REQUIRED"

    if lead == "NONE":
        reason = "Evidence is not yet sufficient to identify a lead rebuild candidate."
    elif incremental_available:
        reason = (
            "The foundation parameters were selected using 2024 walk-forward development, then evaluated unchanged on an untouched 2025 holdout and pre-Week8 2026 confirmation set. The full rich bundle is rejected, and no advanced feature family currently has sufficient incremental evidence over this stronger foundation."
        )
    else:
        reason = (
            "The foundation parameters were selected using 2024 walk-forward development, then evaluated unchanged on an untouched 2025 holdout and pre-Week8 2026 confirmation set. The full rich bundle is rejected. Incremental feature-family evidence is still pending and cannot influence the lead or canonical model until it arrives and passes its own gate."
        )

    return {
        "schemaVersion": 2,
        "league": "cfb",
        "season": 2026,
        "week": 8,
        "role": "REBUILD_DECISION_REGISTRY",
        "status": status,
        "canonicalInfluence": False,
        "canonicalPromotionAuthorized": False,
        "leadRebuildCandidate": lead,
        "leadCandidateTier": "VALIDATED_FOUNDATION_PROSPECTIVE_SHADOW" if lead != "NONE" else "NONE",
        "leadCandidateReason": reason,
        "evidence": {
            "establishedWeek7CanonicalReference": {
                "games": ref["overall"]["games"],
                "marginMae": ref_model["marginMae"],
                "totalMae": ref_model["totalMae"],
                "suAccuracyPct": ref_model["suAccuracyPct"],
                "descriptiveOnly": True,
            },
            "validatedFoundation": {
                "modelId": foundation_shadow["modelId"],
                "params": locked["params"],
                "development2024": locked["development2024"]["aggregate"],
                "holdout2025": locked["holdout2025"]["aggregate"],
                "confirmation2026PreWeek8": locked["confirmation2026PreWeek8"]["aggregate"],
                "structuralHomeMarginAdvantage": foundation_shadow["structuralHomeMarginAdvantage"],
                "week8ProjectionCount": len(foundation_shadow.get("games", [])),
                "ready": foundation_ready,
            },
            "richBundle": {
                "modelId": rich["modelId"],
                "initialComparisonGatePass": rich["validation"]["comparisonGatePass"],
                "multiSeasonFolds": len(multi_wf["folds"]),
                "multiSeasonGames": multi_wf["aggregate"]["games"],
                "richMinusSimpleMarginMae": multi_wf["aggregate"]["richMinusSimpleMarginMae"],
                "richMinusSimpleTotalMae": multi_wf["aggregate"]["richMinusSimpleTotalMae"],
                "evidenceStatus": multi_wf["evidenceStatus"],
                "rejected": rich_rejected,
            },
            "incrementalFeatureFamiliesAgainstFoundation": {
                "sourceAvailable": incremental_available,
                "folds": inc["foldCount"],
                "minimumRequiredFolds": inc.get("minimumRequiredFolds", 3),
                "games": inc["games"],
                "evidenceStatus": inc.get("evidenceStatus"),
                "eligibleFamilies": inc.get("challengerEligibleFamilies", []),
                "notPromoted": incremental_not_promoted,
                "familyDeltas": {
                    name: {
                        "marginMaeDeltaVsFoundation": row["marginMaeDeltaVsSimple"],
                        "totalMaeDeltaVsFoundation": row["totalMaeDeltaVsSimple"],
                    }
                    for name, row in inc.get("families", {}).items()
                },
            },
        },
        "week8Policy": {
            "useLeadCandidateAsCanonical": False,
            "publishLeadCandidateAsEstablished09J": False,
            "allowMarketOrExternalBenchmarkInfluence": False,
            "allowUnvalidatedManualAdjustments": False,
            "supersedeOldTemporaryShadowForResearchPriority": True,
            "supersedeEarlierFamilyEligibilityAgainstWeakerBase": True,
            "nextStep": "Freeze the validated foundation prospectively for Week 8 research, continue late factual QB/personnel/weather/referee/market capture, and require explicit promotion review before any canonical replacement.",
            "promotionRequirement": "Prospective frozen-week evidence plus explicit review remains required. Historical/holdout success alone does not silently change canonical status.",
        },
        "sources": {
            "foundationShadow": str(foundation_shadow_path),
            "foundationValidation": str(foundation_validation_path),
            "richShadow": str(rich_path),
            "multiSeasonWalkForward": str(multi_path),
            "incrementalFeatureValidation": str(incremental_path),
            "week7Reference": str(ref_path),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--foundation-shadow", default="cfb/shadow/week-08-tuesday-foundation.json")
    ap.add_argument("--foundation-validation", default="cfb/validation/week-08-simple-foundation-validation.json")
    ap.add_argument("--rich", default="cfb/shadow/week-08-tuesday-rich.json")
    ap.add_argument("--multiseason", default="cfb/validation/week-08-multiseason-walkforward.json")
    ap.add_argument("--incremental", default="cfb/validation/week-08-foundation-feature-family-validation.json")
    ap.add_argument("--reference", default="cfb/validation/week-07-canonical-reference.json")
    ap.add_argument("--output", default="cfb/validation/week-08-rebuild-decision.json")
    a = ap.parse_args()
    out = build(
        Path(a.foundation_shadow),
        Path(a.foundation_validation),
        Path(a.rich),
        Path(a.multiseason),
        Path(a.incremental),
        Path(a.reference),
    )
    p = Path(a.output)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": out["status"],
                "leadRebuildCandidate": out["leadRebuildCandidate"],
                "canonicalPromotionAuthorized": out["canonicalPromotionAuthorized"],
                "incrementalEvidenceStatus": out["evidence"]["incrementalFeatureFamiliesAgainstFoundation"]["evidenceStatus"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
