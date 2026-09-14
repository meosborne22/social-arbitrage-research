import os
from datetime import datetime, timezone

from googleapiclient.discovery import build
from supabase import create_client


# -----------------------------
# Environment variables
# -----------------------------

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]
YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]


# -----------------------------
# Connect to Supabase
# -----------------------------

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
)


# -----------------------------
# Connect to YouTube
# -----------------------------

youtube = build(
    "youtube",
    "v3",
    developerKey=YOUTUBE_API_KEY,
)


# -----------------------------
# Initial search terms
# -----------------------------
# Keep this list small while we test.
# Each term uses one YouTube search.list call.

SEARCH_TERMS = [
    "viral products",
    "new consumer trends",
    "TikTok made me buy it",
    "products everyone is buying",
    "Amazon finds",
]


# -----------------------------
# Collect YouTube results
# -----------------------------

def collect_youtube_results():

    collected_at = datetime.now(timezone.utc).isoformat()

    total_saved = 0

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

        for item in response.get("items", []):

            video_id = item.get("id", {}).get("videoId")

            if not video_id:
                continue

            snippet = item.get("snippet", {})

            observation = {
                "source": "youtube",
                "source_id": video_id,
                "observed_at": collected_at,
                "raw_text": snippet.get("title", ""),
                "metadata": {
                    "search_term": term,
                    "channel_title": snippet.get("channelTitle"),
                    "channel_id": snippet.get("channelId"),
                    "published_at": snippet.get("publishedAt"),
                    "description": snippet.get("description"),
                    "video_url": (
                        f"https://www.youtube.com/watch?v={video_id}"
                    ),
                },
            }

            try:

                supabase.table("observations").insert(
                    observation
                ).execute()

                total_saved += 1

            except Exception as error:

                print(
                    f"Could not save video {video_id}: {error}"
                )

    print(
        f"YouTube collection complete. "
        f"Saved {total_saved} observations."
    )


# -----------------------------
# Start collector
# -----------------------------

if __name__ == "__main__":
    collect_youtube_results()
