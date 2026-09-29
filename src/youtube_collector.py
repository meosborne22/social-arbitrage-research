import os
import sys
import requests
from datetime import datetime, timezone, timedelta

YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3"
SEARCH_QUERIES = [
    "TikTok made me buy it",
    "everyone is buying this product",
    "sold out everywhere product",
    "products selling out",
    "I switched from to product",
    "holy grail product worth it",
    "new product everyone loves",
    "Amazon finds viral product",
]
MAX_RESULTS_PER_QUERY = 10


def required_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required GitHub Actions secret/environment variable: {name}")
    return value


def youtube_get(endpoint, params):
    response = requests.get(
        f"{YOUTUBE_API_URL}/{endpoint}", params=params, timeout=30
    )
    if not response.ok:
        raise RuntimeError(
            f"YouTube API request failed ({response.status_code}): {response.text[:1000]}"
        )
    return response.json()


def headers(api_key):
    return {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def existing_video_ids(supabase_url, api_key, video_ids):
    found = set()
    url = f"{supabase_url.rstrip('/')}/rest/v1/observations"
    for start in range(0, len(video_ids), 100):
        batch = video_ids[start:start + 100]
        params = {
            "select": "raw_metadata",
            "source": "eq.youtube",
            "raw_metadata->>video_id": f"in.({','.join(batch)})",
            "limit": "1000",
        }
        response = requests.get(
            url, headers=headers(api_key), params=params, timeout=30
        )
        if not response.ok:
            raise RuntimeError(
                f"Supabase duplicate-check failed ({response.status_code}): {response.text[:1000]}"
            )
        for row in response.json():
            video_id = (row.get("raw_metadata") or {}).get("video_id")
            if video_id:
                found.add(video_id)
    return found


def get_video_details(api_key, video_ids):
    details = {}
    for start in range(0, len(video_ids), 50):
        batch = video_ids[start:start + 50]
        data = youtube_get("videos", {
            "part": "snippet,statistics",
            "id": ",".join(batch),
            "key": api_key,
        })
        for item in data.get("items", []):
            details[item["id"]] = item
    return details


def main():
    youtube_api_key = required_env("YOUTUBE_API_KEY")
    supabase_url = required_env("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_KEY")
    if not supabase_key:
        raise RuntimeError("Missing SUPABASE_SECRET_KEY (or SUPABASE_KEY).")

    candidates = {}
    for query in SEARCH_QUERIES:
        print(f"Searching YouTube for: {query}")
        data = youtube_get("search", {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": MAX_RESULTS_PER_QUERY,
            "order": "date",
            "regionCode": "US",
            "relevanceLanguage": "en",
            "publishedAfter": (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "key": youtube_api_key,
        })
        for item in data.get("items", []):
            video_id = (item.get("id") or {}).get("videoId")
            if not video_id:
                continue
            snippet = item.get("snippet") or {}
            previous = candidates.get(video_id, {})
            candidates[video_id] = {
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt"),
                "description": snippet.get("description", ""),
                "search_queries": sorted(set(previous.get("search_queries", []) + [query])),
            }

    ids = list(candidates)
    print(f"Found {len(ids)} unique candidate videos across {len(SEARCH_QUERIES)} searches.")
    if not ids:
        print("No videos found; nothing to insert.")
        return

    existing = existing_video_ids(supabase_url, supabase_key, ids)
    new_ids = [video_id for video_id in ids if video_id not in existing]
    print(f"{len(existing)} already exist; {len(new_ids)} new videos to evaluate.")
    if not new_ids:
        print("No new videos to insert.")
        return

    details = get_video_details(youtube_api_key, new_ids)
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for video_id in new_ids:
        candidate = candidates[video_id]
        detail = details.get(video_id, {})
        snippet = detail.get("snippet") or {}
        stats = detail.get("statistics") or {}
        views = int(stats.get("viewCount", 0))
        likes = int(stats["likeCount"]) if "likeCount" in stats else None
        comments = int(stats["commentCount"]) if "commentCount" in stats else None
        rows.append({
            "observed_at": now,
            "source": "youtube",
            "source_url": f"https://www.youtube.com/watch?v={video_id}",
            "entity": snippet.get("channelTitle") or candidate["channel_title"] or "YouTube",
            "observation_type": "video",
            "metric": "views",
            "value": views,
            "text_evidence": snippet.get("title") or candidate["title"],
            "reliability": 0.5,
            "raw_metadata": {
                "video_id": video_id,
                "channel_title": snippet.get("channelTitle") or candidate["channel_title"],
                "published_at": snippet.get("publishedAt") or candidate["published_at"],
                "description": snippet.get("description") or candidate["description"],
                "like_count": likes,
                "comment_count": comments,
                "search_queries": candidate["search_queries"],
                "collector": "youtube_collector_v2",
            },
        })

    url = f"{supabase_url.rstrip('/')}/rest/v1/observations"
    response = requests.post(
        url, headers=headers(supabase_key), json=rows, timeout=30
    )
    if not response.ok:
        raise RuntimeError(
            f"Supabase insert failed ({response.status_code}): {response.text[:2000]}"
        )
    print(f"Inserted {len(rows)} new YouTube video observations.")
    print("Search settings: regionCode=US, relevanceLanguage=en, rolling 30-day window.")
    print("Reminder: these settings bias results; they do not guarantee U.S. creators or viewers.")
    print("Reminder: titles and views are discovery clues, not verified sales.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
