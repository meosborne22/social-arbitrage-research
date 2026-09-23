import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

STOP_WORDS = {
    "the","and","for","with","this","that","from","your","you","are","was",
    "were","have","has","just","about","into","their","they","them","product",
    "products","viral","trending","trend","shorts","short","youtube","video",
    "videos","usa","right","now","new","best","top","everyone","buying",
    "bought","tested","test","buy","can","but","made","going","every","like",
    "really","things","thing","know","get","got","one","two","all","our","out",
    "its","day","days","tiktok","ytshorts","fyp","shortvideo","2026","america",
    "business","consumer","changed","actually","finds","live","regret",
    "unsolved","flawless","holiday","comment","everything","fall","life",
    "link","love","needs","obsessed","penny","quot","single","stop","store",
    "tips","under","useful","what","worth","amp","crude","poisoning",
    "everyone","musthave",
}

PRIORITY_WORDS = {
    "makeup","beauty","skincare","fashion","jewelry","kitchen","home",
    "fitness","food","drink","coffee","snacks","chocolate","shoes","clothing",
    "electronics","phone","gaming","pet","baby","travel","amazon","amazonfinds",
    "meesho","nestle","takis","milkshake","football","winter",
    "tarte","skincareroutine","tiktokmademebuy",
}

def extract_keywords(text):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9'-]{2,}", text.lower())
    return [word for word in words if word not in STOP_WORDS]

def detect_trends():
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)

    response = (
        supabase.table("observations")
        .select("observed_at,text_evidence,source,source_url,value,raw_metadata")
        .eq("source", "youtube")
        .gte("observed_at", cutoff.isoformat())
        .order("observed_at", desc=True)
        .limit(1000)
        .execute()
    )

    observations = response.data or []
    print(f"Found {len(observations)} recent YouTube observations.")

    if not observations:
        print("No observations available yet.")
        return

    daily_counts = defaultdict(Counter)
    keyword_observations = defaultdict(list)

    for observation in observations:
        title = observation.get("text_evidence") or ""
        keywords = set(extract_keywords(title))
        day = observation["observed_at"][:10]

        for keyword in keywords:
            daily_counts[keyword][day] += 1
            keyword_observations[keyword].append(observation)

    candidates = []

    for keyword, counts in daily_counts.items():
        total = sum(counts.values())
        active_days = len(counts)

        if total < 3 or active_days < 2:
            continue

        recent_days = sorted(counts.keys())[-3:]
        older_days = sorted(counts.keys())[:-3]
        recent_total = sum(counts[d] for d in recent_days)
        older_total = sum(counts[d] for d in older_days)

        if older_total > 0:
            recent_avg = recent_total / len(recent_days)
            older_avg = older_total / len(older_days)
            growth_ratio = recent_avg / older_avg
        else:
            growth_ratio = 2.0 if recent_total >= 2 else 1.0

        # Keep known consumer categories/brands, plus only
        # genuinely accelerating unknown terms.
        is_priority = keyword in PRIORITY_WORDS
        is_accelerating = growth_ratio >= 1.25 and recent_total >= 3

        if is_priority or is_accelerating:
            candidates.append({
                "keyword": keyword,
                "total": total,
                "active_days": active_days,
                "recent_total": recent_total,
                "growth_ratio": growth_ratio,
                "priority": is_priority,
            })

    candidates.sort(
        key=lambda item: (
            item["priority"],
            item["growth_ratio"],
            item["recent_total"],
            item["active_days"],
        ),
        reverse=True,
    )

    # First mark existing YouTube trends inactive.
    existing = (
        supabase.table("trends")
        .select("id,name")
        .like("name", "YouTube: %")
        .execute()
    )

    for trend in existing.data or []:
        (
            supabase.table("trends")
            .update({"status": "inactive"})
            .eq("id", trend["id"])
            .execute()
        )

    print("\nCurrent consumer themes:")

    activated = 0

    for item in candidates[:25]:
        keyword = item["keyword"]
        trend_name = f"YouTube: {keyword}"

        print(
            f"- {trend_name}: recent={item['recent_total']}, "
            f"total={item['total']}, active_days={item['active_days']}, "
            f"growth_ratio={item['growth_ratio']:.2f}x"
        )

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
            related = keyword_observations[keyword]
            first_seen = min(item["observed_at"] for item in related)

            supabase.table("trends").insert({
                "name": trend_name,
                "first_detected_at": first_seen,
                "status": "active",
            }).execute()

        activated += 1

    print(
        f"\nTrend detection complete. "
        f"Activated {activated} current themes."
    )

if __name__ == "__main__":
    detect_trends()
