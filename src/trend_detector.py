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

PRIORITY_WORDS = {
    "amazon","amazonfinds","beauty","makeup","skincare","skincareroutine",
    "skincaretips","fashion","jewelry","kitchen","home","fitness","food",
    "drink","coffee","snacks","chocolate","shoes","clothing","electronics",
    "phone","gaming","pet","baby","travel","meesho","nestle","takis",
    "milkshake","football","winter","tarte","cleaninghacks",
    "holidayshopping","tiktokmademebuy","amzonmustbuy",
}

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

# Content-quality rules. These classify what the video is evidence OF.
# They do not judge whether a trend is investable.
CONTENT_RULES = {
    "financial_news": [
        "stock market", "stock update", "crude oil", "business news",
        "market update", "share market", "financial news", "trading update",
    ],
    "research_media": [
        "mckinsey", "consumer reports", "research", "industry report",
        "consumer trends leaders", "trend report", "market trends",
    ],
    "direct_commerce": [
        "amazon finds", "amazon haul", "must buy", "must-have", "must have",
        "buying", "bought", "product review", "product reviews", "unboxing",
        "shopping", "finds", "products under", "products everyone is buying",
    ],
    "influencer_adoption": [
        "tiktok made me buy", "tiktok made me", "everyone is buying",
        "went broke buying", "viral", "obsessed", "haul",
    ],
    "consumer_behavior": [
        "made me buy", "can't live without", "switched to", "switching to",
        "stopped using", "instead of", "everyone loves", "everyone's",
        "favorite product", "daily routine", "routine", "what i use",
    ],
}

def clean_text(text):
    return re.sub(r"\s+", " ", (text or "").lower()).strip()

def extract_keywords(text):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9'-]{2,}", clean_text(text))
    return [w for w in words if w not in STOP_WORDS]

def extract_phrases(text):
    normalized = clean_text(text)
    return [p for p in PHRASE_SIGNALS if p in normalized]

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

def classify_content(title):
    text = clean_text(title)
    matched = []

    for category, phrases in CONTENT_RULES.items():
        if any(phrase in text for phrase in phrases):
            matched.append(category)

    # Strong exclusions take precedence.
    if "financial_news" in matched:
        return "financial_news"
    if "research_media" in matched:
        return "research_media"

    if "consumer_behavior" in matched:
        return "consumer_behavior"
    if "influencer_adoption" in matched:
        return "influencer_adoption"
    if "direct_commerce" in matched:
        return "direct_commerce"

    return "other"

def calculate_engagement_growth(observations):
    by_video = defaultdict(list)

    for observation in observations:
        vid = video_id_from_observation(observation)
        try:
            views = int(observation.get("value") or 0)
        except (TypeError, ValueError):
            views = 0
        by_video[vid].append((observation.get("observed_at"), views))

    records = []
    for vid, snapshots in by_video.items():
        snapshots.sort(key=lambda x: x[0] or "")
        if len(snapshots) < 2:
            continue

        start = snapshots[0][1]
        latest = snapshots[-1][1]

        records.append({
            "video_id": vid,
            "observations": len(snapshots),
            "starting_views": start,
            "latest_views": latest,
            "growth_ratio": None if start <= 0 else latest / start,
        })

    return records

def upsert_trend(name, related_observations):
    existing = (
        supabase.table("trends").select("id").eq("name", name).limit(1).execute()
    )
    first_seen = min(x["observed_at"] for x in related_observations)
    payload = {"status": "active", "first_detected_at": first_seen}

    if existing.data:
        supabase.table("trends").update(payload).eq(
            "id", existing.data[0]["id"]
        ).execute()
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
        .select(
            "observed_at,text_evidence,source,source_url,value,raw_metadata"
        )
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

    volume_observations = unique_observations(observations)

    print(
        f"Using {len(volume_observations)} unique YouTube videos "
        f"for trend-volume calculations."
    )

    # Classify unique videos so research/news content cannot inflate
    # direct consumer-behavior volume.
    content_counts = Counter()
    classified_videos = []

    for observation in volume_observations:
        category = classify_content(observation.get("text_evidence") or "")
        content_counts[category] += 1
        classified_videos.append((observation, category))

    print("\nContent-quality classification:")
    for category, count in content_counts.most_common():
        print(f"- {category}: {count}")

    # Only these categories are allowed to contribute to consumer-volume
    # trend detection. Research/media remains useful context but does not
    # count as direct consumer evidence.
    consumer_volume_observations = [
        observation
        for observation, category in classified_videos
        if category in {
            "consumer_behavior",
            "influencer_adoption",
            "direct_commerce",
        }
    ]

    print(
        f"Using {len(consumer_volume_observations)} videos as "
        f"consumer/commerce evidence."
    )

    growth = calculate_engagement_growth(observations)
    repeated = [x for x in growth if x["observations"] >= 2]

    print(f"Found {len(repeated)} videos with repeated engagement snapshots.")

    if repeated:
        print("\nStrongest observed engagement growth:")
        for item in sorted(
            repeated,
            key=lambda x: (
                x["growth_ratio"] if x["growth_ratio"] is not None else -1
            ),
            reverse=True,
        )[:10]:
            ratio = (
                "not calculable"
                if item["growth_ratio"] is None
                else f"{item['growth_ratio']:.2f}x"
            )
            print(
                f"- video={item['video_id']} | "
                f"snapshots={item['observations']} | "
                f"views={item['starting_views']:,}->"
                f"{item['latest_views']:,} | growth={ratio}"
            )

    daily_counts = defaultdict(Counter)
    keyword_observations = defaultdict(list)
    phrase_counts = Counter()
    phrase_observations = defaultdict(list)

    for observation in consumer_volume_observations:
        title = observation.get("text_evidence") or ""
        day = observation["observed_at"][:10]

        for keyword in set(extract_keywords(title)):
            daily_counts[keyword][day] += 1
            keyword_observations[keyword].append(observation)

        for phrase in extract_phrases(title):
            phrase_counts[phrase] += 1
            phrase_observations[phrase].append(observation)

    selected = []

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

    for phrase, total in phrase_counts.items():
        if total >= 2:
            selected.append({
                "name": f"YouTube behavior: {PHRASE_SIGNALS[phrase]}",
                "kind": "behavior",
                "total": total,
                "related": phrase_observations[phrase],
            })

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

        growth_ratio = (
            (recent_total / len(recent_days))
            / (older_total / len(older_days))
        )

        if growth_ratio >= 1.75 and recent_total >= 4:
            selected.append({
                "name": f"YouTube emerging: {keyword}",
                "kind": "accelerating",
                "total": total,
                "related": keyword_observations[keyword],
                "growth_ratio": growth_ratio,
            })

    existing = (
        supabase.table("trends")
        .select("id,name")
        .like("name", "YouTube%")
        .execute()
    )

    for trend in existing.data or []:
        supabase.table("trends").update(
            {"status": "inactive"}
        ).eq("id", trend["id"]).execute()

    unique = {item["name"]: item for item in selected}

    print("\nSelected consumer signals:")

    for item in sorted(
        unique.values(),
        key=lambda x: (x["kind"], -x["total"], x["name"])
    )[:40]:
        print(
            f"- {item['name']} | "
            f"type={item['kind']} | "
            f"consumer_videos={item['total']}"
        )
        upsert_trend(item["name"], item["related"])

    print(
        f"\nTrend detection complete. "
        f"Activated {min(len(unique), 40)} consumer signals."
    )

if __name__ == "__main__":
    detect_trends()
