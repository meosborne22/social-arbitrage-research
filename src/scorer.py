from __future__ import annotations
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

def load_config():
    scoring = json.loads((BASE / "config/scoring.json").read_text())
    return scoring

def score_thesis(evidence: dict, penalties: list[float] | None = None) -> dict:
    cfg = load_config()
    weights = cfg["weights"]

    raw = 0.0
    components = {}
    for name, weight in weights.items():
        value = float(evidence.get(name, 0))
        value = max(0.0, min(10.0, value))
        contribution = value * weight / 10.0
        components[name] = round(contribution, 2)
        raw += contribution

    penalty_total = sum(float(x) for x in (penalties or []))
    final = max(0.0, min(100.0, raw + penalty_total))

    if final >= cfg["thresholds"]["exceptional"]:
        tier = "exceptional"
    elif final >= cfg["thresholds"]["high_conviction"]:
        tier = "high_conviction"
    elif final >= cfg["thresholds"]["developing"]:
        tier = "developing"
    else:
        tier = "research_only"

    return {
        "score": round(final, 2),
        "tier": tier,
        "components": components,
        "penalties": penalty_total
    }

if __name__ == "__main__":
    example = {
        "social_acceleration": 9,
        "cross_platform_confirmation": 9,
        "search_acceleration": 8,
        "purchase_adoption_evidence": 9,
        "brand_switching_behavior": 8,
        "company_exposure": 9,
        "earnings_impact": 8,
        "market_awareness_inverse": 9,
        "valuation_mispricing": 8,
        "catalyst_timing": 8
    }
    print(json.dumps(score_thesis(example, penalties=[-3]), indent=2))
