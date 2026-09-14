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

# Words that are too generic to represent a useful consumer trend.

STOP_WORDS = {
"the", "and", "for", "with", "this", "that", "from",
"your", "you", "are", "was", "were", "have", "has",
"just", "about", "into", "their", "they", "them",
"product", "products", "viral", "trending", "trend",
"shorts", "short", "youtube", "video", "videos",
"usa", "right", "now", "new", "best", "top",
"everyone", "buying", "bought", "tested", "test",
"buy", "can", "but", "made", "going", "every",
"like", "really", "things", "thing", "know",
"get", "got", "one", "two", "all", "our",
"out", "its", "just", "day", "days",
"tiktok", "ytshorts", "fyp", "shortvideo",
}

# Words that are especially useful when they appear in consumer/product content.

PRIORITY_WORDS = {
"makeup",
"beauty",
"skincare",
"fashion",
"jewelry",
"kitchen",
"home",
"fitness",
"supplements",
"food",
"drink",
"coffee",
"snacks",
"chocolate",
"fashion",
"shoes",
"clothing",
"electronics",
"phone",
"gaming",
"pet",
"baby",
"travel",
"amazon",
"meesho",
"nestle",
"takis",
"milkshake",
"football",
"winter",
}

def extract_keywords(text):
"""Extract meaningful words from a YouTube title."""

```
words = re.findall(
    r"[a-zA-Z][a-zA-Z0-9'-]{2,}",
    text.lower()
)

useful_words = [
    word
    for word in words
    if word not in STOP_WORDS
]

return useful_words
```

def detect_trends():
"""Find recurring consumer/product themes in recent YouTube data."""

```
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

print(
    f"Found {len(observations)} recent "
    f"YouTube observations."
)

if not observations:
    print("No observations available yet.")
    return

keyword_counts = Counter()
keyword_videos = {}

for observation in observations:
    title = observation.get("text_evidence") or ""

    keywords = set(
        extract_keywords(title)
    )

    for keyword in keywords:
        keyword_counts[keyword] += 1

        if keyword not in keyword_videos:
            keyword_videos[keyword] = []

        keyword_videos[keyword].append(
            observation
        )

# Only keep themes that appear more than once.
candidates = [
    (keyword, count)
    for keyword, count in keyword_counts.items()
    if count >= 2
]

# Give useful consumer/product words a small priority boost.
candidates.sort(
    key=lambda item: (
        item[0] in PRIORITY_WORDS,
        item[1]
    ),
    reverse=True,
)

print("\nDetected meaningful recurring themes:")

created_or_updated = 0

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

        (
            supabase
            .table("trends")
            .update(
                {
                    "status": "active",
                }
            )
            .eq("id", trend_id)
            .execute()
        )

    else:
        result = (
            supabase
            .table("trends")
            .insert(
                {
                    "name": trend_name,
                    "first_detected_at": first_seen,
                    "status": "active",
                }
            )
            .execute()
        )

        trend_id = result.data[0]["id"]

    created_or_updated += 1

    print(
        f"- {trend_name}: "
        f"{count} observations"
    )

print(
    f"\nTrend detection complete. "
    f"Created/updated "
    f"{created_or_updated} trends."
)
```

if **name** == "**main**":
detect_trends()
