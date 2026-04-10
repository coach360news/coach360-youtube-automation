import json
import os
from datetime import date
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# Load credentials
creds = Credentials.from_authorized_user_file("token.json", [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/drive.readonly"
])

# Load schedule
with open("YOUTUBE_SCHEDULE.json") as f:
    schedule = json.load(f)

# Find today's posts
today = str(date.today())
todays_posts = [s for s in schedule if s["post_date"] == today]

if not todays_posts:
    print(f"No posts scheduled for {today}. Done.")
    exit()

# Build Drive and YouTube clients
drive = build("drive", "v3", credentials=creds)
youtube = build("youtube", "v3", credentials=creds)

for post in todays_posts:
    title = post["copy"]["youtube_title"]
    print(f"Processing: {title}")

    # Find and download video from Google Drive
    filename = os.path.basename(post["path"])
    results = drive.files().list(
        q=f"name='{filename}'",
        fields="files(id, name)"
    ).execute()
    files = results.get("files", [])

    if not files:
        print(f"  File not found in Drive: {filename}")
        continue

    file_id = files[0]["id"]
    request = drive.files().get_media(fileId=file_id)
    with open(filename, "wb") as f:
        f.write(request.execute())
    print(f"  Downloaded: {filename}")

    # Upload to YouTube
    body = {
        "snippet": {
            "title": title,
            "description": post["copy"]["youtube_description"],
            "tags": post["copy"]["hashtags"].replace("#", "").split(),
            "categoryId": "17"
        },
        "status": {"privacyStatus": "public"}
    }

    media = MediaFileUpload(filename, mimetype="video/mp4", resumable=True)
    response = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    ).execute()

    print(f"  Uploaded: https://youtube.com/watch?v={response['id']}")
    os.remove(filename)

print("Done.")
