import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

# Generic words that do not represent a useful consumer trend by themselves.
STOP_WORDS = {
    "the", "and", "for", "with", "this", "that", "from", "your", "you",
    "are", "was", "were", "have", "has", "had", "just", "about", "into",
    "their", "they", "them", "our", "out", "its", "now", "new", "best",
    "top", "every", "all", "one", "two", "three", "thing", "things",
    "stuff", "really", "very", "more", "most", "much", "many", "like",
    "know", "going", "got", "get", "can", "could", "would", "should",
    "made", "make", "making", "buy", "buying", "bought", "want", "wanted",
    "need", "needed", "test", "tested", "testing", "review", "reviews",
    "video", "videos", "short", "shorts", "youtube", "ytshorts", "fyp",
    "viral", "trending", "trend", "trends", "usa", "right", "day", "days",
    "live", "business", "consumer", "changed", "change", "unsolved",
    "find", "finds", "amazon", "product", "products",
}

# Terms that are especially useful as early consumer-behavior clues.
PRIORITY_WORDS = {
    "makeup", "beauty", "skincare", "fashion", "jewelry", "kitchen", "home",
    "fitness", "food", "drink", "coffee", "snacks", "chocolate", "shoes",
    "clothing", "electronics", "phone", "gaming", "pet", "baby", "travel",
    "nestle", "takis", "milkshake", "football", "winter", "amazonfinds",
    "meesho",
}

def extract_keywords(text):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9'-]{2,}", text.lower())
    return [word for word in words if word not in STOP_WORDS]

def detect_trends():
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    response = (
        supabase.table("observations")
        .select("*")
        .eq("source", "youtube")
        .gte("observed_at", cutoff.isoformat())
        .order("observed_at", desc=True)
        .limit(500)
        .execute()
    )

    observations = response.data or []
    print(f"Found {len(observations)} recent YouTube observations.")

    if not observations:
        print("No observations available yet.")
        return

    # Count a keyword once per video, not multiple times within one title.
    keyword_counts = Counter()
    keyword_observations = defaultdict(list)

    for observation in observations:
        title = observation.get("text_evidence") or ""
        keywords = set(extract_keywords(title))

        for keyword in keywords:
            keyword_counts[keyword] += 1
            keyword_observations[keyword].append(observation)

    # Require repeated appearances before creating a trend.
    candidates = [
        (keyword, count)
        for keyword, count in keyword_counts.items()
        if count >= 2
    ]

    candidates.sort(
        key=lambda item: (
            item[0] in PRIORITY_WORDS,
            item[1],
        ),
        reverse=True,
    )

    print("\nDetected meaningful recurring themes:")

    created_or_updated = 0

    for keyword, count in candidates[:20]:
        related = keyword_observations[keyword]
        first_seen = min(item["observed_at"] for item in related)
        trend_name = f"YouTube: {keyword}"

        existing = (
            supabase.table("trends")
            .select("id")
            .eq("name", trend_name)
            .limit(1)
            .execute()
        )

        if existing.data:
            trend_id = existing.data[0]["id"]
            (
                supabase.table("trends")
                .update({"status": "active"})
                .eq("id", trend_id)
                .execute()
            )
        else:
            supabase.table("trends").insert({
                "name": trend_name,
                "first_detected_at": first_seen,
                "status": "active",
            }).execute()

        created_or_updated += 1
        print(f"- {trend_name}: {count} observations")

    print(
        f"\nTrend detection complete. "
        f"Created/updated {created_or_updated} trends."
    )

if __name__ == "__main__":
    detect_trends()
