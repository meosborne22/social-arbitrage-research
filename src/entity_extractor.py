import os
import re
from collections import defaultdict
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

KNOWN_ENTITIES = [
    "Tarte", "Medicube", "Plix", "BOLDfit",
    "Nestlé", "Takis", "Frijj", "Meesho",
]

CONTEXT_TERMS = [
    "skincare", "makeup", "serum", "mascara", "cream",
    "shampoo", "straps", "gadgets", "chocolate", "crisps",
    "milkshake", "kitchen", "beauty", "fashion", "cleaning",
    "bundle", "holiday",
]

NEGATIVE_PATTERNS = [
    r"\bboycott\b", r"\bavoid\b", r"\bavoiding\b",
    r"\bhate\b", r"\bhated\b", r"\bregret\b",
    r"\bregretted\b", r"\bstopped\b", r"\bstop using\b",
    r"\bstop buying\b", r"\bstopped buying\b",
    r"\bnever buy\b", r"\bdon't buy\b",
    r"\bdo not buy\b", r"\bnot buying\b",
    r"\bscam\b", r"\bproblem\b", r"\bproblems\b",
]

ADOPTION_PATTERNS = [
    r"\bbuy\b", r"\bbuying\b", r"\bbought\b",
    r"\bpurchase\b", r"\bpurchased\b",
    r"\bmade me buy\b", r"\beveryone is buying\b",
    r"\bsold out\b", r"\bselling out\b",
    r"\bswitched to\b", r"\bswitching to\b",
    r"\blove\b", r"\bfavorite\b", r"\bfavourite\b",
    r"\bobsessed\b", r"\bmust[- ]buy\b",
    r"\bmust[- ]have\b", r"\bworth it\b",
    r"\brecommend\b", r"\brecommended\b",
    r"\busing\b", r"\busers\b", r"\bcustomers\b",
]

INTEREST_PATTERNS = [
    r"\breview\b", r"\bunboxing\b", r"\btry\b",
    r"\btrying\b", r"\btesting\b", r"\btest\b",
    r"\bfinds\b", r"\bfind\b", r"\bdiscover\b",
    r"\bdiscovered\b", r"\bviral\b", r"\btrending\b",
    r"\bnew product\b", r"\bproducts\b",
]

def matches_any(text, patterns):
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)

def classify_direction(title):
    text = (title or "").lower()
    if matches_any(text, NEGATIVE_PATTERNS):
        return "negative"
    if matches_any(text, ADOPTION_PATTERNS):
        return "adoption"
    if matches_any(text, INTEREST_PATTERNS):
        return "interest"
    return "neutral"

def classify_evidence_type(title, direction):
    text = (title or "").lower()

    if direction == "negative":
        return "negative_behavior"

    if direction == "mixed":
        return "mixed_behavior"

    if matches_any(text, [
        r"\bbought\b", r"\bbuying\b", r"\bpurchased\b",
        r"\bpurchase\b", r"\bmade me buy\b",
        r"\beveryone is buying\b", r"\bsold out\b",
        r"\bselling out\b", r"\bswitched to\b",
        r"\bswitching to\b",
    ]):
        return "purchase_signal"

    if matches_any(text, [
        r"\brecommend\b", r"\brecommended\b", r"\blove\b",
        r"\bfavorite\b", r"\bfavourite\b", r"\bobsessed\b",
        r"\bmust[- ]buy\b", r"\bmust[- ]have\b",
        r"\bworth it\b", r"\busing\b",
        r"\bcustomers\b", r"\busers\b",
    ]):
        return "adoption_signal"

    if direction == "interest":
        return "discovery_signal"

    return "mention"

def extract_entities():
    response = (
        supabase.table("observations")
        .select("id, text_evidence, value, raw_metadata")
        .eq("source", "youtube")
        .order("observed_at", desc=True)
        .limit(1000)
        .execute()
    )

    rows = response.data or []
    entity_videos = defaultdict(set)
    entity_counts = defaultdict(lambda: {
        "adoption": 0, "negative": 0, "interest": 0,
        "mixed": 0, "neutral": 0
    })
    entity_context = defaultdict(set)
    entity_examples = defaultdict(list)
    updated = 0

    for row in rows:
        observation_id = row.get("id")
        title = row.get("text_evidence") or ""
        raw_metadata = row.get("raw_metadata") or {}
        video_id = raw_metadata.get("video_id")

        direction = classify_direction(title)
        evidence_type = classify_evidence_type(title, direction)

        if observation_id is not None:
            try:
                (
                    supabase.table("observations")
                    .update({
                        "behavior_signal": direction,
                        "evidence_type": evidence_type,
                    })
                    .eq("id", observation_id)
                    .execute()
                )
                updated += 1
            except Exception as error:
                print(f"Could not update observation {observation_id}: {error}")

        text_lower = title.lower()

        for entity in KNOWN_ENTITIES:
            if entity.lower() not in text_lower:
                continue

            if video_id:
                entity_videos[entity].add(video_id)

            entity_counts[entity][direction] += 1

            for context in CONTEXT_TERMS:
                if context in text_lower:
                    entity_context[entity].add(context)

            if len(entity_examples[entity]) < 5:
                entity_examples[entity].append({
                    "direction": direction,
                    "evidence_type": evidence_type,
                    "views": row.get("value", 0),
                    "title": title,
                })

    print(f"Persisted behavior signals for {updated} observations.")
    print("\nDetected entities:")

    for entity in KNOWN_ENTITIES:
        if not entity_videos[entity]:
            continue

        counts = entity_counts[entity]

        print(
            f"\n{entity} | unique_videos={len(entity_videos[entity])} | "
            f"adoption={counts['adoption']} | negative={counts['negative']} | "
            f"interest={counts['interest']} | mixed={counts['mixed']} | "
            f"neutral={counts['neutral']} | "
            f"context={','.join(sorted(entity_context[entity]))}"
        )

        for example in entity_examples[entity]:
            print(
                f"  - {example['direction']} | {example['evidence_type']} | "
                f"{example['views']} views | {example['title']}"
            )

    print("\nEntity extraction complete. No stock/company mapping was forced.")

if __name__ == "__main__":
    extract_entities()
