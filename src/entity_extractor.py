import os
import re
from collections import defaultdict
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

KNOWN_ENTITIES = [
    "Tarte",
    "Medicube",
    "Plix",
    "BOLDfit",
    "Nestlé",
    "Takis",
    "Frijj",
    "Meesho",
]

CONTEXT_TERMS = [
    "skincare", "makeup", "serum", "mascara", "cream", "shampoo",
    "straps", "gadgets", "chocolate", "crisps", "milkshake",
    "kitchen", "beauty", "fashion", "cleaning", "bundle", "holiday",
]

# These terms indicate rejection, avoidance, dissatisfaction, or a boycott.
NEGATIVE_PATTERNS = [
    r"\bboycott\b",
    r"\bavoid\b",
    r"\bavoiding\b",
    r"\bhate\b",
    r"\bhated\b",
    r"\bregret\b",
    r"\bregretted\b",
    r"\bstopped\b",
    r"\bstop using\b",
    r"\bstop buying\b",
    r"\bnever buy\b",
    r"\bdon't buy\b",
    r"\bdo not buy\b",
    r"\bnot buying\b",
    r"\bwon't buy\b",
    r"\bcomplaint\b",
    r"\bcomplaints\b",
    r"\bproblem\b",
    r"\bproblems\b",
    r"\bscam\b",
    r"\bdisappointed\b",
    r"\bdisappointing\b",
]

# These terms count only when they describe actual consumer behavior,
# demand, preference, recommendation, or adoption.
POSITIVE_PATTERNS = [
    r"\bbuying\b",
    r"\bbought\b",
    r"\bbuy\b",
    r"\bpurchase\b",
    r"\bpurchased\b",
    r"\blove\b",
    r"\bloved\b",
    r"\bfavorite\b",
    r"\bfavourite\b",
    r"\bobsessed\b",
    r"\bmust[- ]buy\b",
    r"\bmust[- ]have\b",
    r"\bmade me buy\b",
    r"\beveryone is buying\b",
    r"\bselling out\b",
    r"\bsold out\b",
    r"\bpopular\b",
    r"\brecommend\b",
    r"\brecommended\b",
    r"\bworth it\b",
    r"\bswitching to\b",
    r"\bswitched to\b",
    r"\busing\b",
    r"\busers\b",
    r"\bcustomers\b",
]

def matches_any(text, patterns):
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)

def classify_direction(title):
    """
    Direction rules:
      positive = actual buying/adoption/preference/switching/demand evidence
      negative = boycott/rejection/stopping/complaints/avoidance
      neutral  = mention/display/review without behavior evidence
      mixed    = genuinely contains both positive and negative evidence
    """
    text = title.lower()
    negative = matches_any(text, NEGATIVE_PATTERNS)
    positive = matches_any(text, POSITIVE_PATTERNS)

    if positive and negative:
        return "mixed"
    if negative:
        return "negative"
    if positive:
        return "positive"
    return "neutral"

def extract_entities():
    response = (
        supabase.table("observations")
        .select("text_evidence,value,raw_metadata")
        .eq("source", "youtube")
        .order("observed_at", desc=True)
        .limit(1000)
        .execute()
    )

    # Entity -> video_id -> evidence record.
    entity_videos = defaultdict(dict)

    for row in response.data or []:
        title = row.get("text_evidence") or ""
        metadata = row.get("raw_metadata") or {}
        video_id = metadata.get("video_id")

        if not video_id:
            match = re.search(r"v=([^&\s]+)", metadata.get("video_url", ""))
            video_id = match.group(1) if match else None

        if not video_id:
            continue

        lower_title = title.lower()

        for entity in KNOWN_ENTITIES:
            if entity.lower() not in lower_title:
                continue

            context = [
                term for term in CONTEXT_TERMS
                if term in lower_title
            ]

            entity_videos[entity].setdefault(
                video_id,
                {
                    "title": title,
                    "views": row.get("value") or 0,
                    "direction": classify_direction(title),
                    "context": context,
                },
            )

    print("Detected entities:")

    for entity in KNOWN_ENTITIES:
        videos = entity_videos.get(entity, {})
        if not videos:
            continue

        positive = sum(1 for item in videos.values() if item["direction"] == "positive")
        negative = sum(1 for item in videos.values() if item["direction"] == "negative")
        mixed = sum(1 for item in videos.values() if item["direction"] == "mixed")
        neutral = sum(1 for item in videos.values() if item["direction"] == "neutral")

        contexts = sorted({
            term
            for item in videos.values()
            for term in item["context"]
        })

        print(
            f"- {entity} | unique_videos={len(videos)} | "
            f"positive={positive} | negative={negative} | "
            f"mixed={mixed} | neutral={neutral} | "
            f"context={', '.join(contexts) if contexts else 'none'}"
        )

        for item in list(videos.values())[:10]:
            print(
                f"    {item['direction']} | {item['views']:,} views | "
                f"{item['title']}"
            )

    print("Entity extraction complete. No stock/company mapping was forced.")

if __name__ == "__main__":
    extract_entities()
