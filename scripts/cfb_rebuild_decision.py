#!/usr/bin/env python3
"""Create an auditable Week 8 CFB rebuild decision record.

This script does not calculate or alter a projection. It summarizes already
frozen validation evidence and identifies the current *lead shadow candidate*.
Canonical promotion always remains an explicit separate action.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build(simple_path: Path, rich_path: Path, wf_path: Path, multi_path: Path, ref_path: Path) -> dict[str, Any]:
    simple = load(simple_path)
    rich = load(rich_path)
    wf = load(wf_path)
    multi = load(multi_path)
    ref = load(ref_path)

    multi_wf = multi["walkForward2026"]
    one_wf = wf["walkForward"]
    ref_model = ref["overall"]["model"]

    rich_rejected = (
        rich["validation"].get("comparisonGatePass") is False
        and one_wf.get("prospectiveShadowGatePass") is False
        and multi_wf.get("evidenceStatus") == "RICH_REJECTED"
        and multi_wf.get("prospectiveShadowGatePass") is False
    )
    simple_safe = (
        simple.get("role") == "SHADOW_CHALLENGER_ONLY"
        and simple.get("canonicalInfluence") is False
        and simple["source"].get("marketDataUsed") is False
        and simple["source"].get("externalRatingsUsed") is False
        and simple["source"].get("postKickoffDataUsed") is False
        and all(g.get("status") == "SHADOW_READY" for g in simple.get("games", []))
    )

    lead = "cfb-rebuild-alpha-shadow-v8h" if simple_safe and rich_rejected else "NONE"
    status = "LEAD_SHADOW_IDENTIFIED" if lead != "NONE" else "REVIEW_REQUIRED"

    return {
        "schemaVersion": 1,
        "league": "cfb",
        "season": 2026,
        "week": 8,
        "role": "REBUILD_DECISION_REGISTRY",
        "status": status,
        "canonicalInfluence": False,
        "canonicalPromotionAuthorized": False,
        "leadShadowCandidate": lead,
        "leadCandidateReason": (
            "Simple market-independent rebuild is the current lead shadow because it passed source/coverage/HFA safety gates, "
            "while the richer box-score bundle failed both the initial comparison gate and the three-fold season-reset walk-forward promotion gate."
            if lead != "NONE" else "Validation evidence is not yet sufficient to name a lead shadow candidate."
        ),
        "evidence": {
            "establishedWeek7CanonicalReference": {
                "games": ref["overall"]["games"],
                "marginMae": ref_model["marginMae"],
                "totalMae": ref_model["totalMae"],
                "suAccuracyPct": ref_model["suAccuracyPct"],
                "descriptiveOnly": True,
            },
            "simpleRebuild": {
                "modelId": simple["modelId"],
                "rawTrainingGames": simple["rawTrainingGames"],
                "eligibleTrainingGames": simple["eligibleTrainingGames"],
                "structuralHomeMarginAdvantage": simple["fit"]["structuralHomeMarginAdvantage"],
                "homeFieldSanityPass": simple["fit"]["homeFieldSanityPass"],
                "homeFieldProvenancePass": simple["fit"]["homeFieldProvenancePass"],
                "oneUnseenFoldMarginMae": one_wf["aggregate"]["simpleMargin"]["mae"],
                "oneUnseenFoldTotalMae": one_wf["aggregate"]["simpleTotal"]["mae"],
            },
            "richRebuild": {
                "modelId": rich["modelId"],
                "initialComparisonGatePass": rich["validation"]["comparisonGatePass"],
                "multiSeasonFolds": len(multi_wf["folds"]),
                "multiSeasonGames": multi_wf["aggregate"]["games"],
                "simpleMarginMae": multi_wf["aggregate"]["simpleMargin"]["mae"],
                "richMarginMae": multi_wf["aggregate"]["richMargin"]["mae"],
                "richMinusSimpleMarginMae": multi_wf["aggregate"]["richMinusSimpleMarginMae"],
                "simpleTotalMae": multi_wf["aggregate"]["simpleTotal"]["mae"],
                "richTotalMae": multi_wf["aggregate"]["richTotal"]["mae"],
                "richMinusSimpleTotalMae": multi_wf["aggregate"]["richMinusSimpleTotalMae"],
                "evidenceStatus": multi_wf["evidenceStatus"],
                "promotionGatePass": multi_wf["prospectiveShadowGatePass"],
            },
        },
        "week8Policy": {
            "useLeadShadowAsCanonical": False,
            "publishLeadShadowAsEstablished09J": False,
            "allowMarketOrExternalBenchmarkInfluence": False,
            "allowUnvalidatedManualAdjustments": False,
            "nextResearchStep": "Test isolated feature families against the lead shadow using the same season-reset, leakage-safe multi-week walk-forward framework.",
            "promotionRequirement": "A future candidate must beat the lead shadow by the predefined out-of-sample gate, then survive prospective frozen-week evidence and explicit promotion review.",
        },
        "sources": {
            "simpleShadow": str(simple_path),
            "richShadow": str(rich_path),
            "currentSeasonWalkForward": str(wf_path),
            "multiSeasonWalkForward": str(multi_path),
            "week7Reference": str(ref_path),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--simple", default="cfb/shadow/week-08-tuesday.json")
    ap.add_argument("--rich", default="cfb/shadow/week-08-tuesday-rich.json")
    ap.add_argument("--walkforward", default="cfb/validation/week-08-rebuild-walkforward.json")
    ap.add_argument("--multiseason", default="cfb/validation/week-08-multiseason-walkforward.json")
    ap.add_argument("--reference", default="cfb/validation/week-07-canonical-reference.json")
    ap.add_argument("--output", default="cfb/validation/week-08-rebuild-decision.json")
    args = ap.parse_args()
    out = build(Path(args.simple), Path(args.rich), Path(args.walkforward), Path(args.multiseason), Path(args.reference))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": out["status"], "leadShadowCandidate": out["leadShadowCandidate"], "canonicalPromotionAuthorized": out["canonicalPromotionAuthorized"]}, indent=2))


if __name__ == "__main__":
    main()
