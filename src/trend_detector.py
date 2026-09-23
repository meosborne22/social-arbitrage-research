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
    "tips","under","useful","what","worth","amp","crude","poisoning","did",
    "mystery","luxury","outfit","skin",
}

# These are useful consumer categories or brands. They are allowed
# to become themes even when they are not rapidly accelerating yet.
PRIORITY_WORDS = {
    "amazon","amazonfinds","beauty","makeup","skincare","skincareroutine",
    "skincaretips","fashion","jewelry","kitchen","home","fitness","food",
    "drink","coffee","snacks","chocolate","shoes","clothing","electronics",
    "phone","gaming","pet","baby","travel","meesho","nestle","takis",
    "milkshake","football","winter","tarte","cleaninghacks",
    "holidayshopping","tiktokmademebuy","amzonmustbuy",
}

# Phrase signals are stronger than isolated words because they describe
# consumer behavior rather than generic vocabulary.
PHRASE_SIGNALS = {
    "tiktok made me buy": "TikTok purchase influence",
    "made me buy it": "social purchase influence",
    "must buy": "purchase intent",
    "worth the hype": "purchase validation",
    "everyone's raving": "word of mouth",
    "everyone is buying": "broad purchase intent",
    "selling products": "sales signal",
    "viral product": "product virality",
    "amazon finds": "Amazon discovery",
    "amazon haul": "Amazon shopping behavior",
    "amazon gadgets": "Amazon gadget demand",
}

def clean_text(text):
    return re.sub(r"\s+", " ", (text or "").lower()).strip()

def extract_keywords(text):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9'-]{2,}", clean_text(text))
    return [word for word in words if word not in STOP_WORDS]

def extract_phrases(text):
    normalized = clean_text(text)
    return [phrase for phrase in PHRASE_SIGNALS if phrase in normalized]

def upsert_trend(name, related_observations):
    existing = (
        supabase.table("trends")
        .select("id")
        .eq("name", name)
        .limit(1)
        .execute()
    )

    first_seen = min(item["observed_at"] for item in related_observations)

    if existing.data:
        trend_id = existing.data[0]["id"]
        (
            supabase.table("trends")
            .update({
                "status": "active",
                "first_detected_at": first_seen,
            })
            .eq("id", trend_id)
            .execute()
        )
    else:
        supabase.table("trends").insert({
            "name": name,
            "first_detected_at": first_seen,
            "status": "active",
        }).execute()

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
    phrase_counts = Counter()
    phrase_observations = defaultdict(list)

    for observation in observations:
        title = observation.get("text_evidence") or ""
        day = observation["observed_at"][:10]

        for keyword in set(extract_keywords(title)):
            daily_counts[keyword][day] += 1
            keyword_observations[keyword].append(observation)

        for phrase in extract_phrases(title):
            phrase_counts[phrase] += 1
            phrase_observations[phrase].append(observation)

    selected = []

    # 1. Meaningful consumer categories/brands.
    for keyword in PRIORITY_WORDS:
        counts = daily_counts.get(keyword, Counter())
        total = sum(counts.values())
        if total >= 2:
            selected.append({
                "name": f"YouTube: {keyword}",
                "kind": "category",
                "total": total,
                "related": keyword_observations[keyword],
            })

    # 2. Strong behavior phrases.
    for phrase, total in phrase_counts.items():
        if total >= 2:
            selected.append({
                "name": f"YouTube behavior: {PHRASE_SIGNALS[phrase]}",
                "kind": "behavior",
                "total": total,
                "related": phrase_observations[phrase],
            })

    # 3. Unknown words are admitted only if they are both repeated
    # and accelerating. This prevents generic words like "did" from
    # becoming themes simply because they appeared a few times.
    for keyword, counts in daily_counts.items():
        if keyword in PRIORITY_WORDS:
            continue

        total = sum(counts.values())
        days = sorted(counts.keys())

        if total < 4 or len(days) < 3:
            continue

        recent_days = days[-3:]
        older_days = days[:-3]
        recent_total = sum(counts[d] for d in recent_days)
        older_total = sum(counts[d] for d in older_days)

        if older_total <= 0:
            continue

        recent_avg = recent_total / len(recent_days)
        older_avg = older_total / len(older_days)
        growth_ratio = recent_avg / older_avg

        if growth_ratio >= 1.75 and recent_total >= 4:
            selected.append({
                "name": f"YouTube emerging: {keyword}",
                "kind": "accelerating",
                "total": total,
                "related": keyword_observations[keyword],
                "growth_ratio": growth_ratio,
            })

    # Deactivate all existing YouTube themes first.
    existing = (
        supabase.table("trends")
        .select("id,name")
        .like("name", "YouTube%")
        .execute()
    )

    for trend in existing.data or []:
        (
            supabase.table("trends")
            .update({"status": "inactive"})
            .eq("id", trend["id"])
            .execute()
        )

    # Remove duplicate selections by name.
    unique = {}
    for item in selected:
        unique[item["name"]] = item

    print("\nSelected consumer signals:")

    for item in sorted(
        unique.values(),
        key=lambda x: (x["kind"], -x["total"], x["name"])
    )[:40]:
        print(
            f"- {item['name']} | "
            f"type={item['kind']} | "
            f"observations={item['total']}"
        )
        upsert_trend(item["name"], item["related"])

    print(
        f"\nTrend detection complete. "
        f"Activated {min(len(unique), 40)} consumer signals."
    )

if __name__ == "__main__":
    detect_trends()
