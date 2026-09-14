import os
import re
from collections import Counter
from datetime import datetime, timezone, timedelta

from supabase import create_client


SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
)


# Words that are useful for finding consumer/product themes.
# Common generic words are excluded so they don't dominate the results.
STOP_WORDS = {
    "the", "and", "for", "with", "this", "that", "from",
    "your", "you", "are", "was", "were", "have", "has",
    "just", "about", "into", "their", "they", "them",
    "product", "products", "viral", "trending", "trend",
    "shorts", "short", "youtube", "video", "videos",
    "usa", "right", "now", "new", "best", "top",
    "everyone", "buying", "bought", "tested", "test",
}


def extract_keywords(text):
    """Extract useful words from a YouTube title."""

    words = re.findall(r"[a-zA-Z][a-zA-Z0-9'-]{2,}", text.lower())

    useful_words = [
        word
        for word in words
        if word not in STOP_WORDS
    ]

    return useful_words


def detect_trends():
    """Find recurring consumer/product themes in recent YouTube data."""

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    response = (
        supabase
        .table("observations")
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

    keyword_counts = Counter()

    # Keep track of which videos mention each keyword.
    keyword_videos = {}

    for observation in observations:
        title = observation.get("text_evidence") or ""

        keywords = set(extract_keywords(title))

        for keyword in keywords:
            keyword_counts[keyword] += 1

            if keyword not in keyword_videos:
                keyword_videos[keyword] = []

            keyword_videos[keyword].append(observation)

    # Only consider themes appearing in at least two observations.
    candidates = [
        (keyword, count)
        for keyword, count in keyword_counts.items()
        if count >= 2
    ]

    candidates.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    print("\nDetected recurring themes:")

    for keyword, count in candidates[:20]:

        related = keyword_videos[keyword]

        first_seen = min(
            item["observed_at"]
            for item in related
        )

        trend_name = f"YouTube: {keyword}"

        existing = (
            supabase
            .table("trends")
            .select("id")
            .eq("name", trend_name)
            .limit(1)
            .execute()
        )

        if existing.data:
            trend_id = existing.data[0]["id"]

            supabase.table("trends").update(
                {
                    "status": "active",
                }
            ).eq("id", trend_id).execute()

        else:
            result = supabase.table("trends").insert(
                {
                    "name": trend_name,
                    "first_detected_at": first_seen,
                    "status": "active",
                }
            ).execute()

            trend_id = result.data[0]["id"]

        print(
            f"- {trend_name}: "
            f"{count} observations"
        )

    print(
        f"\nTrend detection complete. "
        f"Created/updated {min(len(candidates), 20)} trends."
    )


if __name__ == "__main__":
    detect_trends()
