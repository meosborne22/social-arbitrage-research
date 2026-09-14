import os
from datetime import datetime, timezone

from googleapiclient.discovery import build
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]
YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

youtube = build(
    "youtube",
    "v3",
    developerKey=YOUTUBE_API_KEY,
)

SEARCH_TERMS = [
    "viral products",
    "new consumer trends",
    "TikTok made me buy it",
    "products everyone is buying",
    "Amazon finds",
]


def collect_youtube_results():
    collected_at = datetime.now(timezone.utc).isoformat()
    total_saved = 0
    total_skipped = 0

    for term in SEARCH_TERMS:
        print(f"Searching YouTube for: {term}")

        response = youtube.search().list(
            part="snippet",
            q=term,
            type="video",
            order="date",
            maxResults=10,
            regionCode="US",
            relevanceLanguage="en",
        ).execute()

        video_ids = []

        for item in response.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if video_id:
                video_ids.append(video_id)

        if not video_ids:
            continue

        stats_response = youtube.videos().list(
            part="snippet,statistics",
            id=",".join(video_ids),
        ).execute()

        stats_by_id = {
            item["id"]: item
            for item in stats_response.get("items", [])
        }

        for item in response.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if not video_id:
                continue

            # Prevent duplicate observations for the same YouTube video.
            existing = (
                supabase.table("observations")
                .select("id")
                .eq("source", "youtube")
                .eq(
                    "source_url",
                    f"https://www.youtube.com/watch?v={video_id}",
                )
                .limit(1)
                .execute()
            )

            if existing.data:
                total_skipped += 1
                print(f"Skipped existing video: {video_id}")
                continue

            snippet = item.get("snippet", {})
            video_data = stats_by_id.get(video_id, {})
            statistics = video_data.get("statistics", {})

            view_count = int(statistics.get("viewCount", 0))
            like_count = int(statistics.get("likeCount", 0))
            comment_count = int(statistics.get("commentCount", 0))

            video_url = f"https://www.youtube.com/watch?v={video_id}"

            observation = {
                "observed_at": collected_at,
                "source": "youtube",
                "source_url": video_url,
                "entity": snippet.get("channelTitle"),
                "observation_type": "youtube_video",
                "metric": "video_engagement",
                "value": view_count,
                "text_evidence": snippet.get("title", ""),
                "reliability": 0.80,
                "raw_metadata": {
                    "video_id": video_id,
                    "search_term": term,
                    "channel_title": snippet.get("channelTitle"),
                    "channel_id": snippet.get("channelId"),
                    "published_at": snippet.get("publishedAt"),
                    "description": snippet.get("description"),
                    "view_count": view_count,
                    "like_count": like_count,
                    "comment_count": comment_count,
                    "video_url": video_url,
                },
            }

            try:
                supabase.table("observations").insert(
                    observation
                ).execute()

                total_saved += 1

                print(
                    f"Saved: {snippet.get('title', '')} | "
                    f"Views: {view_count:,} | "
                    f"Likes: {like_count:,} | "
                    f"Comments: {comment_count:,}"
                )

            except Exception as error:
                print(
                    f"Could not save video {video_id}: {error}"
                )

    print(
        f"YouTube collection complete. "
        f"Saved {total_saved} new observations; "
        f"skipped {total_skipped} duplicates."
    )


if __name__ == "__main__":
    collect_youtube_results()
