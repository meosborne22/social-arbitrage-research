import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

# Known names from the evidence we have already observed.
# This layer identifies entities; it deliberately does NOT force a stock
# mapping when ownership/public-market exposure has not been verified.
KNOWN_ENTITIES = {
    "tarte": {"entity_type": "brand", "canonical_name": "Tarte"},
    "tartecosmetics": {"entity_type": "brand", "canonical_name": "Tarte"},
    "medicube": {"entity_type": "brand", "canonical_name": "Medicube"},
    "plix": {"entity_type": "brand", "canonical_name": "Plix"},
    "boldfit": {"entity_type": "brand", "canonical_name": "BOLDfit"},
    "nestle": {"entity_type": "company_or_brand", "canonical_name": "Nestlé"},
    "takis": {"entity_type": "brand", "canonical_name": "Takis"},
    "frijj": {"entity_type": "brand", "canonical_name": "Frijj"},
    "meesho": {"entity_type": "company_or_brand", "canonical_name": "Meesho"},
}

# Product/category terms worth preserving as context around an entity.
PRODUCT_TERMS = {
    "skincare", "makeup", "serum", "mascara", "cream", "shampoo",
    "straps", "gadgets", "chocolate", "crisps", "milkshake", "kitchen",
    "beauty", "fashion", "cleaning", "bundle", "holiday",
}

NEGATIVE_TERMS = {
    "boycott", "avoid", "hate", "regret", "stopped", "stop", "never",
    "don't buy", "do not buy", "bad", "scam", "problem", "problems",
}

POSITIVE_TERMS = {
    "buying", "bought", "buy", "love", "loves", "favorite", "obsessed",
    "must buy", "must-have", "worth it", "made me buy", "everyone is buying",
    "selling", "viral", "popular", "recommend", "recommendation",
}

def clean_text(text):
    return re.sub(r"\s+", " ", (text or "").lower()).strip()

def video_id_from_observation(observation):
    metadata = observation.get("raw_metadata") or {}
    if metadata.get("video_id"):
        return metadata["video_id"]
    url = observation.get("source_url") or ""
    match = re.search(r"[?&]v=([^&]+)", url)
    return match.group(1) if match else url

def unique_observations(observations):
    seen = {}
    for observation in observations:
        vid = video_id_from_observation(observation)
        if vid not in seen:
            seen[vid] = observation
    return list(seen.values())

def extract_entities(text):
    normalized = clean_text(text)
    found = []

    for alias, info in KNOWN_ENTITIES.items():
        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            found.append(info["canonical_name"])

    return sorted(set(found))

def extract_context(text):
    normalized = clean_text(text)

    products = [
        term for term in PRODUCT_TERMS
        if re.search(rf"\b{re.escape(term)}\b", normalized)
    ]

    positive_hits = [
        term for term in POSITIVE_TERMS
        if term in normalized
    ]

    negative_hits = [
        term for term in NEGATIVE_TERMS
        if term in normalized
    ]

    if negative_hits and not positive_hits:
        direction = "negative"
    elif positive_hits and not negative_hits:
        direction = "positive"
    elif positive_hits and negative_hits:
        direction = "mixed"
    else:
        direction = "neutral"

    return {
        "products_or_categories": sorted(set(products)),
        "positive_signals": sorted(set(positive_hits)),
        "negative_signals": sorted(set(negative_hits)),
        "direction": direction,
    }

def run_entity_extraction():
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)

    response = (
        supabase.table("observations")
        .select(
            "observed_at,text_evidence,source,source_url,value,raw_metadata"
        )
        .eq("source", "youtube")
        .gte("observed_at", cutoff.isoformat())
        .order("observed_at", desc=True)
        .limit(1000)
        .execute()
    )

    observations = unique_observations(response.data or [])

    print(f"Analyzing {len(observations)} unique YouTube videos.")

    entity_evidence = defaultdict(list)

    for observation in observations:
        title = observation.get("text_evidence") or ""
        entities = extract_entities(title)

        if not entities:
            continue

        context = extract_context(title)

        for entity in entities:
            entity_evidence[entity].append({
                "video_id": video_id_from_observation(observation),
                "title": title,
                "views": observation.get("value"),
                "observed_at": observation.get("observed_at"),
                "source_url": observation.get("source_url"),
                "direction": context["direction"],
                "products_or_categories": context["products_or_categories"],
                "positive_signals": context["positive_signals"],
                "negative_signals": context["negative_signals"],
            })

    print("\nDetected entities:")

    for entity, evidence in sorted(
        entity_evidence.items(),
        key=lambda item: (-len(item[1]), item[0])
    ):
        unique_videos = len({x["video_id"] for x in evidence})
        positive = sum(x["direction"] == "positive" for x in evidence)
        negative = sum(x["direction"] == "negative" for x in evidence)
        mixed = sum(x["direction"] == "mixed" for x in evidence)

        categories = Counter()
        for item in evidence:
            categories.update(item["products_or_categories"])

        print(
            f"- {entity} | unique_videos={unique_videos} | "
            f"positive={positive} | negative={negative} | mixed={mixed} | "
            f"context={', '.join(x for x, _ in categories.most_common(5)) or 'none'}"
        )

        # Show the actual evidence so we can audit extraction before
        # connecting entities to companies/stocks.
        for item in evidence[:5]:
            print(
                f"    {item['direction']} | {item['views']} views | "
                f"{item['title']}"
            )

    print(
        "\nEntity extraction complete. "
        "No stock/company mapping was forced."
    )

if __name__ == "__main__":
    run_entity_extraction()
