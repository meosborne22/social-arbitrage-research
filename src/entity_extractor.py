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

# Evidence hierarchy:
# negative  = rejection, avoidance, boycott, dissatisfaction
# adoption  = actual buying, use, switching, recommendation, demand
# interest  = discovery, review, unboxing, product curiosity
# neutral   = simple mention, announcement, availability, or display

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

ADOPTION_PATTERNS = [
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
    r"\brecommend\b",
    r"\brecommended\b",
    r"\bworth it\b",
    r"\bswitching to\b",
    r"\bswitched to\b",
    r"\busing\b",
    r"\busers\b",
    r"\bcustomers\b",
]

INTEREST_PATTERNS = [
    r"\breview\b",
    r"\breviews\b",
    r"\bunboxing\b",
    r"\bunbox\b",
    r"\bfinds?\b",
    r"\bhaul\b",
    r"\btry(?:ing)?\b",
    r"\btested\b",
    r"\btesting\b",
    r"\bfirst look\b",
    r"\blook at\b",
    r"\bnew product\b",
    r"\bnew products\b",
    r"\bproduct discovery\b",
    r"\bviral product\b",
    r"\bviral products\b",
    r"\btrending product\b",
    r"\btrending products\b",
    r"\bmust see\b",
]

def matches_any(text, patterns):
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)

def classify_direction(title):
    """
    Return one evidence state:
      negative = rejection/avoidance/dissatisfaction
      adoption = actual buying/use/switching/preference/demand
      interest = discovery/review/unboxing/product curiosity
      neutral  = simple mention/announcement/display

    Negative takes priority over adoption. Adoption takes priority over
    interest because direct behavior is stronger evidence than curiosity.
    """
    text = title.lower()

    negative = matches_any(text, NEGATIVE_PATTERNS)
    adoption = matches_any(text, ADOPTION_PATTERNS)
    interest = matches_any(text, INTEREST_PATTERNS)

    if negative and (adoption or interest):
        return "mixed"
    if negative:
        return "negative"
    if adoption:
        return "adoption"
    if interest:
        return "interest"
    return "neutral"

def extract_entities():
    response = (
        supabase.table("observations")
        .select("id,text_evidence,value,raw_metadata")
        .eq("source", "youtube")
        .order("observed_at", desc=True)
        .limit(1000)
        .execute()
    )

    # Entity -> video_id -> evidence record.
    entity_videos = defaultdict(dict)

    # Observation ID -> behavior classification.
    observation_signals = {}

    for row in response.data or []:
        title = row.get("text_evidence") or ""
        metadata = row.get("raw_metadata") or {}
        observation_id = row.get("id")

        direction = classify_direction(title)

        if observation_id is not None:
            observation_signals[observation_id] = direction

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
                    "direction": direction,
                    "context": context,
                },
            )

    # Persist behavior classification for every processed YouTube observation.
    updated = 0

    for observation_id, direction in observation_signals.items():
        try:
            (
                supabase.table("observations")
                .update({"behavior_signal": direction})
                .eq("id", observation_id)
                .execute()
            )
            updated += 1
        except Exception as error:
            print(
                f"Could not update behavior_signal for observation "
                f"{observation_id}: {error}"
            )

    print(f"Persisted behavior signals for {updated} observations.")

    print("Detected entities:")

    for entity in KNOWN_ENTITIES:
        videos = entity_videos.get(entity, {})
        if not videos:
            continue

        adoption = sum(
            1 for item in videos.values()
            if item["direction"] == "adoption"
        )
        negative = sum(
            1 for item in videos.values()
            if item["direction"] == "negative"
        )
        interest = sum(
            1 for item in videos.values()
            if item["direction"] == "interest"
        )
        mixed = sum(
            1 for item in videos.values()
            if item["direction"] == "mixed"
        )
        neutral = sum(
            1 for item in videos.values()
            if item["direction"] == "neutral"
        )

        contexts = sorted({
            term
            for item in videos.values()
            for term in item["context"]
        })

        print(
            f"- {entity} | unique_videos={len(videos)} | "
            f"adoption={adoption} | negative={negative} | "
            f"interest={interest} | mixed={mixed} | neutral={neutral} | "
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
